#!/usr/bin/env python3
"""make_tower.py — the theta tower from real primes -> data/tower.json.

    python3 data/make_tower.py [--out data/tower.json]

For n = 72, 84, 96 bits, 1,500 smaller factors p each: theta ~ density 1/theta + 1 on
[8/n, 1/2] (theta = log p / log N), p = nextprime(floor(2^(theta n))). Each point sits at
radius 1/2 - theta, angle 2 pi bitlen(P+(p-1)) / (n/2), height n, and is lit by the first
lamp of the measured best pipeline that finds it (td -> rho -> p-1 s1 -> p-1 s2 -> dark):

    72, 84   td to 2^12, no rho, p-1 B1 = 2^9,  stage 2 to 10 B1
    96       no td, Brent rho (skip-half, cost <= 2,048), p-1 B1 = 2^10, stage 2 to 10 B1

Every lamp's own verdict is kept. lamp_100 is the same pipeline with stage 2 to 100 B1 (the
chorus's long arm); s2_ratio = q / B1 for the stage-2 prime q, so any other arm is a
one-line change. Rho runs mod p, which is exact for "would rho find p": the product hits
0 mod p exactly when gcd(product, N) contains p.

Seeded and iterated in a fixed order: the JSON is byte-identical on every run.
"""
import argparse, json, math, os, random
import sympy
from sympy import factorint, nextprime
from mpmath import mp, mpf, floor as mfloor, power as mpower

SEED = 20261026
SIZES = (72, 84, 96)
PER_SIZE = 1500
TD = {72: 2**12, 84: 2**12, 96: None}           # trial division bound (None: no td)
RHO = {72: None, 84: None, 96: 2048}            # rho cost budget (None: no rho)
B1 = {72: 2**9, 84: 2**9, 96: 2**10}
ARM, LONG_ARM = 10, 100                         # stage-2 bound as a multiple of B1
GCD_EVERY = 64                                  # comparisons per gcd in the rho detector
GCD_COST = 7.9                                  # rho cost: 1 per f, 1 per comparison, 7.9 per gcd
CHECK_BITS, CHECK_RUNS = 16, 1000               # rho detector check against NOTES (552 / 279.4)
HERE = os.path.dirname(os.path.abspath(__file__))
mp.dps = 40                                     # 2^(theta n) to 40 digits: floor is exact

def sample_theta(rng, n):
    """Inverse CDF of density proportional to 1/theta + 1 on [8/n, 1/2], by bisection."""
    a, b = 8 / n, 0.5
    F = lambda x: math.log(x / a) + (x - a)
    u = rng.random() * F(b)
    lo, hi = a, b
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if F(mid) < u else (lo, mid)
    return 0.5 * (lo + hi)

def powersmooth(f, B):
    return all(q ** e <= B for q, e in f.items())

def s2_ratio(f, B):
    """q / B1 if p-1 = (B-powersmooth) x q with q a prime > B appearing once, else None."""
    q = max(f)
    if q <= B or f[q] != 1:
        return None
    rest = {k: e for k, e in f.items() if k != q}
    return q / B if powersmooth(rest, B) else None

def brent(p, x0, c, budget=None):
    """Pollard rho with Brent's skip-half detector, run mod p. Blocks of r = 1, 2, 4, ...:
    x is saved at the block start, the first r steps make no comparisons, the next r
    multiply |x - y| into the product, with a gcd every GCD_EVERY comparisons and at the
    block's end. Returns (cost, f evaluations, comparisons, gcds) at the gcd that first
    sees the product = 0 mod p, or None once the cost passes the budget."""
    y, r, fe, cmp_, g = x0, 1, 0, 0, 0
    cost = lambda: fe + cmp_ + GCD_COST * g
    while True:
        x = y
        for _ in range(r):
            y = (y * y + c) % p; fe += 1
        k, prod = 0, 1
        while k < r:
            for _ in range(min(GCD_EVERY, r - k)):
                y = (y * y + c) % p; fe += 1
                prod = prod * (x - y) % p; cmp_ += 1
            g += 1; k += GCD_EVERY
            if prod == 0:
                return (cost(), fe, cmp_, g) if budget is None or cost() <= budget else None
            if budget is not None and cost() > budget:
                return None
        r *= 2

def rho_params(rng, p):
    return rng.randrange(p), rng.randrange(1, p - 2)        # x0; c avoids 0 and -2

def mu_lambda(p, x0, c):
    """Index of the first repeat of x -> x^2 + c mod p from x0: mu + lambda, and lambda."""
    seen, x, i = {}, x0, 0
    while x not in seen:
        seen[x] = i; x = (x * x + c) % p; i += 1
    return i, i - seen[x]

def point(rng, n):
    theta = sample_theta(rng, n)
    p = int(nextprime(int(mfloor(mpower(2, mpf(theta) * n)))))
    f = factorint(p - 1)
    big = max(f)
    B = B1[n]
    td = TD[n] is not None and p <= TD[n]
    rho_cost = None
    if RHO[n] is not None:
        x0, c = rho_params(rng, p)           # drawn for every point, so the stream is fixed
        hit = brent(p, x0, c, RHO[n])
        rho_cost = None if hit is None else round(hit[0], 1)
    s1 = powersmooth(f, B)
    s2 = s2_ratio(f, B)
    def lamp(arm):
        if td: return "td"
        if rho_cost is not None: return "rho"
        if s1: return "pm1_s1"
        if s2 is not None and s2 <= arm: return "pm1_s2"
        return "dark"
    return {"theta": round(theta, 6), "p": p, "big": int(big), "big_bits": int(big).bit_length(),
            "radius": round(0.5 - theta, 6),
            "angle": round(2 * math.pi * int(big).bit_length() / (n / 2), 6),
            "height": n, "td": td, "rho_cost": rho_cost, "s1": s1,
            "s2_ratio": None if s2 is None else round(s2, 4),
            "lamp": lamp(ARM), "lamp_100": lamp(LONG_ARM)}

