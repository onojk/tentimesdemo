#!/usr/bin/env python3
"""Ten Times, Not a Hundred — rendered offline.

    .venv/bin/python render.py out.mp4 --audio audio/ten_times.wav --start 0 --dur 7.5 [--res 480]
    .venv/bin/python render.py out.mp4 --audio audio/ten_times.wav --section intro --res 480
    .venv/bin/python render.py out.mp4 --audio audio/ten_times.wav --full [--res 2160 --crf 16]
    .venv/bin/python render.py - --still 3.2 --still 7.0          # stills only

Copied from laser-beam-demo's render.py: the render loop, uniform plumbing, quarter-size
two-pass bloom, ffmpeg rgb24 pipe and audio mux are the same. Deterministic: time =
frame / 30, never the wall clock, and grain is a hash of the pixel and frame number.

Changed: scenes write linear RGB, not three emission channels, because the tower needs six
fixed hues (HEAD's TD, RHO, PM1, PM2, DARK, WHITE) on pure black. The post pass keeps bloom,
tone map, a mild vignette and grain; the tape warp, scanlines and scroller are gone.
"""
import argparse, json, os, subprocess, sys, tempfile
import numpy as np
import moderngl
from sync import Sync, FPS

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SEED = 0x10C5                    # the only source of noise; change it to re-roll the grain
TOWER = os.path.join(HERE, "data", "tower.json")
# the one number whose ray the intro draws (and the bridge lights): the first 72-bit point
# that the short arm (p-1 stage 2 at 10 B1) finds
RAY_SIZE, RAY_LAMP = 72, "pm1_s2"
R_RIM, R_SPINE = 0.86, 0.035     # screen radius (P units) of theta = 8/n and of the spine
ASSEMBLE_RINGS = 16              # verse 1: rings per band, one per beat
ASSEMBLE_TILT = 7.0              # verse 1: seconds to tilt from top-down to the orbit
FLAP_U = (0.75, 4.25)            # verse 2: plotted range of u = ln p / ln B1
FLAP_C = (3.4, 1.41)             # verse 2: c before and after "one-point-four" (NOTES)
FLAP_SPRING = (0.28, 1.3)        # verse 2: damping ratio and period (s) of c's settle
FLAP_SAMPLES = 96                # verse 2: curve samples
FLAP_CAPTION = 3.2               # verse 2: s after "one-point-four" the caption fades in
FLIP_DUR = 0.09                  # verse 2: one flap flip, s
QUARTET_FLASH = 0.12             # pre-choruses: decay (s) of the one white flash on "yes"
# choruses: (tower size, cue, cost change with stage 2 to 100 B1, to 10 B1), percent. Costs
# from NOTES, "Real-prime split-half search", stage 2 appended to the stage-1 pipeline,
# plain (2 multiplies per prime) -- NOTES writes savings as positive (+6.4 / ... 100: -42.8),
# shown here as the change in cost. Point counts come from tower.json.
ARMS = {"chorus1": (72, "forty_three1", +42.8, -6.4), "chorus2": (84, "forty_three2", +35.6, -4.6)}
ARM_LONG = (-5.3, 0.0)           # long-arm sweep and bar climb, s relative to "forty-three"
ARM_SHORT = (1.7, 1.7 + 2.27)    # short-arm sweep and bar (one bar long), same reference
ARM_GREY = 4.8                   # the long arm's extra points grey out ("light the wedge")
ARM_EL, ARM_DIST, ARM_SHIFT = 40.0, 3.1, -0.16   # chorus camera: elevation, distance, NDC shift
LABEL_W, LABEL_H, LABEL_SIZE = 400, 72, 46
# verse 3: the card's rho, from NOTES (outside checks, second round): mean 552.0 f
# evaluations at detection against mean mu + lambda 279.4 on 16-bit primes
RHO_TEXT = ["552 / 279", "f evaluations at detection / \u03bc + \u03bb, mean on 16-bit primes"] + \
           [f"r = {2 ** k}" for k in range(8)]
RHO_TEXT_W, RHO_TEXT_H = 1400, 96
RHO_CAPTION = 0.6                # s after the flash that "552 / 279" fades in
ECM = os.path.join(HERE, "data", "ecm.json")
ECM_PRICE = 8187                 # verse 4: ruint per ECM curve at B1 = 257 (NOTES, I-017)
ECM_TEXT = "ruint per ECM curve at B1 = 257"
ECM_COUNT_FROM = 0.27            # verse 4: the ticker starts this long after the section start
ECM_FLOOD = 1.2                  # verse 4: s for the floodlight to wash in
BRIDGE_L = ((-0.89, 0.0), 0.72)  # bridge: left panel's centre and rim radius (P units)
BRIDGE_SHIFT, BRIDGE_DIST, BRIDGE_EL = 0.50, 5.1, 24.0   # bridge: right panel's tower camera
BRIDGE_A_END = 13.2              # bridge: s after "a thousand rays" by which half A has filled
BRIDGE_B_DUR = 1.8               # bridge: s for half B to fill after "the other half"

VERT = """
#version 330
in vec2 pos;
out vec2 uv;
void main() { uv = pos * 0.5 + 0.5; gl_Position = vec4(pos, 0.0, 1.0); }
"""

