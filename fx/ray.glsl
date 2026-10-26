// Intro: one number's line. Black; a single thin ray at one real point's angle grows from
// the rim (theta = 8/n, the smallest factors) toward the centre (theta = 1/2), one step per
// clock tick, so the picture ticks exactly when the sound does. Each tick lands with a
// bright tip and leaves a faint graduation behind. The spine at the centre is a dim grey
// dot from the start: the ray stops just short of it.
uniform float ray_angle, r_rim, r_spine;

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    vec2 dir = vec2(cos(ray_angle), sin(ray_angle));
    vec2 rim = dir * r_rim;
    float span = r_rim - r_spine * 1.6;               // the ray ends a little outside the spine

    // length in ticks: each tick snaps forward over 80 ms
    float steps = 0.0;
    if (n_tick > 0) steps = float(n_tick - 1) + smoothstep(0.0, 0.08, since_tick);
    float frac = clamp(steps / float(max(ticks_total, 1)), 0.0, 1.0);
    vec2 tip = rim - dir * span * frac;

    // the ray: a thin core with a soft halo
    float h;
    float d = seg(p, rim, tip, h);
    if (frac > 0.0) {
        float w = 1.1 * px();
        c += WHITE * 0.55 * glow(d, w) * (0.6 + 0.4 * h);   // brighter toward the moving tip
        // graduations: one tiny cross-tick per clock tick already struck
        for (int k = 1; k < 64; k++) {
            if (k >= n_tick) break;
            float fk = float(k) / float(max(ticks_total, 1));
            vec2 q = rim - dir * span * fk;
            float g = length(p - q);
            c += WHITE * 0.25 * exp(-g * g / (2.5 * px() * 2.5 * px()));
        }
        // the tip flashes on each tick and decays
        float pulse = exp(-since_tick / 0.12);
        float dt = length(p - tip);
        c += WHITE * (0.35 + 1.4 * pulse) * glow(dt, 2.2 * px());
    }

    // the spine: always grey, the wall
    float ds = length(p);
    c += DARK * 0.9 * smoothstep(r_spine, r_spine * 0.6, ds);
    c += DARK * 0.15 * glow(ds - r_spine, 1.5 * px());

    frag = vec4(c, 1.0);
}
