// Verse 4: "The curves came in at a price tag ... eight thousand for a single roll against the
// floodlight's speed ... the wall is cheap today."
// Right: the price ticker, counting up to 8,187 (ruint per ECM curve at B1 = 257, NOTES
// I-017), landing on "eight thousand". On the band's plane: the floodlight, a broad soft
// wash over the whole disc from "but not tonight" (qs, the wall, lights what is left,
// cheaply). The speckle itself is in ecm.pts.glsl.
uniform mat4 inv_view_proj;
uniform float band_y, flood, ticker_on, landed, since_land;
uniform vec4 ticker;                       // digits, ones first; 10 = blank
uniform sampler2D glyphs, ecm_text;

const vec2 TK = vec2(1.22, 0.50);          // ticker centre
const vec2 DG = vec2(0.065, 0.092);        // digit half-size
const float ADV = 0.125;                   // digit advance

float glyph(float d, vec2 q) {
    if (abs(q.x) > 1.0 || abs(q.y) > 1.0) return 0.0;
    return texture(glyphs, vec2((d + q.x * 0.5 + 0.5) / 11.0, q.y * 0.5 + 0.5)).r;
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);

    // floodlight on the band's disc
    if (flood > 0.0) {
        vec2 ndc = uv * 2.0 - 1.0;
        vec4 a = inv_view_proj * vec4(ndc, -1.0, 1.0), b = inv_view_proj * vec4(ndc, 1.0, 1.0);
        vec3 ro = a.xyz / a.w, rd = b.xyz / b.w - ro;
        float k = (band_y - ro.y) / rd.y;
        if (k > 0.0) {
            float r = 0.5 * length((ro + rd * k).xz);
            float rmax = 0.5 - 8.0 / 96.0;
            c += WHITE * 0.07 * flood * smoothstep(rmax + 0.04, rmax * 0.2, r);
        }
    }

    // the ticker: d3 , d2 d1 d0
    if (ticker_on > 0.0) {
        float lift = 1.0 + 0.6 * landed * exp(-since_land / 0.3);
        vec3 col = WHITE * 0.9 * ticker_on * lift;
        // slots, right to left: d0 d1 d2, the comma (half a slot), d3
        float x0 = TK.x + 1.6 * ADV;
        float xs[4] = float[4](x0, x0 - ADV, x0 - 2.0 * ADV, x0 - 3.5 * ADV);
        for (int i = 0; i < 4; i++) c += col * glyph(ticker[i], (p - vec2(xs[i], TK.y)) / DG);
        if (ticker[3] < 9.5) {                 // the thousands comma: a dot and a short tail
            vec2 cp = vec2(x0 - 2.75 * ADV, TK.y - 0.70 * DG.y);
            float h;
            float d = min(length(p - cp) - 0.011, seg(p, cp, cp + vec2(-0.012, -0.030), h) - 0.0045);
            c += col * smoothstep(px(), 0.0, d);
        }
        vec2 cq = (p - vec2(TK.x, TK.y - 0.17)) / vec2(0.032 * 1400.0 / 96.0, 0.032);
        if (abs(cq.x) <= 1.0 && abs(cq.y) <= 1.0)
            c += DARK * 1.6 * ticker_on * texture(ecm_text, cq * 0.5 + 0.5).r;
    }
    frag = vec4(c, 1.0);
}