LAMPS = ("td", "rho", "pm1_s1", "pm1_s2", "dark")

def rho_check(rng):
    """The detector on CHECK_RUNS random CHECK_BITS-bit primes, no budget: mean f
    evaluations at detection against mean mu + lambda (NOTES: card 552.0 against 279.4).
    Also keeps the run nearest both means, as scene 6's trace."""
    runs = []
    for _ in range(CHECK_RUNS):
        p = int(nextprime(rng.randrange(2 ** (CHECK_BITS - 1), 2 ** CHECK_BITS - 64)))
        x0, c = rho_params(rng, p)
        cost, fe, cmp_, g = brent(p, x0, c)
        ml, lam = mu_lambda(p, x0, c)
        runs.append((p, x0, c, cost, fe, cmp_, g, ml, lam))
    mean = lambda k: sum(r[k] for r in runs) / len(runs)
    m_fe, m_ml = mean(4), mean(7)
    best = min(runs, key=lambda r: abs(r[4] / m_fe - 1) + abs(r[7] / m_ml - 1))
    p, x0, c, cost, fe, cmp_, g, ml, lam = best
    xs = [x0]
    for _ in range(fe):
        xs.append((xs[-1] * xs[-1] + c) % p)
    trace = {"p": p, "x0": x0, "c": c, "mu": ml - lam, "lambda": lam, "mu_plus_lambda": ml,
             "detect_f": fe, "comparisons": cmp_, "gcds": g, "cost": round(cost, 1),
             "blocks": [2 ** k for k in range(int(math.log2(fe)) + 1)], "xs": xs,
             "rule": "the check run nearest both means (f evaluations, mu + lambda)"}
    return {"bits": CHECK_BITS, "runs": CHECK_RUNS,
            "mean_detect_f": round(m_fe, 1), "mean_mu_plus_lambda": round(m_ml, 1),
            "ratio": round(m_fe / m_ml, 3), "mean_cost": round(mean(3), 1),
            "mean_comparisons": round(mean(5), 1), "mean_gcds": round(mean(6), 2),
            "notes": "card: 552.0 f evaluations against mean mu + lambda 279.4 (ratio 1.98)",
            "trace": trace}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "tower.json"))
    a = ap.parse_args()
    rng = random.Random(SEED)
    sizes, summary = [], {}
    for n in SIZES:
        pts = [point(rng, n) for _ in range(PER_SIZE)]
        order = list(range(PER_SIZE)); rng.shuffle(order)
        half = {i: ("A" if k < PER_SIZE // 2 else "B") for k, i in enumerate(order)}
        cols = {k: [pt[k] for pt in pts] for k in pts[0]}
        cols["half"] = [half[i] for i in range(PER_SIZE)]
        frac = lambda key: {l: round(sum(x == l for x in cols[key]) / PER_SIZE, 4) for l in LAMPS}
        summary[n] = {"lit_10": frac("lamp"), "lit_100": frac("lamp_100"),
                      "distinct_p": len(set(cols["p"]))}
        sizes.append({"n": n, "B1": B1[n], "td": TD[n], "rho_budget": RHO[n],
                      "arm": ARM, "long_arm": LONG_ARM, "points": cols})
    check = rho_check(rng)
    out = {"seed": SEED, "sympy": sympy.__version__, "per_size": PER_SIZE,
           "density": "1/theta + 1 on [8/n, 1/2]", "lamp_order": list(LAMPS),
           "rho_cost": {"f": 1, "comparison": 1, "gcd": GCD_COST, "gcd_every": GCD_EVERY},
           "sizes": sizes, "summary": summary, "rho_check": check}
    with open(a.out, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
        fh.write("\n")

    print(f"{'n':>3} {'arm':>4}  " + "  ".join(f"{l:>6s}" for l in LAMPS) + "  distinct p")
    for n in SIZES:
        s = summary[n]
        for arm, key in ((ARM, "lit_10"), (LONG_ARM, "lit_100")):
            print(f"{n:3d} {arm:3d}x  " + "  ".join(f"{s[key][l]:6.3f}" for l in LAMPS)
                  + (f"  {s['distinct_p']}" if arm == ARM else ""))
    c, t = check, check["trace"]
    print(f"\nrho check, {c['runs']} x {c['bits']}-bit primes: detect at {c['mean_detect_f']} f "
          f"(+{c['mean_comparisons']} comparisons, {c['mean_gcds']} gcds; cost {c['mean_cost']}) "
          f"vs mu + lambda {c['mean_mu_plus_lambda']}: ratio {c['ratio']}  [{c['notes']}]")
    print(f"trace: p {t['p']}, mu {t['mu']}, lambda {t['lambda']}, detect at f {t['detect_f']}")
    print(f"wrote {a.out} ({os.path.getsize(a.out) / 1e6:.2f} MB)")

if __name__ == "__main__":
    main()
