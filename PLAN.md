# Ten Times, Not a Hundred — plan

A demoscene music video for "Ten Times, Not a Hundred" (Suno; electronic synth-pop with a
vocoder robot lead, barbershop harmonies and clock ticks). The song reports tonight's
lumens-per-watt findings. Every number on screen is a figure from
`~/lumens-per-watt/NOTES.md` (§6). Every point in the tower comes from real primes, in
`data/tower.json`, built by `data/make_tower.py`.

## 0. What the audio analysis found

- **Length** 232.000 s (48 kHz stereo). The music stops hard at **3:50.87**, on the last
  tracked beat (beat 404): −26 to −83 dBFS within a second, then 1.1 s of silence.
- **Tempo 105.9 bpm** (the style line's 92 doesn't apply). 405 beats, median gap 0.567 s,
  steady in every 30 s window. One bar is 2.267 s. All sync uses the measured beat grid.
- **Ticks** sit on the half-beat (eighth-note) grid: 17 in the intro and 26 in the outro.
  The last is at 3:49.70, after the last spoken word.
- **Sections** are confirmed against a transcript (faster-whisper medium.en with word
  timestamps, run from a scratchpad venv that isn't committed). Suno kept the lyric order.
  The feature-only reading in the first draft was wrong: the 8-beat bass dropouts at 1:23.67
  and 2:32.53 are the **ends of the choruses** (instrumental tails), not the pre-choruses.

## 1. Section map (confirmed by transcript)

Each section starts on its first sung word (or vocal fill), snapped to the nearest beat.

| # | section | start | end | bars | scene | first words |
|---|---|---|---|---|---|---|
| 1 | intro (ticks) | 0:00.00 | 0:07.50 | 3.3 | ray | — |
| 2 | verse 1 | 0:07.50 | 0:36.47 | 12.8 | assemble | "I built a tower" |
| 3 | verse 2 | 0:36.47 | 0:56.37 | 8.8 | flap | "ah" fill, then "I swore the line" |
| 4 | pre-chorus 1 | 0:56.37 | 1:01.50 | 2.3 | quartet (white) | "No warmer, no colder" |
| 5 | chorus 1 | 1:01.50 | 1:28.23 | 11.8 | arms, 72-bit | "Ten times"; ends in a 4 s instrumental tail |
| 6 | verse 3 | 1:28.23 | 1:46.43 | 8.0 | rho | "The rho lamp" |
| 7 | verse 4 | 1:46.43 | 2:04.67 | 8.0 | ecm | "The curves came in" |
| 8 | pre-chorus 2 | 2:04.67 | 2:09.77 | 2.2 | quartet (tower palette) | "No warmer, no colder" |
| 9 | chorus 2 | 2:09.77 | 2:36.53 | 11.8 | arms, 84-bit | "Ten times"; 4 s tail |
| 10 | bridge | 2:36.53 | 3:05.03 | 12.6 | split screen | "One number's line" |
| 11 | final chorus | 3:05.03 | 3:37.50 | 14.3 | finale, 72/84/96 | "da da" fill, then "Ten times" (3:09.00), tag "the tower's lit" ×3 |
| 12 | outro | 3:37.50 | 3:52.00 (music to 3:50.87) | 6.4 | outro | "Twelve percent on the plain arm" |

**Word cues** (transcript word starts, not snapped), in `sections.py` `CUES`:

| cue | time | word |
|---|---|---|
| three_point_four | 0:44.92 | "three-point-four" |
| one_point_four | 0:50.02 | "one-point-four" |
| static1 on / off | 0:56.38 / 0:58.56 | "No warmer, no colder" |
| yes1 | 1:01.12 | "yes" |
| forty_three1 | 1:09.48 | "forty-three" |
| meeting | 1:43.64 | "meeting place" ("twice as far" 1:42.26) |
| eight_thousand | 1:50.98 | "eight thousand" |
| static2 on / off | 2:04.48 / 2:06.78 | "No warmer, no colder" |
| yes2 | 2:09.42 | "yes" |
| forty_three2 / 3 | 2:17.68 / 3:17.00 | "forty-three" |
| tower_lit | 3:30.12 | "and the tower's lit" |
| outro_line1 / 2 | 3:37.38 / 3:40.78 | the two spoken lines |
| last_word | 3:43.58 | "run" (ends 3:44.46): the typed text completes; the clock ticks on to the last tick, 3:49.70 |

## 2. What is reused from ref/laser-beam-demo

`ref/` is git-ignored. Files are copied across and adapted, not imported.

| ref | here | kept | changed |
|---|---|---|---|
| `analyze.py` | `analyze.py` | ffmpeg decode at 22050 Hz mono; 735-sample hop, so exactly 30 frames per second; STFT; rms; spectral-flux onsets; autocorrelation tempo; Ellis DP beats; low/mid/high; beat-chroma novelty | drop tape wobble; add quartet bands, tick detection and the repeat matrix (§4) |
| `sections.py` | `sections.py` | `RAW` map with a `why` per boundary, beat-snapped, printed as a table | the 12 rows above (from the transcript), plus `CUES` and the ticks |
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
   The density 1/θ + 1 on [8/n, 1/2] **is the primehelix prior** that NOTES used (p ≥ 2^8,
   1,500 per size), so the coverage should agree closely with NOTES, and it does.
   - At 72 bits, against NOTES' "Light, best paired" (td 2^12, B1 2^9, stage 2 to 20·B1):
     td 0.246 vs 0.232, p−1 s1 0.190 vs 0.177, dark 0.399 vs 0.375.
   - The remaining gap is the stage-2 bound: this tower uses 10·B1, NOTES 20·B1. Recomputed
     at 20·B1 from the stored q/B1, the tower gives s2 0.199 vs 0.216 and dark 0.365 vs
     0.375. Every lamp is then within about 0.02, which is sampling noise for 1,500 numbers
     (s.e. ≈ 0.011 per fraction).
   - Nothing is tuned toward NOTES.
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
| +42.8% / −6.4% (cost; chorus 1) | stage 2 appended to the stage-1 pipeline, plain, 72 bits: 100·B1 costs 42.8% more, 10·B1 saves 6.4% (NOTES writes savings as +: "+6.4 … 100: −42.8") | "Real-prime split-half search" (l. 4848) |
| +35.6% / −4.6% (chorus 2, 84-bit) | the same row at 84 bits | same |
| 402 / 247 (72), 386 / 225 (84) | stage-2 points lit at 100× / 10× | `data/tower.json` |
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
6. **Chorus 1 (72-bit) / chorus 2 (84-bit), arms: light against bill.** The long arm loses
   on cost, not on light.
   - **Long arm (100·B1):** it sweeps out and lights its stage-2 points. Beside the tower, a
     cost bar climbs past the qs line and turns red, labelled **"+42.8%"** on "forty-three",
     with its count small underneath: **402** stage-2 points at 72 bits.
   - **Short arm (10·B1):** it lights fewer stage-2 points, **247**. Its cost bar settles
     below the line, labelled **"−6.4%"**.
   - **Then:** the long arm's 155 extra points stay lit but grey out slightly (paid for, not
     worth it). The short arm's light-green wedge stays bright and keeps sweeping, once per
     bar.
   - **Sources:** both percentages are from NOTES, "Real-prime split-half search", appended
     to the stage-1 pipeline, plain, 72 bits. Both counts are from `data/tower.json`
     (`pm1_s2` under `lamp_100` vs `lamp`, 72 bits).
   - **Chorus 2 (84-bit tower):** the 84-bit figures from the same NOTES row, labelled
     "84-bit": +35.6% / −4.6%, with 386 / 225 stage-2 points (user, Oct 26). Both choruses
     are 11.8 bars, with a 4 s instrumental tail after "that's how the dark gets lit".
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
    orbiting slowly. Bloom follows the choir swell (smoothed rms + high band). The fan's outer
    edge is a real spiral (max angle = 2π(1 − 2·radius)): when the orbit passes a side-on
    view, the camera eases for a beat or two so the spiral edge reads clearly. On
    "forty-three" (3:17.00), the 72-bit band briefly shows its two cost bars again
    (+42.8% red, −6.4% under the line) for about one bar. Then they fade and the orbit
    continues. No new numbers.
