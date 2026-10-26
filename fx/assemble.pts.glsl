// Verse 1: the tower assembles. key = this point's landing time (s from the section start;
// render.py key_assemble): the 72, 84 and 96 bands land in turn, one ring per beat, rim
// first. A point drops in from above over FALL seconds, flashes white as it lands and
// settles to grey; trial division's points (the rim) then light orange. Nothing else lights
// yet. The spine column is grey throughout: the wall.
const float FALL = 0.45;

void main() {
    float lamp = attr.x;
    vec3 w = world(rah);
    if (lamp > 4.5) {                                  // the spine
        place(w, 0.85);
        v_col = DARK; v_a = 0.6;
        return;
    }
    float age = ts - key;                              // seconds since landing
    if (age < -FALL) {                                 // not yet in the air: off screen
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0); gl_PointSize = 1.0;
        v_col = vec3(0.0); v_a = 0.0;
        return;
    }
    float fall = clamp(-age / FALL, 0.0, 1.0);         // 1 when it appears, 0 on landing
    w.y += 0.7 * fall * fall;
    float land = age >= 0.0 ? exp(-age / 0.15) : 0.0;
    vec3 c = DARK * 0.9;
    if (lamp < 0.5) c = mix(c, TD * 1.5, smoothstep(0.2, 0.6, age));
    v_col = c + WHITE * 0.4 * land;
    v_a = (1.0 - fall) * (1.0 + 0.3 * kick);
    place(w, 1.0);
}
