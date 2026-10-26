// Verse 4: the 96-bit band, lit as in the data (rho blue, p-1 stage 1 / stage 2 greens), the
// dark points grey. key = 1 on the dark points this beat's curve finds (data/ecm.json, a real
// ECM run mod p per point, B1 = 257, B2 = 12,850): they sparkle and fade over the beat, and
// the next beat rolls a new curve. When the floodlight washes in, the dark points light a
// soft white: qs takes what is left, cheaply.
uniform float band_n, flood;

void main() {
    float lamp = attr.x;
    vec3 w = world(rah);
    if (lamp > 4.5) {
        bool near = abs(rah.z - band_n) < 4.0;
        place(w, 0.85);
        v_col = DARK; v_a = near ? 0.6 * (1.0 - abs(rah.z - band_n) / 4.0) : 0.0;
        return;
    }
    if (abs(rah.z - band_n) > 0.5) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 1.0; v_col = vec3(0.0); v_a = 0.0;
        return;
    }
    vec3 c = lamp < 0.5 ? TD * 1.5 : lamp < 1.5 ? RHO * 1.6 : lamp < 2.5 ? PM1 * 2.0 : lamp < 3.5 ? PM2 * 1.5 : DARK * 0.9;
    if (lamp > 3.5) {
        c = mix(c, WHITE * 0.55, 0.8 * flood);
        if (key > 0.5) c += WHITE * (0.25 + 1.3 * exp(-since_beat / 0.18));
    }
    v_col = c; v_a = 1.0 + 0.3 * kick;
    place(w, lamp > 3.5 && key > 0.5 ? 1.15 + 0.6 * exp(-since_beat / 0.25) : 1.15);
}
