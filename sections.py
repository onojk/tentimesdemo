#!/usr/bin/env python3
"""sections.py — cache/features.json -> cache/sections.json, and print the section map.

    .venv/bin/python sections.py

Copied from laser-beam-demo's sections.py. Boundaries are read off the features (novelty
peaks, bass dropouts, chroma repeats; each one's reason is kept in "why"), then snapped to
the nearest tracked beat within half a second, so every hard cut lands on a beat.
Word cues (CUES) are the moments a scene hits on a sung or spoken word; they are not
snapped. Clock ticks are the tick candidates in the intro and outro that sit on the
half-beat grid.

Confirmed against a transcript of the song (faster-whisper medium.en, word timestamps,
Oct 26); every section starts on its first sung word.
"""
import json, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FEATURES = os.path.join(HERE, "cache", "features.json")
OUT = os.path.join(HERE, "cache", "sections.json")
TICK_ON_GRID = 0.05               # s from the half-beat grid
TICK_SECTIONS = {"intro", "outro"}

# (name, scene, start s, why): each start is the first sung word (or vocal fill) of the
# section, from the transcript, snapped to the nearest beat
RAW = [
    ("intro",        "ray",      0.0,    "ticks only, -30 dBFS"),
    ("verse1",       "assemble", 7.28,   "'I built a tower' (pickup 'I' 7.28, 'built' 8.20)"),
    ("verse2",       "flap",     36.54,  "'ah' fill 36.54, then 'I swore the line' 38.76; novelty 0.31"),
    ("prechorus1",   "quartet",  56.38,  "'No warmer, no colder'"),
    ("chorus1",      "arms",     61.56,  "'Ten times, not a hundred'; novelty 0.35"),
    ("verse3",       "rho",      88.50,  "'The rho lamp counts its footsteps', after the 4 s bass dropout"),
    ("verse4",       "ecm",      106.70, "'The curves came in'; novelty 0.40"),
    ("prechorus2",   "quartet",  124.48, "'No warmer, no colder'"),
    ("chorus2",      "arms",     129.90, "'Ten times, not a hundred'"),
    ("bridge",       "bridge",   156.62, "'One number's line', after the bass dropout; novelty 0.91"),
    ("final_chorus", "finale",   185.14, "'da da' fill 185.14, 'Ten times' 189.00; novelty 0.63"),
    ("outro",        "outro",    217.38, "spoken 'Twelve percent on the plain arm' (217.38)"),
]
# (name, time s, why): word starts from the transcript (faster-whisper medium.en, word
# timestamps), not snapped; scenes hit on these
CUES = [
    ("three_point_four", 44.92,  "verse 2 'three-point-four' (44.92-46.02)"),
    ("one_point_four",   50.02,  "verse 2 'one-point-four' (50.02-51.56)"),
    ("static1_on",       56.38,  "pre-chorus 1 'No warmer, no colder' starts"),
    ("static1_off",      58.56,  "'colder' ends"),
    ("yes1",             61.12,  "pre-chorus 1 'yes'"),
    ("forty_three1",     69.48,  "chorus 1 'forty-three' (69.48-70.78)"),
    ("meeting",          103.64, "verse 3 'meeting place' ('twice as far' 102.26)"),
    ("eight_thousand",   110.98, "verse 4 'eight thousand' (110.98-111.88)"),
    ("not_tonight",      119.92, "verse 4 'But not tonight' (the floodlight; 'the wall is cheap today' 122.70)"),
    ("static2_on",       124.48, "pre-chorus 2 'No warmer, no colder' starts"),
    ("static2_off",      126.78, "'colder' ends"),
    ("yes2",             129.42, "pre-chorus 2 'yes'"),
    ("forty_three2",     137.68, "chorus 2 'forty-three' (137.68-139.02)"),
    ("forty_three3",     197.00, "final chorus 'forty-three' (197.00-198.06)"),
    ("tower_lit",        210.12, "final chorus tag 'and the tower's lit' (x3, to 217.38)"),
    ("outro_line1",      217.38, "'Twelve percent on the plain arm' (217.38-219.86)"),
    ("outro_line2",      220.78, "'Sealed before the run' (220.78-224.46)"),
    ("last_word",        223.58, "'run' (223.58-224.46): the typed text completes; the clock ticks on to the last tick"),
]
MUSIC_END_RAW = 230.87            # last tracked beat; -26 -> -83 dBFS within a second