11. **Outro.** "Twelve percent on the plain arm." / "Sealed before the run." are typed on
    the spoken words, and the text completes on "run" (3:43.58–3:44.46). The clock keeps
    ticking with the audio: one tick per detected tick, so picture and sound never disagree.
    It stops on the last audible tick (3:49.70), and the picture holds through the cut at
    3:50.87.

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

## Calls made while the user was away

Made under the standing go of Oct 26: decisions that PLAN.md didn't settle, each the
simplest one that fits the scene's description.

1. **Verse 4: the speckle is real ECM.** Each beat rolls the next of 48 seeded curves from
   `data/make_ecm.py` → `data/ecm.json`. Each is a Suyama curve with the card's bounds,
   B1 = 257 and B2 = 12,850 (NOTES I-017), run mod p on each of the 657 dark 96-bit
   points. The points it finds sparkle, about 136 per curve.
   - The first version stopped as soon as any intermediate multiple hit infinity, and
     disagreed with exact point orders on 12 of 300 test curves. It now uses exact
     arithmetic (infinity is a value, not an exit) and agrees 300/300 with the exact rule
     computed from each curve's point order.
2. **Verse 4: the floodlight starts on "But not tonight" (1:59.92).** That is new cue
   `not_tonight` in `sections.py`, the line that ends "the wall is cheap today". It washes
   only the band's disc, so the background stays black.
