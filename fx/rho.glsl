// Verse 3: "The rho lamp counts its footsteps ... it checks in powers of two, it overshoots
// the turn, twice as far as the meeting place."
// One real Brent run (render.py uniforms_rho): footsteps along its rho, a tail of mu steps
// into a loop of lambda, left and right feet alternating. The walker leaves blue prints:
// dim on steps the detector does not compare, bright on steps it does. The tortoise (the
// saved point, a ring) jumps to the walker at the start of every block, and while a block
// compares, a chord joins them. The loop closes at mu + lambda (the meeting point, marked
// when the walk first gets there); the walk runs on past it to the detecting gcd, which
// flashes. "552 / 279", the card's mean on 16-bit primes, fades in after.
uniform float mu, lam, cur, blk_r, tort, det, flash, after, cap_a, r_cell;
uniform sampler2D rho_text;
uniform vec2 rho_text_size;

const float R = 0.24;                         // loop radius (P units)
const vec2 C = vec2(0.62, 0.08);              // loop centre
const float FOOT = 0.0055;                    // left / right foot offset
const float NTXT = 10.0;

float stepw() { return 2.0 * PI * R / lam; }  // one step along the curve
float side(float i) { return mod(i, 2.0) < 0.5 ? 1.0 : -1.0; }

vec2 pos(float i) {
    if (i < mu) return vec2(C.x - (mu - i) * stepw(), C.y - R + side(i) * FOOT);
    float j = mod(i - mu, lam);
    float a = -0.5 * PI + 2.0 * PI * j / lam;
    return C + (R + side(i) * FOOT) * vec2(cos(a), sin(a));
}

// is step i compared by the detector? (block r holds steps 2r-1 .. 4r-2; the last r compare)
bool compared(float i) {
    float r = exp2(floor(log2((i + 2.0) / 2.0)));
    return i > 3.0 * r - 2.0 + 0.5;
}

float txt(float cell, vec2 p, vec2 at, float hh) {
    vec2 q = (p - at) / vec2(hh * 1400.0 / 96.0, hh);
    if (abs(q.x) > 1.0 || abs(q.y) > 1.0) return 0.0;
    return texture(rho_text, vec2(q.x * 0.5 + 0.5, 1.0 - (cell + 0.5 - 0.5 * q.y) / NTXT)).r;
}

vec3 print_at(vec2 p, float i, float visits) {
    float d = length(p - pos(i));
    float base = (compared(i) ? 0.85 : 0.35) + 0.2 * min(visits - 1.0, 3.0);
    float fresh = exp(-(cur - i) / max(3.0, 0.2 * blk_r));
    float dotv = smoothstep(2.2 * px(), 1.2 * px(), d);
    return (RHO * base + WHITE * 0.8 * fresh) * dotv + RHO * 0.25 * fresh * exp(-d * d / (25.0 * px() * px()));
}

void main() {
    vec2 p = P();
    vec3 c = vec3(0.0);
    float s = stepw();

    // tail prints: the three nearest steps along the line
    if (abs(p.y - (C.y - R)) < 0.03) {
        float fi = mu - (C.x - p.x) / s;
        for (int k = -1; k <= 1; k++) {
            float i = floor(fi + 0.5) + float(k);
            if (i >= 0.0 && i < mu && i <= cur) c += print_at(p, i, 1.0);
        }
    }
    // loop prints: the three nearest slots round the loop; each slot shows its latest visit
    float rr = length(p - C);
    if (abs(rr - R) < 0.03) {
        float a = atan(p.y - C.y, p.x - C.x) + 0.5 * PI;
        float fj = a / (2.0 * PI) * lam;
        for (int k = -1; k <= 1; k++) {
            float j = mod(floor(fj + 0.5) + float(k), lam);
            float first = mu + j;
            if (first <= cur) {
                float visits = floor((cur - first) / lam) + 1.0;
                c += print_at(p, first + (visits - 1.0) * lam, visits);
            }
        }
    }

    // the meeting point: where the loop first closes (step mu + lambda, back onto step mu)
    if (cur >= mu + lam) {
        float d = abs(length(p - pos(mu)) - 0.028);
        c += PM2 * 0.7 * exp(-d * d / (1.5 * px() * px()));
    }

    // tortoise (saved point) and walker
    vec2 tp = pos(tort), hp = pos(floor(cur));
    float dt = abs(length(p - tp) - 0.018);
    c += WHITE * 0.75 * exp(-dt * dt / (1.2 * px() * px()));
    float dh = length(p - hp);
    c += WHITE * 1.2 * glow(dh, 2.5 * px());
    // the chord while the block compares
    if (cur > 3.0 * blk_r - 2.0 && after < 0.0) {
        float h;
        float dc = seg(p, tp, hp, h);
        c += RHO * 0.22 * exp(-dc * dc / (1.0 * px() * px()));
    }

    // detection: one flash and a ring out from the tortoise
    if (after >= 0.0) {
        c += WHITE * 2.2 * flash;
        float ring = abs(length(p - tp) - (0.02 + 0.9 * after));
        c += RHO * 1.2 * exp(-after / 0.8) * exp(-ring * ring / (9.0 * px() * px()));
    }

    // block size, top left; then the card's figures
    c += DARK * 1.5 * txt(r_cell, p, vec2(-1.25, 0.80), 0.04);
    c += WHITE * 0.95 * cap_a * txt(0.0, p, vec2(-0.55, -0.48), 0.075);
    c += DARK * 1.4 * cap_a * txt(1.0, p, vec2(-0.55, -0.62), 0.034);
    frag = vec4(c, 1.0);
}
