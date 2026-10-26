// Choruses: light against bill (render.py uniforms_arms has the timeline).
// On the band's plane: the arms as wedges from the B1 ray (stage 1 lies inside it) out to
// each arm's edge, 1 + log2(k B1) bits; points are lit in arms.pts.glsl. On the right: the
// two cost bars against the qs line (the stage-1 pipeline's cost), with their labels and the
// stage-2 point counts small underneath.
uniform mat4 inv_view_proj;
uniform float band_y, half_bits, arm_e0, arm_long, arm_short, long_dim, grey, scan;
uniform float bar_long, bar_short, lab_long, lab_short, bars_on, label_base;
uniform sampler2D labels;
uniform vec2 labels_size;

const vec3 RED = vec3(1.00, 0.16, 0.10);
const float BX_L = 1.12, BX_S = 1.46, BW = 0.085;   // bar centres and half-width (P units)
const float BY0 = -0.60, BSCALE = 0.60;             // bar base; height of the qs line (1.0)

float label(float i, vec2 q) {                      // q in [-1, 1]^2 over the label cell
    if (abs(q.x) > 1.0 || abs(q.y) > 1.0) return 0.0;
    return texture(labels, vec2(q.x * 0.5 + 0.5, 1.0 - (label_base + i + 0.5 - 0.5 * q.y) / 16.0)).r;
}
// a label of half-height hh, left-aligned in its cell's own centring (cells are centred)
float text(float i, vec2 p, vec2 at, float hh) {
    return label(i, (p - at) / vec2(hh * 400.0 / 72.0, hh));
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);

    // the band's plane under this pixel: polar position in the tower's own terms
    vec2 ndc = uv * 2.0 - 1.0;
    vec4 a = inv_view_proj * vec4(ndc, -1.0, 1.0), b = inv_view_proj * vec4(ndc, 1.0, 1.0);
    vec3 ro = a.xyz / a.w, rd = b.xyz / b.w - ro;
    float k = (band_y - ro.y) / rd.y;
    if (k > 0.0) {
        vec3 w = ro + rd * k;
        float r = 0.5 * length(w.xz);                  // data radius (1/2 - theta)
        float ang = atan(-w.z, w.x); if (ang < 0.0) ang += 2.0 * PI;
        float bits = ang / (2.0 * PI) * half_bits;
        float rmax = 0.5 - 8.0 / (2.0 * half_bits);
        float inside = smoothstep(rmax + 0.01, rmax - 0.01, r) * smoothstep(0.0, 0.02, r);
        float wpx = 2.0 * px() * k * 0.5;              // about two pixels, in world units, here
        float rw = max(2.0 * r, 1e-4);
        // edge distance of a ray at `e` bits, in world units
        // (cos > 0: only the ray itself, not its opposite through the centre)
        #define EDGE(e) (cos(ang - 2.0 * PI * (e) / half_bits) > 0.0 ? abs(sin(ang - 2.0 * PI * (e) / half_bits)) * rw : 1e3)
        // long wedge: faint fill, a bright moving edge; dims when the short arm takes over
        if (arm_long > arm_e0) {
            float fill = step(arm_e0, bits) * step(bits, arm_long) * inside;
            float lv = 1.0 - 0.75 * long_dim;
            c += mix(WHITE, DARK, grey) * 0.045 * lv * fill;
            c += WHITE * 0.55 * lv * inside * exp(-pow(EDGE(arm_long) / wpx, 2.0));
        }
        // short wedge: light green fill and edge, stays bright; its scan line once per bar
        if (arm_short > arm_e0) {
            float fill = step(arm_e0, bits) * step(bits, arm_short) * inside;
            c += PM2 * 0.07 * fill;
            c += PM2 * 0.8 * inside * exp(-pow(EDGE(arm_short) / wpx, 2.0));
            if (scan > 0.0) c += PM2 * 0.5 * inside * exp(-pow(EDGE(scan) / (2.0 * wpx), 2.0));
        }
        // the B1 ray: where stage 1 ends and both arms start
        if (arm_long > arm_e0 || arm_short > arm_e0)
            c += DARK * 0.9 * inside * exp(-pow(EDGE(arm_e0) / wpx, 2.0));
    }

    // the bars
    if (bars_on > 0.0) {
        float lineY = BY0 + BSCALE;
        // qs line, dashed
        if (p.x > BX_L - 0.20 && p.x < BX_S + 0.17)
            c += WHITE * 0.5 * bars_on * step(0.5, fract(p.x * 40.0)) * exp(-pow((p.y - lineY) / (1.2 * px()), 2.0));
        c += DARK * 1.6 * bars_on * text(7.0, p, vec2(BX_L - 0.27, lineY), 0.032);
        // long bar: red once it passes the line
        float hl = BSCALE * bar_long;
        if (abs(p.x - BX_L) < BW && p.y > BY0 && p.y < BY0 + hl) {
            vec3 col = bar_long > 1.0 ? RED : mix(WHITE, DARK, 0.3);
            c += col * 0.75 * (1.0 - 0.35 * long_dim);
        }
        float hs = BSCALE * bar_short;
        if (abs(p.x - BX_S) < BW && p.y > BY0 && p.y < BY0 + hs) c += PM2 * 0.85;
        // labels: percentages above the bars, arm names and counts below
        c += RED * 1.4 * lab_long * text(0.0, p, vec2(BX_L, BY0 + hl + 0.07), 0.045);
        c += PM2 * 1.4 * lab_short * text(1.0, p, vec2(BX_S, BY0 + hs + 0.115), 0.045);
        c += DARK * 1.8 * bars_on * text(4.0, p, vec2(BX_L, BY0 - 0.06), 0.028);
        c += DARK * 1.8 * bars_on * text(5.0, p, vec2(BX_S, BY0 - 0.06), 0.028);
        c += WHITE * 0.6 * step(0.001, bar_long) * bars_on * text(2.0, p, vec2(BX_L, BY0 - 0.13), 0.033);
        c += PM2 * 0.8 * step(0.001, bar_short) * text(3.0, p, vec2(BX_S, BY0 - 0.13), 0.033);
        c += DARK * 1.6 * bars_on * text(6.0, p, vec2(0.5 * (BX_L + BX_S), 0.82), 0.04);
    }
    frag = vec4(c, 1.0);
}