# Shared header for scene shaders: uv in [0,1], P() centred with y in [-1,1].
HEAD = """
#version 330
in vec2 uv;
out vec4 frag;
uniform vec2 res;
uniform float t, ts, sdur, local;     // time; time / length / progress in this section
uniform float rms, low, mid, high;    // 0..1, loudness and the three bands
uniform float phrase, swell;          // ~4 s spectral centroid; smoothed choir swell
uniform float beat, since_beat;       // beats elapsed (float); seconds since the last beat
uniform float kick;                   // strong-onset pulse (spaced under 3 per second)
uniform float travel;                 // integral of rms-driven speed: a position, never jumps
uniform vec4 quartet;                 // bass, baritone, lead, tenor, 0..1 in the pre-choruses
uniform int n_tick, ticks_total;      // clock ticks so far in this section / in all of it
uniform float since_tick;             // seconds since the last tick (1e3 before any)
uniform float music;                  // 1 while the music plays, 0 after the cut
uniform int seed;
const vec3 TD    = vec3(1.00, 0.45, 0.08);    // trial division: orange
const vec3 RHO   = vec3(0.20, 0.45, 1.00);    // rho: blue
const vec3 PM1   = vec3(0.05, 0.62, 0.22);    // p-1 stage 1: deep green
const vec3 PM2   = vec3(0.50, 1.00, 0.55);    // p-1 stage 2: light green
const vec3 DARK  = vec3(0.32, 0.33, 0.35);    // unlit, and the spine: grey
const vec3 WHITE = vec3(1.00, 0.98, 0.95);
const float PI = 3.14159265;
vec2 P() { return (uv * res - 0.5 * res) / (0.5 * res.y); }
float px() { return 2.0 / res.y; }            // one output pixel in P units
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float rnd(float n) { return float(hash(uint(int(n)) ^ uint(seed))) / 4294967295.0; }
// glow of a distance d (in P units): a sharp core plus a soft halo
float glow(float d, float w) { return exp(-d * d / (w * w)) + 0.15 * w / (abs(d) + w); }
// distance from p to the segment a-b, and the position along it (0..1)
float seg(vec2 p, vec2 a, vec2 b, out float h) {
    vec2 pa = p - a, ba = b - a;
    h = clamp(dot(pa, ba) / max(dot(ba, ba), 1e-12), 0.0, 1.0);
    return length(pa - ba * h);
}
"""

FALLBACK = "void main() { frag = vec4(0.0, 0.0, 0.0, 1.0); }\n"   # a scene not written yet

# The point pass: the tower's points as gaussian sprites, added onto the scene before the
# bloom. One vertex per point: rah = (radius, angle, height in bits), attr = (lamp at 10 B1,
# lamp at 100 B1, s2 ratio q / B1, split half 0 / 1), key = the scene's own schedule value
# (for example a landing time). Each scene's fx/<scene>.pts.glsl writes main(), using place()
# and lamp_col() from this header. Lamp ids follow LAMPS, then 5 = the spine column.
PTS_HEAD = """
#version 330
in vec3 rah;
in vec4 attr;
in float key;
out vec3 v_col;
out float v_a;
uniform mat4 view_proj;
uniform vec2 res;
uniform float point_px, cam_dist;
uniform float t, ts, sdur, local, rms, kick, beat, since_beat, swell, travel;
uniform int seed;
const vec3 TD    = vec3(1.00, 0.45, 0.08);
const vec3 RHO   = vec3(0.20, 0.45, 1.00);
const vec3 PM1   = vec3(0.05, 0.62, 0.22);
const vec3 PM2   = vec3(0.50, 1.00, 0.55);
const vec3 DARK  = vec3(0.32, 0.33, 0.35);
const vec3 WHITE = vec3(1.00, 0.98, 0.95);
const float BAND = 0.42;                  // world height between the 72, 84 and 96 bands
// z is mirrored so that the orbit camera seen from straight above shows angle a at
// (cos a, sin a) on screen, as the intro draws it
vec3 world(vec3 q) { return vec3(2.0 * q.x * cos(q.y), (q.z - 84.0) / 12.0 * BAND, -2.0 * q.x * sin(q.y)); }
vec3 lamp_col(float l) {
    return l < 0.5 ? TD : l < 1.5 ? RHO : l < 2.5 ? PM1 : l < 3.5 ? PM2 : DARK;
}
void place(vec3 w, float size) {
    gl_Position = view_proj * vec4(w, 1.0);
    gl_PointSize = max(1.0, size * point_px * cam_dist / max(gl_Position.w, 0.1));
}
"""

PTS_FRAG = """
#version 330
in vec3 v_col;
in float v_a;
out vec4 frag;
void main() {
    vec2 d = gl_PointCoord * 2.0 - 1.0;
    float r2 = dot(d, d);
    if (r2 > 1.0 || v_a <= 0.0) discard;
    frag = vec4(v_col * v_a * exp(-r2 * 3.0), 1.0);
}
"""

DOWN = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D src;
void main() { frag = vec4(texture(src, uv).rgb, 1.0); }
"""

BLUR = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D src;
uniform vec2 dir;                 // one texel along the blur axis
const float W[5] = float[5](0.227027, 0.1945946, 0.1216216, 0.054054, 0.016216);
void main() {
    vec3 c = texture(src, uv).rgb * W[0];
    for (int i = 1; i < 5; i++) {
        c += texture(src, uv + dir * float(i) * 1.5).rgb * W[i];
        c += texture(src, uv - dir * float(i) * 1.5).rgb * W[i];
    }
    frag = vec4(c, 1.0);
}
"""

POST = """
#version 330
in vec2 uv;
out vec4 frag;
uniform sampler2D scene, bloom;
uniform vec2 res;
uniform float kick, gain, bloom_gain;
uniform int frame, seed;
uint hash(uint x) { x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16; return x; }
float grain(ivec2 px) {
    uint h = hash(uint(px.x) + 7919u * uint(px.y) + 104729u * uint(frame) + uint(seed));
    return float(h) / 4294967295.0 - 0.5;
}
void main() {
    vec3 e = texture(scene, uv).rgb;
    vec3 c = e + bloom_gain * texture(bloom, uv).rgb;
    c *= 1.0 + 0.25 * kick;                        // strong onsets lift the glow briefly
    c = 1.0 - exp(-c * 1.15);                      // soft knee: glow never clips flat
    vec2 v = uv - 0.5;
    c *= clamp(1.0 - dot(v, v) * 0.6, 0.0, 1.0);   // mild vignette
    c += grain(ivec2(gl_FragCoord.xy)) * 0.03 * (0.15 + c);   // grain rides the light: black stays black
    frag = vec4(clamp(c * gain, 0.0, 1.0), 1.0);
}
"""

