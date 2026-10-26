"""Sync: the section map and the music-driven uniforms, at 30 fps video frames.

Copied from laser-beam-demo's sync.py. Kept: the section lookup, interpolated features,
beat phase, kick pulses on strong onsets (at most one per KICK_GAP, under 3 per second),
and integrated speeds (travel), so motion follows loudness without ever jumping.
Dropped: tape wobble, the bone flashes on big onsets (here a white flash happens only on a
named cue, such as the pre-chorus's "yes"), the outro collapse and tape stop.
Added: the quartet bands normalised within the pre-choruses, the clock ticks of the intro
and outro (count and phase), the choir swell, and the word cues.
"""
import json, os
import numpy as np

FPS = 30
KICK_MIN = 0.55                  # onset strength (0..1 among onsets) that lifts the glow
KICK_GAP = 0.34                  # s between kick pulses, at least: under 3 per second
TRAVEL = (0.35, 2.2)             # orbit / build speed = a + b * rms (smoothed 0.25 s), per s
QUIET = {"intro", "prechorus1", "prechorus2", "outro"}      # no kick lift
QUARTET = ("q_bass", "q_bari", "q_lead", "q_tenor")
QUARTET_SECTIONS = ("prechorus1", "prechorus2")
SWELL_SMOOTH = 1.0               # s; the choir swell is rms + high, smoothed this much
FLASH_DECAY = 0.12               # s; the white flash on a cue
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, "cache")

