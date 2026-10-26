// Choruses: one band of the tower (band_n bits). td orange, p-1 stage 1 deep green and dark
// grey as in the data; the stage-2 points start grey and light as an arm passes their prime
// q, at 1 + log2(q) bits (q = s2 ratio x B1; drawn on its spoke, bitlen(q)). The long arm's
// points dim when the short arm starts; the short arm relights its own at full strength;
// the long arm's extra points then grey out a little. The scan line flares the short arm's
// points once per bar.
uniform float band_n, b1_bits, arm_long, arm_short, long_dim, grey, scan;

void main() {
    float lamp = attr.x, lamp100 = attr.y, ratio = attr.z;
    vec3 w = world(rah);
    if (lamp > 4.5) {                                  // the spine, near this band only
        bool near = abs(rah.z - band_n) < 4.0;
        place(w, 0.85);
        v_col = DARK; v_a = near ? 0.6 * (1.0 - abs(rah.z - band_n) / 4.0) : 0.0;
        return;
    }
    if (abs(rah.z - band_n) > 0.5) {                   // other bands: not shown
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 1.0; v_col = vec3(0.0); v_a = 0.0;
        return;
    }
    vec3 c = lamp < 0.5 ? TD * 1.5 : lamp > 1.5 && lamp < 2.5 ? PM1 * 2.0 : DARK * 0.9;
    if (lamp100 > 2.5 && lamp100 < 3.5) {              // lit by the long arm (stage 2 to 100 B1)
        float qb = 1.0 + b1_bits + log2(ratio);
        bool short_pt = lamp > 2.5 && lamp < 3.5;      // also lit by the short arm (to 10 B1)
        c = DARK * 0.9;
        if (arm_long >= qb) {
            c = PM2 * 1.6 * (1.0 - 0.5 * long_dim);
            c += WHITE * 0.7 * exp(-(arm_long - qb) / 0.25);
            if (!short_pt) c = mix(c, mix(PM2, DARK, 0.55) * 0.9, grey);
        }
        if (short_pt && arm_short >= qb) {
            c = PM2 * 1.6 + WHITE * 0.7 * exp(-(arm_short - qb) / 0.2);
            if (scan > 0.0) c += PM2 * 0.9 * exp(-pow((scan - qb) / 0.3, 2.0));
        }
    }
    v_col = c; v_a = 1.0 + 0.3 * kick;
    place(w, 1.15);
}