class Renderer:
    def __init__(self, W, H, textures=None):
        self.W, self.H = W, H
        self.ctx = moderngl.create_standalone_context(backend="egl")
        self.quad = self.ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
        def target(w, h):
            tx = self.ctx.texture((w, h), 4, dtype="f2")
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tx.repeat_x = tx.repeat_y = False
            return tx, self.ctx.framebuffer([tx])
        self.scene, self.scene_fbo = target(W, H)
        self.bw, self.bh = W // 4, H // 4
        self.b1, self.b1_fbo = target(self.bw, self.bh)
        self.b2, self.b2_fbo = target(self.bw, self.bh)
        self.out = self.ctx.renderbuffer((W, H), 3)
        self.out_fbo = self.ctx.framebuffer([self.out])
        self.down, self.blur, self.post = (self.program(s) for s in (DOWN, BLUR, POST))
        self.scenes = {}
        self.pts = {}                                          # scene -> (prog, vao) or None
        self.tex = {}
        for name, img in (textures or {}).items():             # 8-bit gray, top row first
            h, w = img.shape
            tx = self.ctx.texture((w, h), 1, np.ascontiguousarray(img[::-1]).tobytes())
            tx.filter = (moderngl.LINEAR, moderngl.LINEAR)
            self.tex[name] = tx
        self.vbo_rah = self.vbo_attr = self.vbo_key = None
    def program(self, frag):
        prog = self.ctx.program(vertex_shader=VERT, fragment_shader=frag)
        return prog, self.ctx.vertex_array(prog, [(self.quad, "2f", "pos")])
    def scene_prog(self, name):
        if name not in self.scenes:
            path = os.path.join(HERE, "fx", name + ".glsl")
            src = open(path).read() if os.path.exists(path) else FALLBACK
            self.scenes[name] = self.program(HEAD + src)
        return self.scenes[name]
    def load_points(self, rah, attr):
        self.n_pts = len(rah)
        self.vbo_rah = self.ctx.buffer(rah.tobytes())
        self.vbo_attr = self.ctx.buffer(attr.tobytes())
        self.vbo_key = self.ctx.buffer(reserve=4 * self.n_pts)
    def points_prog(self, name):
        if name not in self.pts:
            path = os.path.join(HERE, "fx", name + ".pts.glsl")
            if not os.path.exists(path) or self.vbo_rah is None:
                self.pts[name] = None
            else:
                prog = self.ctx.program(vertex_shader=PTS_HEAD + open(path).read(), fragment_shader=PTS_FRAG)
                binds = [(self.vbo_rah, "3f", "rah"), (self.vbo_attr, "4f", "attr"), (self.vbo_key, "1f", "key")]
                vao = self.ctx.vertex_array(prog, [b for b in binds if b[2] in prog])   # unused ones are optimised out
                self.pts[name] = (prog, vao)
        return self.pts[name]
    @staticmethod
    def set(prog, uniforms):
        for k, v in uniforms.items():
            if k in prog:
                if isinstance(v, bytes):                       # a matrix, GL column-major
                    prog[k].write(v)
                elif isinstance(v, np.ndarray):
                    buf = np.zeros(prog[k].array_length * prog[k].dimension, "f4")
                    buf[:v.size] = v.ravel()
                    prog[k].write(buf.tobytes())
                else:
                    prog[k].value = v
    def frame(self, name, u, frame_no, gain=1.0, bloom_gain=0.9, key=None):
        """key: this scene's per-point schedule (float32, one per point), or None."""
        prog, vao = self.scene_prog(name)
        self.set(prog, dict(u, res=(self.W, self.H), seed=SEED))
        for unit, (k, tx) in enumerate(self.tex.items(), start=1):
            if k in prog:
                tx.use(unit); prog[k].value = unit
                if k + "_size" in prog:
                    prog[k + "_size"].value = tx.size
        self.scene_fbo.use(); vao.render(moderngl.TRIANGLE_STRIP)
        pts = self.points_prog(name)
        if pts:
            if key is not None:
                self.vbo_key.write(key.tobytes())
            prog, vao = pts
            self.set(prog, dict(u, res=(self.W, self.H), seed=SEED,
                                point_px=2.4 * self.H / 480, cam_dist=CAM_DIST))
            self.ctx.enable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            self.ctx.blend_func = moderngl.ONE, moderngl.ONE
            vao.render(moderngl.POINTS)
            self.ctx.disable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
        # bloom
        p, v = self.down
        self.scene.use(0); p["src"].value = 0
        self.b1_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        p, v = self.blur
        p["src"].value = 0
        for _ in range(2):
            self.b1.use(0); p["dir"].value = (1 / self.bw, 0)
            self.b2_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
            self.b2.use(0); p["dir"].value = (0, 1 / self.bh)
            self.b1_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        # post
        p, v = self.post
        self.scene.use(0); self.b1.use(1)
        p["scene"].value, p["bloom"].value = 0, 1
        self.set(p, {"res": (self.W, self.H), "kick": u.get("kick", 0.0), "gain": gain,
                     "bloom_gain": bloom_gain, "frame": frame_no, "seed": SEED})
        self.out_fbo.use(); v.render(moderngl.TRIANGLE_STRIP)
        return self.out_fbo.read(components=3)                 # bottom row first

