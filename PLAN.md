# Ten Times, Not a Hundred — plan

A demoscene music video for "Ten Times, Not a Hundred" (Suno; electronic synth-pop with a
vocoder robot lead, barbershop harmonies and clock ticks). The song reports tonight's
lumens-per-watt findings. Every number on screen is a figure from
`~/lumens-per-watt/NOTES.md` (§6). Every point in the tower comes from real primes, in
`data/tower.json`, built by `data/make_tower.py`.

## 0. What the audio analysis found

Run with ref's `analyze.py`, unchanged; stage 3 adapts it.

- **Length** 232.000 s (48 kHz stereo). The music stops hard at **3:50.87**, on the last
  tracked beat (beat 404), dropping from −26 to −83 dBFS within a second, followed by 1.1 s
  of silence.
- **Tempo 105.9 bpm** (the style line's 92 doesn't apply). The beat tracker gives 405 beats,
  median gap 0.567 s ± 0.016, steady in every 30 s window. Autocorrelation at 92 bpm is
  negative in every window. One bar is 2.267 s. All sync uses the measured beat grid.
- **Bass dropouts** with strong novelty peaks at 1:23.67, 2:32.53, 3:04.43 and 3:31.83. The
  first two last **exactly 8 beats (2 bars)** each, which fits the two-line a cappella
  pre-chorus.
- **Repeats (beat-synchronous chroma):** the passage at **1:00.37–1:23.67** recurs at
  **2:08.63–2:32.53** (similarity 0.72) and at **3:13.57–3:31.83** (0.60–0.67). The first
  two each lead straight into a pre-chorus, so they are verse 2 and verse 4 (10.3 and
  10.5 bars).

## 1. Section map (provisional; feature-based, no transcription)

Times are snapped to the beat grid. "Confidence" says how well the features support each
row.

| # | section | start | end | bars | scene | confidence, evidence |
|---|---|---|---|---|---|---|
| 1 | intro (ticks) | 0:00.00 | 0:08.63 | 3.8 | ray | high: −30 dBFS, no bass |
| 2 | verse 1 | 0:08.63 | 1:00.37 | 22.8 | assemble | **low**: see *Unplaced* |
| 3 | verse 2 | 1:00.37 | 1:23.67 | 10.3 | flap | medium: same music as verse 4, leads into pre-chorus 1 |
| 4 | pre-chorus 1 | 1:23.67 | 1:28.23 | 2.0 | quartet (white) | high: 8-beat bass dropout, novelty 0.82 |
| 5 | chorus 1 | 1:28.23 | 1:47.00 | 8.3 | arms, 72-bit | medium: end at novelty 0.40 |
| 6 | verse 3 | 1:47.00 | 2:08.63 | 9.5 | rho | medium |
| 7 | verse 4 | 2:08.63 | 2:32.53 | 10.5 | ecm | medium-high: repeat of verse 2 (0.72) |
| 8 | pre-chorus 2 | 2:32.53 | 2:37.10 | 2.0 | quartet (tower palette) | high: 8-beat dropout, novelty 0.81 / 0.91 |
| 9 | chorus 2 | 2:37.10 | 3:04.43 | 12.1 | arms, 84-bit | high on start; 4 bars longer than chorus 1 |
| 10 | bridge | 3:04.43 | 3:13.57 | 4.0 | split screen | start high (dropout, sparse: 4 onsets in 4 s); **end low** |
| 11 | final chorus | 3:13.57 | 3:41.00 | 12.1 | finale, 72/84/96 stacked | **low**: see *Unplaced* |
| 12 | outro (spoken, ticks) | 3:41.00 | 3:50.87 (+1.13 s silence) | 4.4 | outro | medium: high band collapses 0.25 → 0.13 |

**Unplaced: please confirm by ear.**

- **0:08.63–1:00.37.** Is verse 1 all of this? Or is 0:08.63–0:36.47 more intro, with
  verse 1 at 0:36.47 (10.5 bars, the same length as the other verses)? There is also a
  1.5-bar step at 0:56.93.
- **3:04.43 → 3:13.57 → 3:31.83.** A bridge of 8 lines in 4 bars is short. 3:13.57–3:31.83
  is the same music as verses 2 and 4, so the bridge may be sung over it, with the final
  chorus starting at the 3:31.83 dropout. That would leave the final chorus only 4 bars
  plus the outro.
