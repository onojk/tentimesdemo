// Final chorus: the whole tower (finale.pts.glsl) on black. On "forty-three" the 72-bit cost
// bars of chorus 1 echo for one bar (+42.8% red over the qs line, -6.4% under it, with
// their counts), then fade; no new numbers. Geometry and label cells as in arms.glsl.
uniform float echo, bar_long, bar_short, label_base;
uniform sampler2D labels;

const vec3 RED = vec3(1.00, 0.16, 0.10);
const float BX_L = 1.22, BX_S = 1.52, BW = 0.075;
const float BY0 = -0.55, BSCALE = 0.55;

float label(float i, vec2 q) {
    if (abs(q.x) > 1.0 || abs(q.y) > 1.0) return 0.0;
    return texture(labels, vec2(q.x * 0.5 + 0.5, 1.0 - (label_base + i + 0.5 - 0.5 * q.y) / 16.0)).r;
}
float text(float i, vec2 p, vec2 at, float hh) { return label(i, (p - at) / vec2(hh * 400.0 / 72.0, hh)); }

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    if (echo > 0.0) {
        float lineY = BY0 + BSCALE;
        if (p.x > BX_L - 0.18 && p.x < BX_S + 0.15)
            c += WHITE * 0.5 * step(0.5, fract(p.x * 40.0)) * exp(-pow((p.y - lineY) / (1.2 * px()), 2.0));
        c += DARK * 1.6 * text(7.0, p, vec2(BX_L - 0.25, lineY), 0.03);
        float hl = BSCALE * bar_long, hs = BSCALE * bar_short;
        if (abs(p.x - BX_L) < BW && p.y > BY0 && p.y < BY0 + hl) c += RED * 0.75;
        if (abs(p.x - BX_S) < BW && p.y > BY0 && p.y < BY0 + hs) c += PM2 * 0.85;
        c += RED * 1.4 * text(0.0, p, vec2(BX_L, BY0 + hl + 0.065), 0.042);
        c += PM2 * 1.4 * text(1.0, p, vec2(BX_S, BY0 + hs + 0.105), 0.042);
        c += DARK * 1.8 * text(4.0, p, vec2(BX_L, BY0 - 0.06), 0.026);
        c += DARK * 1.8 * text(5.0, p, vec2(BX_S, BY0 - 0.06), 0.026);
        c += WHITE * 0.6 * text(2.0, p, vec2(BX_L, BY0 - 0.12), 0.03);
        c += PM2 * 0.8 * text(3.0, p, vec2(BX_S, BY0 - 0.12), 0.03);
        c += DARK * 1.6 * text(6.0, p, vec2(0.5 * (BX_L + BX_S), 0.62), 0.036);
        c *= echo;
    }
    frag = vec4(c, 1.0);
}