def text_image(lines, size, w, h, font=FONT_MONO, spacing=0):
    """White text on black from ffmpeg's drawtext, 8-bit gray, top row first (from
    laser-beam-demo)."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as fh:
        fh.write("\n".join(lines))
    try:
        vf = (f"drawtext=fontfile={font}:textfile={fh.name}:fontsize={size}:fontcolor=white:"
              f"x=(w-text_w)/2:y=(h-text_h)/2:line_spacing={spacing}:expansion=none")
        raw = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"color=c=black:s={w}x{h}",
                              "-frames:v", "1", "-vf", vf, "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True, check=True).stdout
    finally:
        os.unlink(fh.name)
    return np.frombuffer(raw, np.uint8).reshape(h, w)

GLYPHS = "0123456789"             # atlas cells 0-9; cell 10 is blank
GLYPH_W, GLYPH_H, GLYPH_SIZE = 120, 170, 150

def glyph_atlas():
    """The digits in fixed cells (one drawtext call each, so every digit is centred in its
    cell the same way), plus one blank cell."""
    cells = [text_image([ch], GLYPH_SIZE, GLYPH_W, GLYPH_H) for ch in GLYPHS]
    cells.append(np.zeros((GLYPH_H, GLYPH_W), np.uint8))
    return np.hstack(cells)

def ffmpeg_writer(path, W, H, start, dur, audio, crf, preset, song_end):
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-"]
    if audio:
        cmd += ["-ss", f"{start:.6f}", "-t", f"{dur:.6f}", "-i", audio]
    cmd += ["-vf", "vflip,format=yuv420p", "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
            "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709",
            "-color_range", "tv"]
    if audio:
        af = "apad"                                            # silence past the end
        if start + dur >= song_end - 1e-3:                     # the song's cut: no click
            af += f",afade=t=out:st={dur - 0.04:.6f}:d=0.04"
        cmd += ["-af", af, "-c:a", "aac", "-b:a", "320k", "-shortest"]
    cmd += ["-movflags", "+faststart", path]
    return subprocess.Popen(cmd, stdin=subprocess.PIPE)

def save_png(buf, W, H, path):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                    "-s", f"{W}x{H}", "-i", "-", "-vf", "vflip", path], input=buf, check=True)

LAMPS = ("td", "rho", "pm1_s1", "pm1_s2", "dark")
SPINE_N = 90                     # grey sprites in the spine column (the wall)
CAM_DIST, FOV = 3.9, 30.0        # orbit camera: distance (world units), vertical fov (degrees)
BAND = 0.42                      # world height between bands (as in PTS_HEAD)

def perspective(fov, aspect, near=0.1, far=50.0):
    f = 1 / np.tan(np.radians(fov) / 2)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
                     [0, 0, -1, 0]], "f4")

def look_at(eye, target, up):
    f = target - eye; f = f / np.linalg.norm(f)
    r = np.cross(f, up); r = r / np.linalg.norm(r)
    u = np.cross(r, f)
    m = np.eye(4, dtype="f4")
    m[0, :3], m[1, :3], m[2, :3] = r, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m

def orbit(azimuth, elevation, aspect, dist=CAM_DIST, target=(0.0, 0.0, 0.0), shift=0.0, inverse=False):
    """view-projection for a camera circling the tower's axis, as GL column-major bytes
    (with inverse=True, also its inverse). shift moves the picture sideways (in NDC x), so
    the tower can sit left of centre.
    At elevation 90 degrees it looks straight down, with world +z up the screen and +x to
    the right (so a point at angle a sits where the intro drew it)."""
    el = np.radians(min(elevation, 89.9))
    tgt = np.array(target, "f4")
    eye = tgt + dist * np.array([np.cos(el) * np.sin(azimuth), np.sin(el), np.cos(el) * np.cos(azimuth)], "f4")
    up = np.array([-np.sin(azimuth), 0.0, -np.cos(azimuth)], "f4") if elevation >= 89.9 else np.array([0, 1, 0], "f4")
    sh = np.eye(4, dtype="f4"); sh[0, 3] = shift
    vp = (sh @ perspective(FOV, aspect) @ look_at(eye, tgt, up)).astype("f8")
    b = vp.T.astype("f4").tobytes()
    return (b, np.linalg.inv(vp).T.astype("f4").tobytes()) if inverse else b

def tower_arrays(tower):
    """Per-vertex arrays for the point pass: every tower point, then the spine column."""
    rah, attr = [], []
    for s in tower["sizes"]:
        P = s["points"]
        for i in range(len(P["p"])):
            r2 = P["s2_ratio"][i]
            rah.append((P["radius"][i], P["angle"][i], s["n"]))
            attr.append((LAMPS.index(P["lamp"][i]), LAMPS.index(P["lamp_100"][i]),
                         -1.0 if r2 is None else r2, 0.0 if P["half"][i] == "A" else 1.0))
    for k in range(SPINE_N):
        rah.append((0.0, 0.0, 66.0 + 36.0 * k / (SPINE_N - 1)))
        attr.append((5, 5, -1.0, 0.0))
    return np.array(rah, "f4"), np.array(attr, "f4")

def ray_point(tower):
    """The intro's number: (p, theta, screen angle) of the first RAY_SIZE-bit point lit RAY_LAMP."""
    s = next(x for x in tower["sizes"] if x["n"] == RAY_SIZE)["points"]
    i = s["lamp"].index(RAY_LAMP)
    return s["p"][i], s["theta"][i], s["angle"][i]