- **Outro start:** 3:41.00 or 3:45.67.
- **Word cues** (the "yes" flash, "forty-three", 3.4 → 1.4, the outro's last word): I'll
  propose times from onset and rms features in stage 3 for you to confirm.

## 2. What is reused from ref/laser-beam-demo

`ref/` is git-ignored. Files are copied across and adapted, not imported.

| ref | here | kept | changed |
|---|---|---|---|
| `analyze.py` | `analyze.py` | ffmpeg decode at 22050 Hz mono; 735-sample hop, so exactly 30 frames per second; STFT; rms; spectral-flux onsets; autocorrelation tempo; Ellis DP beats; low/mid/high; beat-chroma novelty | drop tape wobble; add quartet bands, tick detection and the repeat matrix (§4) |
| `sections.py` | `sections.py` | `RAW` map with a `why` per boundary, beat-snapped, printed as a table | the 12 rows above, plus `CUES` |
| `sync.py` | `sync.py` | `at/since/beat/section/uniforms`; flashes under 3 per second; integrated speeds | white flash only where asked; per-scene uniforms |
| `render.py` | `render.py` | moderngl/EGL headless; `t = frame / 30`; hash-seeded grain (byte-identical reruns); HEAD prelude; quarter-res two-pass bloom; ffmpeg rgb24 → libx264 + `-ss/-t` audio mux, `apad`, 40 ms tail fade, bt709, faststart; `--start/--dur/--full/--still/--scene/--crf`; `text_image()` | §3 |
| `fx/*.glsl` | `fx/*.glsl` | one fragment shader per scene on the shared HEAD | new scenes (§7) |

Not reused: the scroller, the logo pen, the tape warp, the collapse.

## 3. Renderer changes

- **Linear RGB from scenes.** ref's three-emission-channel palette can't give six fixed
  hues. HEAD instead defines `TD` orange, `RHO` blue, `PM1` deep green, `PM2` light green,
  `DARK` grey and `WHITE`. Post keeps bloom, tone map and grain on pure black. Scanlines are
  off by default.
- **Point pass.** The tower's 4,500 points are drawn as `GL_POINTS` from a VBO, with an
  orbit camera and per-point lamp/fade logic in the vertex shader and gaussian sprites,
  blended additively into the scene FBO before bloom. Looping over them per pixel would be
  about 9 G ops per frame at 1080p. Sprite size scales with resolution.
- **`--res 480|1080|2160`**, width = H·16/9 rounded to even (854×480 previews).
- **Text** comes from one monospace glyph atlas made with `text_image()`, indexed per
  character in the shaders.

## 4. Audio analysis (stage 3)

ref's features minus wobble, plus:

- **Quartet bands** `q_bass/q_bari/q_lead/q_tenor`: about 70–180 / 180–300 / 300–500 /
  500–900 Hz, each normalised within the pre-choruses. These are four levels in a mix, not
  separated voices. I'll print their correlations and move the edges if any two have
  r > 0.9.
- **Ticks** `tick_t`: evenly spaced, high-band-dominant onsets in the intro and outro, with a
  fitted period.
- **Repeats:** the beat-chroma similarity used for §0, saved for checking.

## 5. The data: `data/make_tower.py` → `data/tower.json` (stage 2)

Python with sympy and a seeded `random.Random`, in a fixed order, so the JSON is
byte-identical on every run.

Per n ∈ {72, 84, 96}, 1,500 samples:

1. θ ~ density ∝ 1/θ + 1 on [8/n, 1/2], by inverse CDF (F ∝ ln θ + θ, bisection);
   p = `nextprime(floor(2^(θn)))`.
2. Position: radius = 1/2 − θ; angle = 2π · bitlen(P⁺(p−1)) / (n/2); height = n.
3. Lamps, in pipeline order td → rho → p−1 s1 → p−1 s2 → dark. Every lamp's own verdict is
   stored; the colour comes from the first one that hits.

   | n | td | rho | p−1 B1 | stage 2 |
   |---|---|---|---|---|
   | 72 | p ≤ 2^12 | — | 2^9 | prime q ∈ (B1, 10·B1] |
   | 84 | p ≤ 2^12 | — | 2^9 | prime q ∈ (B1, 10·B1] |
   | 96 | — | Brent, skip-half, cost ≤ 2,048 | 2^10 | prime q ∈ (B1, 10·B1] |

   - **p−1 stage 1:** p−1 is B1-powersmooth (every q^e ‖ p−1 has q^e ≤ B1).
   - **p−1 stage 2:** p−1 = m·q, with m B1-powersmooth and q a prime in (B1, 10·B1] that
     appears once.
   - **rho (96 only):** f(x) = x² + c mod p, with x₀ and c from the seeded RNG. This is the
     standard Brent/Pollard loop:
     - blocks of length r = 1, 2, 4, …;
     - the saved point x is fixed at the start of each block;
     - the first r steps of a block make no comparisons;
     - the next r steps accumulate |x − y| into a product;
     - a gcd runs every 64 comparisons and at the end of the block.

     Cost = 1 per f-evaluation + 1 per comparison + 7.9 per gcd. It hits if the gcd that
     first sees the product ≡ 0 mod p comes at cost ≤ 2,048. Working mod p is exact for
     this question.
4. **Stored per point:**
   - n, θ, p, P⁺(p−1), radius, angle;
   - the stage-2 prime q and q/B1, so 20× is a one-line change;
   - `lamp` (10× B1) and `lamp_100` (100× B1, the chorus's long arm);
   - the rho cost at 96;
   - a split-half label A/B (seeded), for the bridge's "half of the numbers chose the road".
5. **Summary** (printed and in the JSON): the fraction lit per lamp per n at 10× and 100×.
   I'll print these next to the NOTES coverage tables as a sanity check. They will not
   match exactly, because NOTES used the primehelix prior and this uses 1/θ + 1, so I won't
   tune anything toward them.
6. **Rho check:** the same detector on 16-bit primes, reporting the mean f-evaluations at
   detection against the mean μ + λ. NOTES has 552 against 279.4 for the card. I'll report
   my figures as they come out. One real run's trace (μ, λ, power-of-two checkpoints,
   detection step) is stored for scene 6.

Duplicate p (common at small θ) stay in; they are part of the density.

## 6. Numbers on screen and where they come from

All are from `~/lumens-per-watt/NOTES.md`, Oct 26, and are shown exactly as written there:

| on screen | figure | NOTES |
|---|---|---|
| 3.4 → 1.4 (1.41) | p−1 behaves like a random integer of size p/c: model input 3.4, fitted c = 1.41 (stage 1) on 1,500 real primes per size, 16–44 bits | "Real-prime measurement run" (l. 4741–4743) |
| 43 (+42.8%) | appending stage 2 at 100·B1: −42.8% at 72 bits (plain); at 10·B1 it saves 6.4% | "Real-prime split-half search" (l. 4848) |
| 552 / 279 (1.98×) | the card's rho detects at 552.0 f-evaluations against mean μ + λ = 279.4 on 16-bit primes | Outside checks, second round (l. 1713–1716) |
| 8,187 | ruint per ECM curve at B1 = 257 | I-017 information step (l. 4626) |
| 12.1% | the honest saving from plain p−1 stage 2 at 72 bits, split-half | "Real-prime split-half search" (l. 4845) |

## 7. Scenes

Colours on black: td orange, rho blue, p−1 stage 1 deep green, p−1 stage 2 light green, dark
grey. The spine (radius → 0) is always grey: it's the wall.

1. **Intro, ray.** A thin line at one real point's angle grows from the rim toward the
   centre, one step per detected tick, stopping short of the grey spine.
2. **Verse 1, assemble.** The 72, 84 and 96 bands build in turn. Points land ring by ring on
   the beat in radius order, rim first. The td rim lights orange; the spine stays grey.
3. **Verse 2, flap.** A split-flap counter flips 3.4 → 1.4 on the cue. A curve (Dickman at
   c = 3.4) overshoots, then settles (damped spring) onto the dots, which are the tower's
   measured p−1 stage-1 lit fraction per θ bin, scaled so the settled curve is Dickman at
   c = 1.41.
4. **Pre-chorus 1, quartet.** Four vertical beams in white (bass, baritone, lead, tenor),
   with brightness and width from their bands. Static grey on "no warmer, no colder"; one
   white flash on "yes".
5. **Pre-chorus 2.** The same scene, with beam colours from the tower palette (td, rho, p−1
   s1, p−1 s2).
6. **Chorus 1 (72-bit) / chorus 2 (84-bit), arms.**
   - Long arm to 100·B1: the points `lamp_100` gains light, then dim and fall away on
     "forty-three", with "+42.8%" shown.
   - Short arm to 10·B1: a clean light-green wedge sweeps round once per bar, lighting
     stage-2 points as it passes.
   - Chorus 2 is 4 bars longer, so the sweep runs longer, not faster.
7. **Verse 3, rho.** The stored Brent run's footsteps around its ρ cycle. The stride doubles
   at each power of two, and the walk runs past the meeting point toward 2× ("552 / 279").
   Flash on detection.
8. **Verse 4, ECM.** A speckle re-rolls each beat (seed = beat index). A ticker counts up to
   8,187. A broad, soft floodlight washes in.
9. **Bridge, split screen.**
   - Left: one ray lights outside-in, with a spark at the find.
   - Right: the spark lands on the tower, which fills over the section, half A first, then
     half B checking it through.
   - The centre stays grey.
10. **Final chorus.** All three sizes stacked (72 / 84 / 96), fully lit from the JSON,
    orbiting slowly. Bloom follows the choir swell (smoothed rms + high band).
11. **Outro.** "Twelve percent on the plain arm." / "Sealed before the run." typed on the
    spoken words over a ticking clock, which stops on the last word.

## 8. Stages and commits

Each commit uses explicit `git add <paths>`. I never push.

1. `PLAN.md`, `lyrics.md`, `.gitignore`.
2. `data/make_tower.py`, `data/tower.json`, `requirements.txt`.
3. `analyze.py`, `sections.py`, `sync.py` (`cache/` stays ignored).
4. `render.py` plus `fx/*.glsl`, one scene at a time, with a 480p preview of each
   (`renders/preview_<n>.mp4`) sent before the next.
5. Full 1080p render with the mux.
6. 4K, on approval only.

Setup: `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` (numpy,
moderngl, sympy).
