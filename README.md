# Ten Times, Not a Hundred — a demoscene music video

A demoscene music video for **"Ten Times, Not a Hundred"**, a synth-pop song: vocoder robot
lead, barbershop quartet harmonies, clock ticks, measured at 105.9 bpm. It is rendered
offline and deterministically from GLSL shaders, driven by an analysis of the song.

The song reports one night's findings from
[lumens-per-watt](https://github.com/onojk/lumens-per-watt), a project that meters how
much work each factoring method ("lamp") spends to light up a number. The video shows those
findings, and its data is real. Every point drawn is a real prime, every lamp decision is
an exact test, and every number on screen comes from a stated source (see below).

## The song is not included

This repo has no audio in it. Bring your own WAV of the song as `audio/ten_times.wav`
(`audio/` is git-ignored).

## What the film shows

The picture at the centre is the **theta tower**. A point is a number N = p · q with smaller
factor p, for 72-, 84- and 96-bit N:
- **radius** = 1/2 − θ, with θ = log p / log N, so small factors sit at the rim and
  balanced ones at the centre;
- **angle** = 2π · bits of the largest prime factor of p − 1, over n/2;
- **height** = n, so each size is one band.

Each point is coloured by the first lamp of the pipeline that finds it:

| lamp | colour |
|---|---|
| trial division | orange |
| rho | blue |
| p−1 stage 1 | deep green |
| p−1 stage 2 | light green |
| nothing (left for the quadratic sieve) | grey |

The centre, the spine, is always grey: that's the wall.

| section | scene |
|---|---|
| intro (ticks) | One number's ray grows from the rim to the spine, one step per detected clock tick. |
| verse 1 | The tower assembles band by band, one ring per beat, rim first. Trial division lights the rim orange. |
| verse 2 | A split-flap counter flips 3.4 → 1.4. A Dickman curve at c = 3.4 sits above the measured stage-1 hit rates, then springs, overshoots and settles at c = 1.41. |
| pre-choruses | Four beams, one per quartet voice, each lit by its frequency band. Grey static on "no warmer, no colder", one white flash on "yes". |
| choruses | **Light against bill.** The long arm (stage 2 to 100·B1) lights more numbers than the short arm (10·B1), but its cost bar goes red past the qs line. The short arm saves. 72-bit in chorus 1, 84-bit in chorus 2. |
| verse 3 | A real Brent rho run as footsteps on its ρ: the detector checks in powers of two, overshoots the meeting point, then flashes on detection. |
| verse 4 | Real ECM curves re-roll every beat, and the dark points each one would find sparkle. A price ticker lands on 8,187, and a floodlight (qs) washes in. |
| bridge | Split screen. Left: one number's ray lights from the rim to its factor and sparks. Right: the spark lands on the tower, which fills, half A then half B. The centre stays grey. |
| final chorus | The whole tower lit, orbiting, with bloom on the choir swell. The orbit slows side-on to the spiral edge, and the 72-bit cost bars echo on "forty-three". |
| outro | "Twelve percent on the plain arm. / Sealed before the run." typed on the spoken words. A clock ticks with the audio and stops on the last tick. |

## The data

`data/make_tower.py` → `data/tower.json` (seeded; byte-identical on every run):

- **Prior.** For n = 72, 84 and 96 bits, there are 1,500 samples each, drawn from the
  primehelix prior used in lumens-per-watt: θ has density ∝ 1/θ + 1 on [8/n, 1/2], and
  p = nextprime(⌊2^(θn)⌋), so p ≥ 2^8.
- **Lamp rules** (exact tests, in pipeline order), from the measured best pipeline shapes:

  | n | trial division | rho | p−1 B1 | p−1 stage 2 |
  |---|---|---|---|---|
  | 72 | p ≤ 2^12 | — | 2^9 | one prime q in (B1, 10·B1] |
  | 84 | p ≤ 2^12 | — | 2^9 | one prime q in (B1, 10·B1] |
  | 96 | — | Brent, skip-half, cost ≤ 2,048 | 2^10 | one prime q in (B1, 10·B1] |

  - p−1 stage 1 needs p − 1 to be B1-powersmooth.
  - p−1 stage 2 needs p − 1 = (B1-powersmooth) × q.
  - Rho is a real Brent run mod p. Cost is 1 per f-evaluation, 1 per comparison and 7.9 per
    gcd, with a gcd every 64 comparisons.
  - Each point also stores its verdict with stage 2 at 100·B1 (the long arm), and q / B1.
- **Checks.**
  - At 72 bits, at NOTES' 20·B1 bound, the coverage agrees with lumens-per-watt's to within
    about 0.02 per lamp: td 0.246, s1 0.190, s2 0.199, dark 0.365.
  - Fitting the Dickman size divisor to the tower's own stage-1 hits gives c = 1.46
    (95% interval 1.29–1.65), consistent with the 1.41 shown on screen.
  - The rho detector, run on 1,000 random 16-bit primes, detects at a mean of 536 f
    evaluations against a mean μ + λ of 279 (the card in NOTES: 552 against 279.4).

`data/make_ecm.py` → `data/ecm.json`:
- 48 seeded Suyama ECM curves at the card's B1 = 257 and B2 = 12,850, run mod p on each of
  the 657 dark 96-bit points;
- the arithmetic is exact, and was checked 300/300 against exact point orders;
- each curve finds about 136 of the 657 points. These are the verse-4 speckle.

## Where each number on screen comes from

From lumens-per-watt's `NOTES.md` (Oct 26) and from `data/tower.json`:

| on screen | figure | source |
|---|---|---|
| 3.4 → 1.4, "fitted c = 1.41" | p − 1 behaves like a random integer of size p/c: model input 3.4; fitted c = 1.41 (stage 1) on 1,500 real primes per size | NOTES, "Real-prime measurement run" |
| +42.8% / −6.4% (chorus 1, 72-bit) | stage 2 appended to the stage-1 pipeline, plain, 72 bits: to 100·B1 it costs 42.8% more; to 10·B1 it saves 6.4% | NOTES, "Real-prime split-half search" |
| +35.6% / −4.6% (chorus 2, 84-bit) | the same row at 84 bits | same |
| 402 / 247 (72-bit), 386 / 225 (84-bit) | stage-2 points lit at 100·B1 / 10·B1 | `data/tower.json` |
| 552 / 279 | the card's rho: mean 552.0 f evaluations at detection against mean μ + λ 279.4, on 16-bit primes | NOTES, outside checks, second round |
| 8,187 | ruint per ECM curve at B1 = 257 | NOTES, I-017 information step |
| "Twelve percent on the plain arm." | the honest saving from plain p−1 stage 2 at 72 bits, 12.1%, split-half | NOTES, "Real-prime split-half search" |
| "Sealed before the run." | every prediction is sealed in NOTES before its run | NOTES |

The rho footsteps are one real run (p = 51503, μ = 165, λ = 114). It detects at 510 f
evaluations; the caption gives the card's mean.

## Requirements

- Python 3.10+, with ffmpeg on `PATH`
- a GPU or driver with EGL and OpenGL 3.3 (Mesa works headless)

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt        # numpy, moderngl, sympy
```

## Rebuild

```sh
# the data (already committed; both scripts are deterministic)
.venv/bin/python data/make_tower.py              # -> data/tower.json
.venv/bin/python data/make_ecm.py                # -> data/ecm.json

# analyse the song -> cache/features.json (tempo, beats, onsets, bands, quartet bands,
# clock ticks, beat chroma); then the section map and word cues -> cache/sections.json
.venv/bin/python analyze.py audio/ten_times.wav
.venv/bin/python sections.py

# the whole film at 1080p, song muxed in (about 2 minutes on an Intel Lunar Lake iGPU, Mesa)
.venv/bin/python render.py renders/ten_times_1080p.mp4 --audio audio/ten_times.wav --full

# one section as a 480p preview, or stills
.venv/bin/python render.py renders/bridge.mp4 --audio audio/ten_times.wav --section bridge --res 480
.venv/bin/python render.py - --still 210.3 --still 226        # PNGs into renders/
```

The section boundaries and word cues in `sections.py` were checked against a transcript
of the song with word timestamps. Rendering is deterministic: time is `frame / 30`, and
grain comes from a fixed seed, so the same command gives byte-identical frames.

The pipeline (offline GLSL renderer, audio analysis, ffmpeg mux) is adapted from the
author's earlier video, [laser-beam-demo](https://github.com/onojk/laser-beam-demo).

## License

MIT, see [LICENSE](LICENSE). This covers the code and data only. The song belongs to its
author.
