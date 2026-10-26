// Pre-choruses: "No warmer, no colder, / just no until it's yes."
// Four vertical beams of light, one per voice (bass, baritone, lead, tenor, left to right),
// each one's brightness and width from its band (sync.py: normalised within the
// pre-choruses). Pre-chorus 1 is white; pre-chorus 2 takes the tower's lamp colours (td, rho,
// p-1 s1, p-1 s2). On "no warmer, no colder" a grey static covers the frame (no reading
// either way); on "yes" one white flash, the only one in the section.
uniform float static_a;           // 0..1, the static's strength
uniform float flash;              // 0..1, the "yes" flash (decaying)
uniform float palette;            // 0 white beams, 1 tower colours

const float BX[4] = float[4](-0.84, -0.28, 0.28, 0.84);

vec3 voice_col(int i) {
    vec3 tower = i == 0 ? TD : i == 1 ? RHO : i == 2 ? PM1 * 1.6 : PM2;
    return mix(WHITE * 0.95, tower, palette);
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    for (int i = 0; i < 4; i++) {
        float q = quartet[i];
        float w = (0.018 + 0.05 * q);                       // beam half-width, P units
        float dx = p.x - BX[i];
        float core = exp(-dx * dx / (w * w));
        float halo = exp(-dx * dx / (16.0 * w * w));
        float fall = smoothstep(-1.05, 0.2, p.y) * (0.75 + 0.25 * smoothstep(1.0, -0.6, p.y));
        vec3 col = voice_col(i);
        c += col * (0.12 + 1.1 * q) * (core + 0.25 * halo) * fall;
        // where the beam meets the floor
        vec2 f = (p - vec2(BX[i], -0.92)) / vec2(4.0 * w, 0.03);
        c += col * (0.1 + 0.6 * q) * exp(-dot(f, f));
    }
    // the static: grey, re-rolled every frame, in 2 px cells
    if (static_a > 0.0) {
        vec2 cell = floor(gl_FragCoord.xy / 2.0);
        float fr = floor(t * 30.0 + 0.5);
        float n = float(hash(uint(cell.x) + 7919u * uint(cell.y) + 104729u * uint(fr) + uint(seed))) / 4294967295.0;
        c = mix(c, DARK * (0.4 + 1.6 * n), 0.85 * static_a);
    }
    c += WHITE * 3.0 * flash;
    frag = vec4(c, 1.0);
}
