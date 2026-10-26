// Verse 2: "I said three-point-four ... told me one-point-four".
// Top: a split-flap counter. Each card's top half folds down over the hinge to show the next
// digit, and the cards cycle forward like real ones: blank -> 3.4 on "three-point-four",
// then 3 -> 4 -> ... -> 0 -> 1 on "one-point-four" (render.py flip_path).
// Below: the measured dots (the tower's p-1 stage-1 hit rate by u = ln p / ln B1) and a
// smooth Dickman curve at c = 3.4, above them: the flattering formula. On "one-point-four",
// c springs toward 1.41, overshoots below the dots, then settles onto them.
uniform sampler2D glyphs;
uniform vec2 glyphs_size;
uniform sampler2D caption;
uniform vec2 flap_a, flap_b, flap_f;      // per card: digit before, after, flip progress
uniform float curve_y[96];
uniform float curve_on, curve_c, caption_a;
uniform float dots_x[16], dots_y[16], dots_a[16];
uniform int n_dots;
uniform vec2 u_range;

const int NC = 96;
const float CW = 0.16, CH = 0.23, CY = 0.50;          // card half-size, centre height
const float PX0 = -1.30, PX1 = 1.30, PY0 = -0.88, PY1 = 0.02;   // plot box (P units)

float glyph(float d, vec2 q) {                        // q in [-1, 1]^2 over the card
    if (abs(q.x) > 1.0 || abs(q.y) > 1.0) return 0.0;
    vec2 c = vec2((d + q.x * 0.5 + 0.5) / 11.0, q.y * 0.5 + 0.5);
    return texture(glyphs, c).r;
}

vec3 card(vec2 q, float a, float b, float f) {
    vec3 bg = vec3(0.055);
    float g, shade = 1.0;
    if (q.y >= 0.0) {
        float hy = cos(PI * f);
        if (f < 0.5 && q.y < hy) { g = glyph(a, vec2(q.x, q.y / hy)); shade = 0.55 + 0.45 * hy; }
        else g = glyph(b, q);
    } else {
        float hy = -cos(PI * f);
        if (f >= 0.5 && -q.y < hy) { g = glyph(b, vec2(q.x, q.y / hy)); shade = 0.55 + 0.45 * hy; }
        else g = glyph(a, q);
    }
    vec3 c = (bg + WHITE * 0.92 * g) * shade;
    c *= smoothstep(0.0, 0.035, abs(q.y));            // the hinge gap
    float edge = max(abs(q.x), abs(q.y));
    return c * smoothstep(1.0, 0.97, edge);
}

vec2 plot(float u, float y) {
    return vec2(mix(PX0, PX1, (u - u_range.x) / (u_range.y - u_range.x)), mix(PY0, PY1, y));
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);

    // the counter: card, decimal point, card
    for (int k = 0; k < 2; k++) {
        vec2 cc = vec2(k == 0 ? -0.22 : 0.22, CY);
        vec2 q = (p - cc) / vec2(CW, CH);
        if (abs(q.x) <= 1.0 && abs(q.y) <= 1.0)
            c += card(q, flap_a[k], flap_b[k], flap_f[k]);
    }
    float shown = (flap_b.x < 9.5 || flap_a.x < 9.5) ? 1.0 : 0.0;     // the point appears with the digits
    c += WHITE * 0.9 * shown * smoothstep(0.028, 0.020, length(p - vec2(0.0, CY - CH + 0.03)));

    // caption under the counter
    if (caption_a > 0.0) {
        vec2 cq = (p - vec2(0.0, CY - CH - 0.10)) / vec2(0.40, 0.05);
        if (abs(cq.x) <= 1.0 && abs(cq.y) <= 1.0)
            c += PM2 * 0.8 * caption_a * texture(caption, cq * 0.5 + 0.5).r;
    }

    // axes and ticks at u = 1, 2, 3, 4
    float w = 1.0 * px();
    float ax = abs(p.y - PY0);
    if (p.x > PX0 - 0.02 && p.x < PX1 + 0.02) c += DARK * 0.8 * exp(-ax * ax / (w * w));
    float ay = abs(p.x - PX0);
    if (p.y > PY0 - 0.02 && p.y < PY1 + 0.02) c += DARK * 0.8 * exp(-ay * ay / (w * w));
    for (int k = 1; k <= 4; k++) {
        vec2 tk = plot(float(k), 0.0);
        if (abs(p.x - tk.x) < w * 1.5 && p.y < PY0 && p.y > PY0 - 0.025) c += DARK * 0.9;
        vec2 q = (p - (tk - vec2(0.0, 0.075))) / vec2(0.032, 0.045);
        c += DARK * 1.4 * glyph(float(k), q);
    }

    // the curve, drawn in left to right after "three-point-four"
    if (curve_on > 0.0) {
        float d = 1e3;
        int last = int(curve_on * float(NC - 1));
        for (int k = 0; k < NC - 1; k++) {
            if (k >= last) break;
            float h;
            vec2 a = vec2(mix(PX0, PX1, float(k) / float(NC - 1)), mix(PY0, PY1, curve_y[k]));
            vec2 b = vec2(mix(PX0, PX1, float(k + 1) / float(NC - 1)), mix(PY0, PY1, curve_y[k + 1]));
            d = min(d, seg(p, a, b, h));
        }
        vec3 col = mix(PM2, WHITE, clamp((curve_c - 1.41) / 1.5, 0.0, 1.0));
        c += col * 0.8 * glow(d, 1.4 * px());
    }

    // the measured dots
    for (int k = 0; k < 16; k++) {
        if (k >= n_dots) break;
        vec2 dp = plot(dots_x[k], dots_y[k]);
        float r = length(p - dp);
        c += PM1 * 2.2 * dots_a[k] * (smoothstep(5.0 * px(), 3.5 * px(), r) + 0.3 * exp(-r * r / (64.0 * px() * px())));   // no 1/r tail: it would tint the frame
    }

    frag = vec4(c, 1.0);
}