3. **Verse 4: the ticker eases out (quadratic) and reaches 8,187 on the cue frame.** That
   is frame 3329 for 1:50.98; it reads 8,184 a tenth of a second earlier.
4. **`render.py --section` now starts on the section's own first frame (t ≥ start).** It
   used to round the start time, so a preview could begin with the previous section's last
   frame. That showed up as a false regression in pre-chorus 2 once verse 4 stopped being
   black. Full renders were never affected.
5. **Bridge cues** from the transcript:
   - "The rim lights first" 2:40.88;
   - "spark" 2:43.58;
   - "A thousand rays" 2:45.18;
   - "Half of the numbers" 2:59.92;
   - "the other half" 3:02.94.

   The ray lights from the rim to its factor's radius (θ = 0.1991, 22.6% of the way in),
   arriving exactly on "spark". The spark lands on "a thousand rays". The tower's 2,898 lit
   points light rim-first:
   - half A from 2:45.5 to 2:58.4;
   - half A pulses once on "half of the numbers chose the road";
   - half B lights between 3:02.94 and 3:04.7, with a white check flare.

   The 1,602 dark points and the spine stay grey. A thin grey line divides the two panels.
6. **Final chorus: what "side-on" means.** The orbit runs at 22° elevation. Around 3:23 it
   slows to 15% speed (gaussian, half-width 0.3 rad) while the camera looks across the
   spiral edge at data radius 0.2, whose edge angle is 2π(1 − 2·0.2).
7. **Final chorus: what "brightest moment" means.** "The tower's lit" (3:30.12) is the
   moment the *tower's own light* is brightest: point brightness ×(1 + 0.9), bloom gain up
   to 2.6, decaying over 2.5 s. By whole-frame mean luma it can't be the film's brightest
   frame:
   - the pre-chorus grey static averages 121/255 over a second;
   - the "yes" and rho-detection flashes peak at 226–229;
   - the tower on black peaks at a mean of about 19.

   A full-frame white-out long enough to beat those would break "on black" and the flash
   rules, so I didn't add one.
