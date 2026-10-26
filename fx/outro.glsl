// Outro (spoken, over clock ticks): "Twelve percent on the plain arm. / Sealed before the run."
// The two lines type out word by word on the spoken words (render.py uniforms_outro) and
// complete as "run" ends. Above them a clock: its hand steps one notch on every detected
// tick, so picture and sound tick together, and stops on the last tick (3:49.70); the
// picture holds until the music's cut (3:50.87), then black through the silent tail.
uniform int len0, len1, shown0, shown1;
uniform float adv_px, typing, stopped, black;
uniform vec2 tex_wh;
uniform sampler2D outro_l0, outro_l1;

const vec2 CK = vec2(0.0, 0.36);          // clock centre
const float CR = 0.25;                    // clock radius
const float S = 0.0011;                   // P units per line-texture pixel

// one typed line, centred at height y: the texture's pixels, up to slot `shown`
float type_line(vec2 p, float y, int n, int shown, int which) {
    vec2 tp = vec2(0.5 * tex_wh.x + p.x / S, 0.5 * tex_wh.y + (p.y - y) / S);
    if (tp.x < 0.0 || tp.y < 0.0 || tp.x > tex_wh.x || tp.y > tex_wh.y) return 0.0;
    float left = 0.5 * (tex_wh.x - float(n) * adv_px);
    if (tp.x >= left + float(shown) * adv_px) return 0.0;
    vec2 q = tp / tex_wh;
    return which == 0 ? texture(outro_l0, q).r : texture(outro_l1, q).r;
}

void main() {
    if (black > 0.5) { frag = vec4(0.0, 0.0, 0.0, 1.0); return; }
    vec2 p = P();
    vec3 c = vec3(0.0);

    // the clock: rim, 60 notches, the hand
    float r = length(p - CK);
    c += DARK * 0.8 * exp(-pow((r - CR) / (1.3 * px()), 2.0));
    float a = atan(p.x - CK.x, p.y - CK.y);                    // 0 at twelve, clockwise
    float notch = abs(fract(a / (2.0 * PI) * 60.0 + 0.5) - 0.5) * 2.0 * PI * r / 60.0;
    c += DARK * 0.7 * step(CR - 0.03, r) * step(r, CR - 0.012) * exp(-pow(notch / (1.0 * px()), 2.0));
    float ha = float(n_tick) * 2.0 * PI / 60.0;
    vec2 tip = CK + (CR - 0.04) * vec2(sin(ha), cos(ha));
    float h;
    float d = seg(p, CK, tip, h);
    c += WHITE * 0.85 * glow(d, 1.1 * px());
    c += DARK * 1.2 * smoothstep(0.014, 0.010, r);
    if (stopped < 0.5) c += WHITE * 1.2 * exp(-since_tick / 0.10) * exp(-pow(length(p - tip) / (3.0 * px()), 2.0));

    // the typed lines, and a cursor after the last character typed
    c += WHITE * 0.9 * type_line(p, -0.22, len0, shown0, 0);
    c += WHITE * 0.9 * type_line(p, -0.40, len1, shown1, 1);
    bool on2 = shown1 > 0;
    int n = on2 ? len1 : len0;
    int sh = on2 ? shown1 : shown0;
    float cy = on2 ? -0.40 : -0.22;
    float cx = (float(sh) + 0.5 - 0.5 * float(n)) * adv_px * S;
    float blink = typing > 0.5 ? step(0.5, fract(t * 2.0)) : 1.0;
    if ((shown0 > 0 || on2) && abs(p.x - cx) < 0.4 * adv_px * S && abs(p.y - cy) < 0.042) c += WHITE * 0.55 * blink;

    frag = vec4(c, 1.0);
}
