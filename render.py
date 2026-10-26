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
import argparse, json, os, subprocess, sys
import numpy as np
import moderngl
from sync import Sync, FPS

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 0x10C5                    # the only source of noise; change it to re-roll the grain
TOWER = os.path.join(HERE, "data", "tower.json")
# the one number whose ray the intro draws (and the bridge lights): the first 72-bit point
# that the short arm (p-1 stage 2 at 10 B1) finds
RAY_SIZE, RAY_LAMP = 72, "pm1_s2"
R_RIM, R_SPINE = 0.86, 0.035     # screen radius (P units) of theta = 8/n and of the spine

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
    def __init__(self, W, H):
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
    def program(self, frag):
        prog = self.ctx.program(vertex_shader=VERT, fragment_shader=frag)
        return prog, self.ctx.vertex_array(prog, [(self.quad, "2f", "pos")])
    def scene_prog(self, name):
        if name not in self.scenes:
            path = os.path.join(HERE, "fx", name + ".glsl")
            src = open(path).read() if os.path.exists(path) else FALLBACK
            self.scenes[name] = self.program(HEAD + src)
        return self.scenes[name]
    @staticmethod
    def set(prog, uniforms):
        for k, v in uniforms.items():
            if k in prog:
                if isinstance(v, np.ndarray):
                    buf = np.zeros(prog[k].array_length * prog[k].dimension, "f4")
                    buf[:v.size] = v.ravel()
                    prog[k].write(buf.tobytes())
                else:
                    prog[k].value = v
    def frame(self, name, u, frame_no, gain=1.0, bloom_gain=0.9):
        prog, vao = self.scene_prog(name)
        self.set(prog, dict(u, res=(self.W, self.H), seed=SEED))
        self.scene_fbo.use(); vao.render(moderngl.TRIANGLE_STRIP)
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

def ray_point(tower):
    """The intro's number: (p, theta, screen angle) of the first RAY_SIZE-bit point lit RAY_LAMP."""
    s = next(x for x in tower["sizes"] if x["n"] == RAY_SIZE)["points"]
    i = s["lamp"].index(RAY_LAMP)
    return s["p"][i], s["theta"][i], s["angle"][i]

class Film:
    def __init__(self, W, H, scene=None):
        self.sync = Sync()
        self.scene = scene
        self.r = Renderer(W, H)
        tower = json.load(open(TOWER))
        p, theta, angle = ray_point(tower)
        print(f"ray: {RAY_SIZE}-bit point p = {p}, theta {theta:.4f}, angle {angle:.4f} rad",
              file=sys.stderr)
        self.consts = {"ray_angle": angle, "r_rim": R_RIM, "r_spine": R_SPINE}

    def frame(self, fi):
        t = fi / FPS
        s = self.sync.section(t)
        name = self.scene or s["scene"]
        u = dict(self.sync.uniforms(t), **self.consts)
        return self.r.frame(name, u, fi)

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
        f0, n = round(s["start"] * FPS), round(s["end"] * FPS) - round(s["start"] * FPS)
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
