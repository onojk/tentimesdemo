// Bridge: split screen. "One number's line is one ray of the tower, the rim lights first, then
// the spark comes in. A thousand rays and the tower fills, and the centre stays grey."
// Left: the intro's number (p = 20693) as its ray, rim to spine. From "the rim lights first"
// the ray lights from the rim inward and reaches the radius of its factor on "spark", where
// a light-green spark (p-1 stage 2, the lamp that finds it) flares. The spark then arcs across
// the grey centre line to the same number's point on the tower (right, bridge.pts.glsl).
uniform float ray_angle, r_spine;
uniform float lit_front, spark_f, since_spark, fly, left_r;
uniform vec2 spark_from, spark_to, left_c;

// a glow with no 1/r tail: a bright spark must not tint the whole frame
float halo(float d, float w) { return exp(-d * d / (w * w)) + 0.25 * exp(-d * d / (36.0 * w * w)); }

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    vec2 dir = vec2(cos(ray_angle), sin(ray_angle));
    vec2 rim = left_c + dir * left_r;
    float span = left_r - r_spine * 1.6;
    vec2 inner = rim - dir * span;

    // the whole ray, unlit: grey; the lit part from the rim in to lit_front
    float h;
    float d = seg(p, rim, inner, h);
    float w = 1.1 * px();
    float lit = step(h * 1.0, lit_front + 1e-4);
    vec3 col = mix(DARK * 0.45, WHITE * 0.75, lit);
    c += col * glow(d, w);
    vec2 front = rim - dir * span * lit_front;
    if (lit_front > 0.0 && since_spark < 0.0) c += WHITE * 0.8 * glow(length(p - front), 2.2 * px());

    // the faint rim circle and the spine dot of this one-number picture
    float rr = length(p - left_c);
    c += DARK * 0.25 * exp(-pow((rr - left_r) / (1.2 * px()), 2.0));
    c += DARK * 0.9 * smoothstep(r_spine, r_spine * 0.6, rr);

    // the spark: a flare at the find, a mark left behind, and the one that flies across
    if (since_spark >= 0.0) {
        float ds = length(p - spark_from);
        c += PM2 * (0.5 + 2.5 * exp(-since_spark / 0.25)) * halo(ds, 3.0 * px());
        if (fly > 0.0 && fly < 1.0) {
            float e = fly * fly * (3.0 - 2.0 * fly);
            vec2 mid = 0.5 * (spark_from + spark_to) + vec2(0.0, 0.35);
            vec2 sp = mix(mix(spark_from, mid, e), mix(mid, spark_to, e), e);
            c += (PM2 * 2.0 + WHITE) * halo(length(p - sp), 3.5 * px());
        }
    }

    // the centre of the split stays grey
    c += DARK * 0.5 * exp(-pow(p.x / (1.0 * px()), 2.0)) * smoothstep(0.95, 0.80, abs(p.y));
    frag = vec4(c, 1.0);
}