def build():
    f = json.load(open(FEATURES))
    beats = np.array(f["beats"])
    secs = []
    for name, scene, t, why in RAW:
        snapped = t
        if t > 0:
            b = beats[np.argmin(np.abs(beats - t))]
            if abs(b - t) <= 0.5:
                snapped = float(b)
        secs.append({"name": name, "scene": scene, "start": round(snapped, 3),
                     "raw": t, "why": why})
    for i, s in enumerate(secs):
        s["end"] = secs[i + 1]["start"] if i + 1 < len(secs) else round(f["duration"], 3)
    k = int(np.argmin(np.abs(beats - MUSIC_END_RAW)))
    music_end = round(float(beats[k]), 3)
    tk = f["ticks"]
    ticks = [t for t, o in zip(tk["t"], tk["grid_offset"])
             if o <= TICK_ON_GRID and any(s["name"] in TICK_SECTIONS and s["start"] <= t < s["end"]
                                          for s in secs) and t < music_end]
    json.dump({"source": "cache/features.json", "confirmed": "transcript, 2026-10-26", "sections": secs,
               "cues": [{"name": n, "t": t, "why": w} for n, t, w in CUES],
               "ticks": ticks, "music_end": music_end},
              open(OUT, "w"), indent=1)
    return f, secs, ticks, music_end

def mmss(t):
    return f"{int(t // 60)}:{t % 60:05.2f}"

if __name__ == "__main__":
    f, secs, ticks, music_end = build()
    fps = f["fps"]
    rms, onset, high, low = (np.array(f[k]) for k in ("rms", "onset", "high", "low"))
    beats = np.array(f["beats"])
    bar = 4 * 60 / f["tempo"]
    print(f"tempo {f['tempo']:.2f} bpm, bar {bar:.3f} s, duration {f['duration']:.3f} s, "
          f"{len(secs)} sections\n")
    print(f"{'#':>2} {'name':13s} {'scene':9s} {'start':>8s} {'end':>8s} {'len':>6s} {'bars':>5s} "
          f"{'snap':>6s} {'beats':>5s} {'ons':>4s} {'rms':>5s} {'low':>5s} {'high':>5s}")
    for i, s in enumerate(secs):
        a, b = int(s["start"] * fps), int(s["end"] * fps)
        nb = int(((beats >= s["start"]) & (beats < s["end"])).sum())
        print(f"{i + 1:2d} {s['name']:13s} {s['scene']:9s} {mmss(s['start']):>8s} {mmss(s['end']):>8s} "
              f"{s['end'] - s['start']:5.1f}s {(s['end'] - s['start']) / bar:5.1f} "
              f"{s['start'] - s['raw']:+6.2f} {nb:5d} {int(onset[a:b].sum()):4d} "
              f"{rms[a:b].mean():5.2f} {low[a:b].mean():5.2f} {high[a:b].mean():5.2f}")
    for name in TICK_SECTIONS:
        s = next(x for x in secs if x["name"] == name)
        tt = [t for t in ticks if s["start"] <= t < s["end"]]
        if tt:
            print(f"\n{name} ticks: {len(tt)}, {mmss(tt[0])} .. {mmss(tt[-1])}")
    for c in CUES:
        print(f"cue {c[0]:14s} {mmss(c[1])}  {c[2]}")
    print(f"music ends {mmss(music_end)}\nwrote {OUT}")
