// Bridge, right: the whole tower (72 / 84 / 96), every point grey until it lights. key = the
// time (s from the section start) it lights, -1 never: the dark points, the hard ones, stay
// grey with the spine. Half A lights rim first from "a thousand rays", in lamp colours; on
// "half of the numbers chose the road" it pulses once; on "the other half checked it
// through" half B lights fast, each with a white check flare. The intro's number lights
// first, when its spark lands.
uniform float since_a, since_b;

void main() {
    float lamp = attr.x;
    vec3 w = world(rah);
    if (lamp > 4.5) { place(w, 0.85); v_col = DARK; v_a = 0.6; return; }
    vec3 c = DARK * 0.55;
    float age = ts - key;
    if (key >= 0.0 && age >= 0.0) {
        vec3 lc = lamp < 0.5 ? TD * 1.5 : lamp < 1.5 ? RHO * 1.6 : lamp < 2.5 ? PM1 * 2.0 : PM2 * 1.5;
        float rise = smoothstep(0.0, 0.25, age);
        c = mix(c, lc, rise);
        bool half_b = attr.w > 0.5;
        c += (half_b ? WHITE * 1.2 : lc * 0.8) * exp(-age / 0.2);
        if (!half_b && since_a >= 0.0) c += lc * 0.6 * exp(-since_a / 0.6);
    }
    v_col = c; v_a = 1.0 + 0.2 * kick;
    place(w, 1.0);
}