def boxcar(x, seconds, fps=FPS):
    n = max(1, int(seconds * fps))
    return np.convolve(np.pad(x, (n // 2, n - n // 2 - 1), mode="edge"), np.ones(n) / n, mode="valid")

class Sync:
    def __init__(self, features=os.path.join(CACHE, "features.json"),
                 sections=os.path.join(CACHE, "sections.json")):
        f = json.load(open(features))
        self.ffps = f["fps"]
        self.duration = f["duration"]
        self.tempo = f["tempo"]
        self.beat_t = np.array(f["beats"])
        for k in ("rms", "low", "mid", "high", "onset_strength", "centroid_slow"):
            setattr(self, k, np.array(f[k], "f4"))
        self.onset_t = np.nonzero(np.array(f["onset"]))[0] / self.ffps
        sm = json.load(open(sections))
        self.sections = sm["sections"]
        self.cues = {c["name"]: c["t"] for c in sm["cues"]}
        self.tick_t = np.array(sm["ticks"])
        self.music_end = sm["music_end"]
        self.n_frames = int(round(self.duration * FPS))
        self.by_name = {s["name"]: s for s in self.sections}

        # quartet: each band's 5th-95th percentile over the pre-choruses only -> 0..1
        sl = [slice(int(self.by_name[n]["start"] * self.ffps), int(self.by_name[n]["end"] * self.ffps))
              for n in QUARTET_SECTIONS if n in self.by_name]
        self.quartet = []
        for k in QUARTET:
            x = np.array(f[k], "f4")
            ref = np.concatenate([x[s] for s in sl]) if sl else x
            a, b = np.percentile(ref, 5), np.percentile(ref, 95)
            self.quartet.append(np.clip((x - a) / (b - a + 1e-9), 0, 1))

        # kick pulses: strong onsets anywhere the music plays, spaced under 3 per second
        idx = (self.onset_t * self.ffps).round().astype(int)
        st = self.onset_strength[idx]
        self.kick_t, self.kick_s, last = [], [], -1e9
        for t, v in zip(self.onset_t, st):
            if v >= KICK_MIN and t - last >= KICK_GAP and t < self.music_end:
                self.kick_t.append(t); self.kick_s.append(float(v)); last = t
        self.kick_t, self.kick_s = np.array(self.kick_t), np.array(self.kick_s)

        # travel: integral of an rms-driven speed, so it follows the music and never jumps
        s = boxcar(self.rms, 0.25, self.ffps)
        self.travel = np.r_[0, np.cumsum(TRAVEL[0] + TRAVEL[1] * s)[:-1]] / self.ffps
        sw = boxcar(0.6 * self.rms + 0.4 * self.high, SWELL_SMOOTH, self.ffps)
        self.swell = np.clip(sw / (np.percentile(sw, 99) + 1e-9), 0, 1)

    def at(self, arr, t):
        """arr (at the features' frame rate) at time t, linearly interpolated."""
        x = min(len(arr) - 1.0, max(0.0, t * self.ffps))
        i = int(x); j = min(len(arr) - 1, i + 1)
        return float(arr[i] + (arr[j] - arr[i]) * (x - i))

    def since(self, times, t):
        i = np.searchsorted(times, t, side="right") - 1
        return 1e3 if i < 0 else float(t - times[i])

    def section(self, t):
        for s in self.sections:
            if s["start"] <= t < s["end"]:
                return s
        return self.sections[-1]

    def beat(self, t):
        """(beats elapsed as a float, seconds since the last beat)."""
        b = self.beat_t
        i = int(np.searchsorted(b, t, side="right")) - 1
        if i < 0:
            return t / (b[0] if b[0] > 0 else 1) - 1.0, 1e3
        nxt = b[i + 1] if i + 1 < len(b) else b[i] + 60 / self.tempo
        return i + (t - b[i]) / (nxt - b[i]), float(t - b[i])

    def cue(self, name, t):
        """Seconds since the named cue (negative before it; -1e3 if the cue is not set)."""
        return t - self.cues[name] if name in self.cues else -1e3

    def ticks(self, s, t):
        """(ticks so far in section s, seconds since the last one, ticks in the section)."""
        m = (self.tick_t >= s["start"]) & (self.tick_t < s["end"])
        tt = self.tick_t[m]
        return int(np.searchsorted(tt, t, side="right")), self.since(tt, t), int(len(tt))

    def uniforms(self, t):
        s = self.section(t)
        ki = np.searchsorted(self.kick_t, t, side="right") - 1
        beat, since_beat = self.beat(t)
        n_tick, since_tick, ticks_total = self.ticks(s, t)
        u = {"t": t, "ts": t - s["start"], "sdur": s["end"] - s["start"],
             "local": (t - s["start"]) / (s["end"] - s["start"]),
             "rms": self.at(self.rms, t), "low": self.at(self.low, t),
             "mid": self.at(self.mid, t), "high": self.at(self.high, t),
             "phrase": self.at(self.centroid_slow, t), "swell": self.at(self.swell, t),
             "beat": beat, "since_beat": since_beat,
             "kick": 0.0 if ki < 0 or s["name"] in QUIET
                     else self.kick_s[ki] * float(np.exp(-(t - self.kick_t[ki]) / 0.12)),
             "travel": self.at(self.travel, t),
             "quartet": tuple(self.at(q, t) for q in self.quartet),
             "n_tick": n_tick, "since_tick": since_tick, "ticks_total": ticks_total,
             "music": 1.0 if t < self.music_end else 0.0}
        return u

if __name__ == "__main__":
    s = Sync()
    print(f"{s.duration:.3f} s, {s.n_frames} frames @ {FPS} fps, {len(s.onset_t)} onsets, "
          f"{len(s.beat_t)} beats, {len(s.tick_t)} ticks, cues {sorted(s.cues)}")
    g = np.diff(s.kick_t)
    print(f"kick pulses {len(s.kick_t)} of {len(s.onset_t)} onsets; min gap {g.min():.2f} s "
          f"({1 / g.min():.2f}/s max)")
    for n in QUARTET_SECTIONS:
        x = s.by_name[n]
        a, b = int(x["start"] * s.ffps), int(x["end"] * s.ffps)
        q = np.stack([v[a:b] for v in s.quartet])
        c = np.corrcoef(q)
        print(f"{n}: quartet means " + " ".join(f"{v:.2f}" for v in q.mean(1)) +
              "; max pairwise r " + f"{max(c[i, j] for i in range(4) for j in range(i + 1, 4)):.2f}")
    print(f"swell: final chorus mean {np.mean([s.at(s.swell, t) for t in np.arange(193.6, 221, 0.5)]):.2f}, "
          f"verse 1 mean {np.mean([s.at(s.swell, t) for t in np.arange(8.6, 60, 0.5)]):.2f}")