class Film:
    def __init__(self, W, H, scene=None):
        self.sync = Sync()
        self.scene = scene
        tower = json.load(open(TOWER))
        caption = text_image(["fitted c = 1.41"], 44, 520, 64)
        self.arm_counts = {}
        cells = []
        for name, (n, cue, plong, pshort) in ARMS.items():
            P = next(x for x in tower["sizes"] if x["n"] == n)["points"]
            cl, cs = P["lamp_100"].count("pm1_s2"), P["lamp"].count("pm1_s2")
            self.arm_counts[name] = (cl, cs)
            print(f"{name}: {n}-bit, stage-2 points lit {cl} (100x) / {cs} (10x), "
                  f"cost {plong:+.1f}% / {pshort:+.1f}%", file=sys.stderr)
            for txt in (f"{plong:+.1f}%", f"{pshort:+.1f}%".replace("-", "\u2212"), f"{cl}", f"{cs}",
                        "100\u00d7 B1", "10\u00d7 B1", f"{n}-bit", "qs"):
                cells.append(text_image([txt], LABEL_SIZE, LABEL_W, LABEL_H))
        ecm_cells = [text_image([ECM_TEXT], 40, RHO_TEXT_W, RHO_TEXT_H)]
        rho_cells = [text_image([x], 64 if i == 0 else 40, RHO_TEXT_W, RHO_TEXT_H) for i, x in enumerate(RHO_TEXT)]
        self.r = Renderer(W, H, {"glyphs": glyph_atlas(), "caption": caption, "labels": np.vstack(cells),
                                 "rho_text": np.vstack(rho_cells), "ecm_text": ecm_cells[0]})
        ecm = json.load(open(ECM))
        off = [x["n"] for x in tower["sizes"]].index(ecm["size"]) * tower["per_size"]
        self.ecm_hits = [np.array(c["hits"], int) + off for c in ecm["curves"]]
        tr = tower["rho_check"]["trace"]
        self.rho_trace = (tr["mu"], tr["lambda"], tr["detect_f"])
        p, theta, angle = ray_point(tower)
        print(f"ray: {RAY_SIZE}-bit point p = {p}, theta {theta:.4f}, angle {angle:.4f} rad",
              file=sys.stderr)
        self.consts = {"ray_angle": angle, "r_rim": R_RIM, "r_spine": R_SPINE}
        self.ray_theta = theta
        P72 = next(x for x in tower["sizes"] if x["n"] == RAY_SIZE)["points"]
        self.ray_index = [x["n"] for x in tower["sizes"]].index(RAY_SIZE) * tower["per_size"] + P72["lamp"].index(RAY_LAMP)
        self.rah, self.attr = tower_arrays(tower)
        self.r.load_points(self.rah, self.attr)
        self.aspect = W / H
        self.keys = {}                                         # section name -> key array
        self.flap_init(tower)

    def key(self, s):
        """The per-point schedule of section s (cached), from its scene's schedule function."""
        if s["name"] not in self.keys:
            fn = getattr(self, "key_" + s["scene"], None)
            self.keys[s["name"]] = None if fn is None else fn(s).astype("f4")
        return self.keys[s["name"]]

    def key_assemble(self, s):
        """Verse 1: landing time (s from the section start) of each point. The 72, 84 and 96
        bands land in turn, ASSEMBLE_RINGS rings each, one ring per beat; within a band the
        rings go by radius, rim first, with a small stagger by angle so each ring ripples
        round. The spine column is there from the start."""
        beats = [b for b in self.sync.beat_t if s["start"] <= b < s["end"]]
        key = np.zeros(len(self.rah), "f4")
        for k, n in enumerate((72, 84, 96)):
            idx = np.nonzero(self.rah[:, 2] == n)[0]
            idx = idx[np.argsort(-self.rah[idx, 0], kind="stable")]
            for j, ring in enumerate(np.array_split(idx, ASSEMBLE_RINGS)):
                b = beats[min(k * ASSEMBLE_RINGS + j, len(beats) - 1)]
                key[ring] = b - s["start"] + 0.12 * self.rah[ring, 1] / (2 * np.pi)
        key[self.attr[:, 0] == 5] = -1.0
        return key

    def camera_assemble(self, s, u):
        """Starts straight down, as the intro left the ray, then tilts to 24 degrees over the
        first ASSEMBLE_TILT seconds while orbiting at a speed that follows the loudness."""
        x = min(1.0, u["ts"] / ASSEMBLE_TILT)
        x = x * x * (3 - 2 * x)
        el = 90.0 + (24.0 - 90.0) * x
        az = 0.10 * (u["travel"] - self.sync.at(self.sync.travel, s["start"]))
        # first frame: the 72-bit rim (theta = 8/72) projects at the intro's R_RIM
        rim = 2 * (0.5 - 8 / 72)
        d0 = rim / (R_RIM * np.tan(np.radians(FOV) / 2)) - BAND
        return orbit(az, el, self.aspect, dist=d0 + (CAM_DIST - d0) * x, target=(0.0, -0.06 * x, 0.0))

    def flap_init(self, tower):
        """Verse 2's data. Dots: the tower's measured p-1 stage-1 hit rate (B1-powersmooth)
        in bins of u = ln p / ln B1, all three sizes pooled. Curve: Dickman rho(u - ln c /
        ln B1) with ln B1 averaged over the points; c = 3.4 is the model input, 1.41 the
        fitted value in NOTES ("Real-prime measurement run"). This tower alone fits
        c = 1.46 (95% 1.29-1.65), so the settled curve lies on the dots."""
        h = 1e-3
        self.rho_u = np.arange(0, 8, h)
        rho = np.ones_like(self.rho_u)
        k = int(round(1 / h))
        for i in range(k, len(rho)):                           # rho'(u) = -rho(u - 1) / u
            rho[i] = rho[i - 1] - h * rho[i - k] / self.rho_u[i]
        self.rho = rho
        ps, s1, lnb = [], [], []
        for sz in tower["sizes"]:
            P = sz["points"]
            ps += P["p"]; s1 += P["s1"]; lnb += [np.log(sz["B1"])] * len(P["p"])
        ps, s1, lnb = np.array(ps, float), np.array(s1, float), np.array(lnb)
        u = np.log(ps) / lnb
        self.lnb = float(lnb.mean())
        edges = np.arange(FLAP_U[0], FLAP_U[1] + 1e-9, 0.25)
        dx, dy = [], []
        for a, b in zip(edges, edges[1:]):
            m = (u >= a) & (u < b)
            if m.sum() >= 30:
                dx.append(0.5 * (a + b)); dy.append(s1[m].mean())
        self.dots_x, self.dots_y = np.array(dx, "f4"), np.array(dy, "f4")
        print(f"flap: {len(dx)} dots, u {dx[0]:.3f}..{dx[-1]:.3f}", file=sys.stderr)
        # the two flap cards: (time, target digit) events; cards cycle forward like real ones
        c = self.sync.cues
        self.flips = [self.flip_path([(c["three_point_four"], 3), (c["one_point_four"], 1)]),
                      self.flip_path([(c["three_point_four"] + 0.05, 4)])]

    @staticmethod
    def flip_path(events):
        """[(start time, from, to)] for one card, from blank, cycling forward 0-9."""
        flips, cur = [], 10
        for t0, target in events:
            k = 0
            while cur != target:
                nxt = 0 if cur == 10 else (cur + 1) % 10
                flips.append((t0 + k * FLIP_DUR, cur, nxt)); cur = nxt; k += 1
        return flips

    @staticmethod
    def flap_state(flips, t):
        a = b = 10; f = 0.0
        for t0, x, y in flips:
            if t < t0:
                break
            a, b, f = x, y, min(1.0, (t - t0) / FLIP_DUR)
        return (b, b, 0.0) if f >= 1.0 else (a, b, f)

    def uniforms_flap(self, s, u):
        t = u["t"]
        cues = self.sync.cues
        st = [self.flap_state(fl, t) for fl in self.flips]
        # c: 3.4 until "one-point-four", then a damped spring in log c down to 1.41
        lc0, lc1 = np.log(FLAP_C[0]), np.log(FLAP_C[1])
        tau = t - cues["one_point_four"]
        if tau < 0:
            lc = lc0
        else:
            w = 2 * np.pi / FLAP_SPRING[1]; z = FLAP_SPRING[0]
            lc = lc1 + (lc0 - lc1) * np.exp(-z * w * tau) * np.cos(w * np.sqrt(1 - z * z) * tau)
        xs = np.linspace(FLAP_U[0], FLAP_U[1], FLAP_SAMPLES)
        ys = np.interp(xs - lc / self.lnb, self.rho_u, self.rho, left=1.0)
        on = np.clip((t - cues["three_point_four"]) / 0.6, 0, 1)
        # dots: one per half beat from the section start (the "ah" fill)
        half = np.sort(np.r_[self.sync.beat_t, 0.5 * (self.sync.beat_t[1:] + self.sync.beat_t[:-1])])
        half = half[half >= s["start"]][:len(self.dots_x)]
        da = np.clip((t - half) / 0.12, 0, 1)
        cap = np.clip((tau - FLAP_CAPTION) / 0.5, 0, 1) if tau > 0 else 0.0
        return {"flap_a": tuple(float(x[0]) for x in st), "flap_b": tuple(float(x[1]) for x in st),
                "flap_f": tuple(float(x[2]) for x in st),
                "curve_y": ys.astype("f4"), "curve_on": float(on), "curve_c": float(np.exp(lc)),
                "dots_x": self.dots_x, "dots_y": self.dots_y, "dots_a": da.astype("f4"),
                "n_dots": len(self.dots_x), "u_range": FLAP_U, "caption_a": float(cap)}

    def uniforms_quartet(self, s, u):
        """The pre-chorus cues: static from "No warmer" to the end of "colder" (with 60 ms
        edges), and one white flash on "yes"."""
        k = "1" if s["name"] == "prechorus1" else "2"
        t = u["t"]
        c = self.sync.cues
        on, off, yes = c[f"static{k}_on"], c[f"static{k}_off"], c[f"yes{k}"]
        st = float(np.clip((t - on) / 0.06, 0, 1) * np.clip((off - t) / 0.06, 0, 1))
        fl = float(np.exp(-(t - yes) / QUARTET_FLASH)) if t >= yes else 0.0
        return {"static_a": st, "flash": fl, "palette": 0.0 if k == "1" else 1.0}

    def uniforms_arms(self, s, u):
        """Choruses: light against bill. The long arm (stage 2 to 100 B1) sweeps out from the
        B1 ray, lighting its stage-2 points as it passes each one's prime q, while its cost bar
        climbs past the qs line and turns red; "forty-three" shows its +%. Then those points
        dim, and the short arm (10 B1) sweeps and relights its own, fewer, at full strength,
        its bar settling under the line. On "light the wedge" the long arm's extra points grey
        out a little (paid for, not worth it); the short wedge keeps scanning once per bar."""
        n, cue, plong, pshort = ARMS[s["name"] if s["name"] in ARMS else "chorus1"]
        t, c43 = u["t"], self.sync.cues[cue]
        b1 = {72: 9.0, 84: 9.0, 96: 10.0}[n]
        e0, eL, eS = 1 + b1, 1 + b1 + np.log2(100), 1 + b1 + np.log2(10)   # arm edges, in bits
        ease = lambda x: float(np.clip(x, 0, 1) ** 2 * (3 - 2 * np.clip(x, 0, 1)))
        xl = (t - c43 - ARM_LONG[0]) / (ARM_LONG[1] - ARM_LONG[0])
        xs = (t - c43 - ARM_SHORT[0]) / (ARM_SHORT[1] - ARM_SHORT[0])
        al, as_ = ease(xl), ease(xs)
        scan = -1.0
        if xs >= 1:
            b0 = self.sync.beat(c43 + ARM_SHORT[1])[0]
            scan = e0 + (eS - e0) * ((u["beat"] - b0) / 4.0 % 1.0)
        return {"band_n": float(n), "band_y": (n - 84) / 12 * BAND, "b1_bits": b1, "half_bits": n / 2,
                "arm_e0": e0, "arm_long": e0 + (eL - e0) * al if xl > 0 else 0.0,
                "arm_short": e0 + (eS - e0) * as_ if xs > 0 else 0.0,
                "long_dim": ease((t - c43 - ARM_SHORT[0]) / 0.4),
                "grey": ease((t - c43 - ARM_GREY) / 0.6), "scan": scan,
                "bar_long": (1 + plong / 100) * al, "bar_short": (1 + pshort / 100) * as_,
                "lab_long": ease((t - c43) / 0.15), "lab_short": ease((xs - 1) * (ARM_SHORT[1] - ARM_SHORT[0]) / 0.15),
                "bars_on": ease(xl * 4), "label_base": float(list(ARMS).index(s["name"]) * 8) if s["name"] in ARMS else 0.0}

    def camera_arms(self, s, u):
        """One band, seen from 40 degrees, the wedge turned toward the camera at an angle; a
        slow sway (not a full orbit) keeps the wedge readable. The tower sits left of centre,
        the bars on the right."""
        n = u["band_n"]
        a = 2 * np.pi * (u["arm_e0"] + 3.3) / (n / 2)          # the wedge's middle
        az0 = np.arctan2(np.cos(a), -np.sin(a)) + 0.55
        az = az0 + 0.35 * np.sin(0.07 * (u["travel"] - self.sync.at(self.sync.travel, s["start"])))
        return orbit(az, ARM_EL, self.aspect, dist=ARM_DIST, target=(0.0, u["band_y"], 0.0),
                     shift=ARM_SHIFT, inverse=True)

    def uniforms_rho(self, s, u):
        """Verse 3: the stored Brent run (data/tower.json rho_check.trace) as footsteps on its
        rho: a tail of mu steps into a loop of lambda. Brent's detector works in blocks of
        r = 1, 2, 4, ...: the saved point (the tortoise) jumps to the walker at step 2r - 2;
        the next r steps are not compared, the r after are, with a gcd every 64. Each block
        gets an equal slice of time, so the pace doubles block by block; the last block ends
        on the gcd that detects (step 510 for this run), timed to "meeting" (1:43.64). The
        loop first closes at step mu + lambda (279): the meeting point the walk overshoots."""
        mu, lam, det = self.rho_trace
        t0, t1 = s["start"], self.sync.cues["meeting"]
        kd = int(np.log2((det + 2) // 4))                     # the detecting block: r = 2^kd ends at 4r - 2
        d = (t1 - t0) / (kd + 1)
        k = int(np.clip((u["t"] - t0) // d, 0, kd))
        r = 2 ** k
        x = np.clip((u["t"] - t0 - k * d) / d, 0, 1)
        cur = (2 * r - 2) + 2 * r * x if u["t"] < t1 else float(det)
        tf = u["t"] - t1
        return {"mu": float(mu), "lam": float(lam), "cur": float(cur), "blk_r": float(r),
                "tort": float(2 * r - 2), "det": float(det),
                "flash": float(np.exp(-tf / 0.15)) if tf >= 0 else 0.0,
                "after": float(max(tf, 0.0)) if tf >= 0 else -1.0,
                "cap_a": float(np.clip((tf - RHO_CAPTION) / 0.5, 0, 1)) if tf >= 0 else 0.0,
                "r_cell": float(2 + k)}

    def uniforms_ecm(self, s, u):
        """Verse 4: the price ticker counts up (ease-out) to 8,187 on "eight thousand"; the
        floodlight washes in on "but not tonight" (the line after "re-roll on the way")."""
        t, c = u["t"], self.sync.cues
        t0, t1 = s["start"] + ECM_COUNT_FROM, c["eight_thousand"]
        x = float(np.clip((t - t0) / (t1 - t0), 0, 1))
        v = int(round(ECM_PRICE * (1 - (1 - x) ** 2)))          # ease-out: the last digits settle on the cue
        digits = [10] * 4
        for k, ch in enumerate(reversed(str(v))):
            digits[k] = int(ch)
        flood = float(np.clip((t - c["not_tonight"]) / ECM_FLOOD, 0, 1))
        return {"band_n": 96.0, "band_y": (96 - 84) / 12 * BAND, "ticker": tuple(float(d) for d in digits),
                "ticker_on": float(np.clip((t - t0) / 0.2, 0, 1)), "landed": float(x >= 1),
                "since_land": float(t - t1), "flood": flood}

    def keyframe_ecm(self, s, u):
        """Each beat of verse 4 rolls the next curve of data/ecm.json: key = 1 for the dark
        points it finds."""
        b0 = int(np.searchsorted(self.sync.beat_t, s["start"] - 1e-6))
        k = max(0, int(np.floor(u["beat"])) - b0) % len(self.ecm_hits)
        key = np.zeros(len(self.rah), "f4")
        key[self.ecm_hits[k]] = 1.0
        return key

    def camera_ecm(self, s, u):
        az = 0.9 + 0.35 * np.sin(0.07 * (u["travel"] - self.sync.at(self.sync.travel, s["start"])))
        return orbit(az, ARM_EL + 6, self.aspect, dist=ARM_DIST, target=(0.0, u["band_y"], 0.0),
                     shift=ARM_SHIFT, inverse=True)

    def key_bridge(self, s):
        """Bridge: the time (s from the section start) each point lights; -1 never (dark
        points: the hard ones, left to qs, stay grey). Half A lights rim first from "a
        thousand rays"; half B from "the other half", fast. The ray's own number lights when
        the spark lands."""
        c = self.sync.cues
        key = np.full(len(self.rah), -1.0, "f4")
        lit = self.attr[:, 0] < 3.5
        for half, (t0, t1) in enumerate(((c["thousand_rays"] + 0.3, c["thousand_rays"] + BRIDGE_A_END),
                                         (c["half_b"], c["half_b"] + BRIDGE_B_DUR))):
            idx = np.nonzero(lit & (self.attr[:, 3] == half))[0]
            idx = idx[np.argsort(-self.rah[idx, 0], kind="stable")]
            key[idx] = np.linspace(t0, t1, len(idx)) - s["start"]
        key[self.ray_index] = c["thousand_rays"] - s["start"]
        return key

    def camera_bridge(self, s, u):
        az = 0.6 + 0.10 * (u["travel"] - self.sync.at(self.sync.travel, s["start"]))
        return orbit(az, BRIDGE_EL, self.aspect, dist=BRIDGE_DIST, target=(0.0, -0.04, 0.0), shift=BRIDGE_SHIFT)

    def uniforms_bridge(self, s, u):
        """Left: the ray of the intro's number lights from the rim inward from "the rim lights
        first", reaching its factor's radius (theta of p) on "spark"; the spark then arcs to
        that number's point on the tower at right and lands on "a thousand rays"."""
        c, t = self.sync.cues, u["t"]
        n = RAY_SIZE
        f = (self.ray_theta - 8 / n) / (0.5 - 8 / n)            # fraction of the way in
        x = np.clip((t - c["rim_first"]) / (c["spark"] - c["rim_first"]), 0, 1)
        fly = float(np.clip((t - c["spark"] - 0.15) / (c["thousand_rays"] - c["spark"] - 0.15), 0, 1))
        # where the spark lands: the number's point, projected by this frame's camera
        vp = np.frombuffer(self.camera_bridge(s, u), "f4").reshape(4, 4).T
        r, a, h = self.rah[self.ray_index]
        w = np.array([2 * r * np.cos(a), (h - 84) / 12 * BAND, -2 * r * np.sin(a), 1.0])
        cl = vp @ w
        to = (float(cl[0] / cl[3] * self.aspect), float(cl[1] / cl[3]))
        (cx, cy), R = BRIDGE_L
        span = R - R_SPINE * 1.6
        dirv = np.array([np.cos(u["ray_angle"]), np.sin(u["ray_angle"])])
        frm = tuple(float(v) for v in np.array([cx, cy]) + dirv * (R - span * f))
        return {"lit_front": float(f * x), "spark_f": float(f), "since_spark": float(t - c["spark"]),
                "fly": fly, "spark_from": frm, "spark_to": to, "left_c": (cx, cy), "left_r": R,
                "since_a": float(t - c["half_a"]), "since_b": float(t - c["half_b"])}

    def frame(self, fi):
        t = fi / FPS
        s = self.sync.section(t)
        name = self.scene or s["scene"]
        u = dict(self.sync.uniforms(t), **self.consts)
        extra = getattr(self, "uniforms_" + name, None)
        if extra:
            u.update(extra(s, u))
        cam = getattr(self, "camera_" + name, None)
        if cam:
            m = cam(s, u)
            if isinstance(m, tuple):
                u["view_proj"], u["inv_view_proj"] = m
            else:
                u["view_proj"] = m
        kf = getattr(self, "keyframe_" + name, None)
        key = kf(s, u) if kf else self.key(dict(s, scene=name))
        return self.r.frame(name, u, fi, key=key)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out", help="'-' renders stills only")
    ap.add_argument("--audio", default="", help="the song's WAV ('' for a silent clip)")
    ap.add_argument("--start", type=float, default=0.0)
    ap.add_argument("--dur", type=float, default=10.0)
    ap.add_argument("--section", default=None, help="render exactly this section (by name)")
    ap.add_argument("--full", action="store_true", help="the whole film: 0 to the song's end")
    ap.add_argument("--res", type=int, default=1080, choices=(480, 1080, 2160))
    ap.add_argument("--scene", default=None, help="force one scene (else the section map)")
    ap.add_argument("--crf", type=int, default=22, help="22 for previews; 16 for the 4K master")
    ap.add_argument("--preset", default="medium")
    ap.add_argument("--still", action="append", type=float, default=[],
                    help="also save the frame at this time as PNG (repeatable)")
    a = ap.parse_args()

    H = a.res; W = int(round(H * 16 / 9 / 2)) * 2
    film = Film(W, H, a.scene)
    if a.full:
        f0, n = 0, film.sync.n_frames
    elif a.section:
        s = film.sync.by_name[a.section]
        # the section's own frames: the first with t >= start up to the first with t >= end
        f0 = int(np.ceil(s["start"] * FPS - 1e-9)); n = int(np.ceil(s["end"] * FPS - 1e-9)) - f0
    else:
        f0, n = round(a.start * FPS), round(a.dur * FPS)
    stills = {round(t * FPS): t for t in a.still}
    stem = os.path.splitext(a.out)[0] if a.out != "-" else os.path.join(HERE, "renders", "still")
    os.makedirs(os.path.dirname(os.path.abspath(stem)), exist_ok=True)
    print(f"render {W}x{H} @ {FPS} fps: frames {f0}..{f0 + n - 1} ({n} frames, "
          f"{f0 / FPS:.3f}-{(f0 + n) / FPS:.3f} s), scene {a.scene or 'by section'}", file=sys.stderr)
    if a.out == "-":
        for fi, t in sorted(stills.items()):
            save_png(film.frame(fi), W, H, f"{stem}_{t:.2f}s.png")
        return
    proc = ffmpeg_writer(a.out, W, H, f0 / FPS, n / FPS, a.audio, a.crf, a.preset, film.sync.duration)
    for fi in range(f0, f0 + n):
        buf = film.frame(fi)
        proc.stdin.write(buf)
        if fi in stills:
            save_png(buf, W, H, f"{stem}_{stills[fi]:.2f}s.png")
        if (fi - f0) % 300 == 0:
            print(f"frame {fi} / {f0 + n} ({fi / FPS:.1f} s)", file=sys.stderr, flush=True)
    proc.stdin.close()
    sys.exit(proc.wait())

if __name__ == "__main__":
    main()
