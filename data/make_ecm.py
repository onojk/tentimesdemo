#!/usr/bin/env python3
"""make_ecm.py — real ECM curves on the tower's dark 96-bit points -> data/ecm.json.

    .venv/bin/python data/make_ecm.py [--out data/ecm.json]

Verse 4's speckle: on every beat a new curve is rolled, and the dark points it would find
light up. Each curve here is a real elliptic-curve run, done mod p (as rho is in
make_tower.py): a curve finds p exactly when its point becomes the point at infinity mod p,
which is when gcd(..., N) would contain p.

    curve       Suyama's parametrisation from sigma (torsion 12), one sigma per curve, the
                same sigma for every point; written as a short Weierstrass curve mod p
    stage 1     Q = k P, k = product of the prime powers <= B1
    stage 2     q Q for every prime q in (B1, B2], by prime-gap stepping (one addition each)
    bounds      B1 = 257, B2 = 12,850: the card's curve priced at 8,187 ruint in NOTES (I-017)

"Dark" means dark under the 10 B1 pipeline (data/tower.json lamp). Seeded, fixed order; the
JSON is byte-identical on every run (the pool only splits the work).
"""
import argparse, json, os, random
from multiprocessing import Pool
from sympy import primerange

SEED = 20261026 + 257
N_CURVES = 48                    # more than verse 4's beats
SIZE = 96
B1, B2 = 257, 12850
HERE = os.path.dirname(os.path.abspath(__file__))

class Found(Exception):
    """An inversion mod p failed while setting up the curve: the gcd shows p at once."""

def inv(x, p):
    x %= p
    if x == 0:
        raise Found
    return pow(x, -1, p)

def add(P, Q, a, p):
    """Affine Weierstrass addition mod p; None is the point at infinity. Exact: infinity is
    a value, never an early exit, so a run finds p only if the multiple it checks is O."""
    if P is None: return Q
    if Q is None: return P
    (x1, y1), (x2, y2) = P, Q
    if x1 == x2:
        if (y1 + y2) % p == 0:
            return None
        l = (3 * x1 * x1 + a) * pow(2 * y1, -1, p) % p
    else:
        l = (y2 - y1) * pow(x2 - x1, -1, p) % p
    x3 = (l * l - x1 - x2) % p
    return (x3, (l * (x1 - x3) - y1) % p)

def mul(k, P, a, p):
    R, A = None, P
    while k:
        if k & 1:
            R = add(R, A, a, p)
        A = add(A, A, a, p); k >>= 1
    return R

def suyama(sigma, p):
    """(point, a) of the Weierstrass form of Suyama's curve for sigma, mod p."""
    u, v = (sigma * sigma - 5) % p, 4 * sigma % p
    x = u ** 3 * inv(v ** 3, p) % p
    A = (pow(v - u, 3, p) * (3 * u + v) * inv(4 * u ** 3 * v, p) - 2) % p
    B = (x ** 3 + A * x * x + x) % p          # Montgomery B y^2 = x^3 + A x^2 + x, with y = 1
    iB = inv(B, p)
    a = (3 - A * A) * inv(3 * B * B, p) % p
    return ((x * iB + A * inv(3 * B, p)) % p, iB), a

K1 = 1
for q in primerange(2, B1 + 1):
    e = q
    while e * q <= B1:
        e *= q
    K1 *= e
PRIMES2 = list(primerange(B1 + 1, B2 + 1))

def ecm_finds(p, sigma):
    """1 if stage 1 finds p (K1 P = O mod p), 2 if stage 2 does (q K1 P = O for a prime q in
    (B1, B2]), 0 if this curve misses."""
    try:
        P, a = suyama(sigma, p)
    except Found:
        return 1
    Q = mul(K1, P, a, p)
    if Q is None:
        return 1
    R, prev, D = mul(PRIMES2[0], Q, a, p), PRIMES2[0], {}
    if R is None:
        return 2
    for q in PRIMES2[1:]:
        g = q - prev
        if g not in D:
            D[g] = mul(g, Q, a, p)
        R = add(R, D[g], a, p); prev = q
        if R is None:
            return 2
    return 0

def run(job):
    sigma, ps = job
    return [ecm_finds(p, sigma) for p in ps]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "ecm.json"))
    ap.add_argument("--curves", type=int, default=N_CURVES)
    a = ap.parse_args()
    tower = json.load(open(os.path.join(HERE, "tower.json")))
    size = next(s for s in tower["sizes"] if s["n"] == SIZE)
    P = size["points"]
    dark = [i for i in range(len(P["p"])) if P["lamp"][i] == "dark"]
    ps = [P["p"][i] for i in dark]
    rng = random.Random(SEED)
    sigmas = [rng.randrange(6, 2 ** 32) for _ in range(a.curves)]
    with Pool() as pool:
        res = pool.map(run, [(s, ps) for s in sigmas])
    curves = [{"sigma": s, "hits": [dark[j] for j, r in enumerate(row) if r],
               "stage2": [dark[j] for j, r in enumerate(row) if r == 2]} for s, row in zip(sigmas, res)]
    n_hit = [len(c["hits"]) for c in curves]
    ever = sorted({i for c in curves for i in c["hits"]})
    out = {"seed": SEED, "size": SIZE, "B1": B1, "B2": B2, "parametrisation": "Suyama (torsion 12)",
           "dark": dark, "curves": curves,
           "summary": {"dark_points": len(dark), "mean_hits_per_curve": round(sum(n_hit) / len(n_hit), 2),
                       "per_curve_rate": round(sum(n_hit) / len(n_hit) / len(dark), 4),
                       "found_by_some_curve": len(ever)}}
    with open(a.out, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))
        fh.write("\n")
    s = out["summary"]
    print(f"{SIZE}-bit dark points {s['dark_points']}; {a.curves} curves at B1 {B1}, B2 {B2}: "
          f"{s['mean_hits_per_curve']} hits per curve (rate {s['per_curve_rate']}), "
          f"min {min(n_hit)} max {max(n_hit)}; found by at least one curve: {s['found_by_some_curve']}")
    print(f"wrote {a.out} ({os.path.getsize(a.out) / 1e3:.1f} kB)")

if __name__ == "__main__":
    main()
