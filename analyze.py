#!/usr/bin/env python3
"""analyze.py — song -> cache/features.json, using ffmpeg and numpy only.

    .venv/bin/python analyze.py audio/ten_times.wav [--out cache/features.json]

Copied from laser-beam-demo's analyze.py: same rms / spectral-flux onsets / slow centroid /
tempo / beats / bands / novelty; its tape-wobble estimate is dropped (this song has none).
Added for this film:

    tempo, beats    autocorrelation of the onset envelope, then Ellis dynamic-programming
                    beat tracking on that period
    low/mid/high    band energies (< 250 Hz, 250-2000 Hz, > 2000 Hz), each normalised
    quartet         four voice bands for the barbershop pre-chorus, as raw log energies
                    (bass 70-180, baritone 180-300, lead 300-500, tenor 500-900 Hz); sync.py
                    normalises them within the pre-choruses, where they are used
    ticks           clock-tick candidates: peaks of the > 4 kHz spectral flux, with their
                    distance to the half-beat grid (the ticks run in eighth notes); sections.py
                    keeps the ones in the intro and outro that sit on the grid
    chroma          beat-synchronous chroma, mean-centred and unit-norm, for the repeat check
    novelty         checkerboard novelty over a beat-synchronous self-similarity matrix
                    (log band energies + chroma); its peaks are the section candidates

Frames are centred (frame i covers time i / fps), and the duration comes from the sample
count, not the frame count, so nothing drifts against the audio.
"""
import argparse, json, os, subprocess, sys
import numpy as np

SR = 22050
FPS = 30                      # 22050 / 30 = 735 samples per frame exactly
WIN = 2048
QUARTET = {"q_bass": (70, 180), "q_bari": (180, 300), "q_lead": (300, 500), "q_tenor": (500, 900)}
TICK_ON_GRID = 0.05           # s; a tick this close to a half-beat counts as on the grid
HERE = os.path.dirname(os.path.abspath(__file__))

def decode(path):
    p = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-acodec", "pcm_f32le",
                        "-ac", "1", "-ar", str(SR), "-"], capture_output=True)
    if p.returncode != 0:
        sys.exit(f"ffmpeg failed: {p.stderr.decode()[:400]}")
    return np.frombuffer(p.stdout, dtype=np.float32)

def boxcar(x, seconds, fps=FPS):
    n = max(1, int(seconds * fps))
    return np.convolve(np.pad(x, (n // 2, n - n // 2 - 1), mode="edge"), np.ones(n) / n, mode="valid")

def norm(x, lo=2.0, hi=98.0):
    a, b = np.percentile(x, lo), np.percentile(x, hi)
    return np.clip((x - a) / (b - a + 1e-9), 0, 1) if b > a else np.zeros_like(x)

def stft(y, hop, win):
    yp = np.pad(y, (win // 2, win // 2))
    n = int(np.ceil(len(y) / hop))
    w = np.hanning(win).astype(np.float32)
    idx = np.arange(win)[None, :] + hop * np.arange(n)[:, None]
    yp = np.pad(yp, (0, max(0, idx.max() + 1 - len(yp))))
    frames = yp[idx] * w
    mag = np.empty((n, win // 2 + 1), np.float32)
    for i in range(0, n, 512):                                    # chunks: bounded memory
        mag[i:i + 512] = np.abs(np.fft.rfft(frames[i:i + 512], axis=1))
    return mag, frames

def tempo(env, lo=50, hi=180):
    """Autocorrelation of the onset envelope over lo..hi bpm, weighted to ~90 bpm (log-normal)."""
    e = env - env.mean()
    ac = np.correlate(e, e, "full")[len(e) - 1:]
    lags = np.arange(int(60 * FPS / hi), int(60 * FPS / lo) + 1)
    bpm = 60 * FPS / lags
    score = ac[lags] * np.exp(-0.5 * (np.log2(bpm / 90) / 1.0) ** 2)
    best = lags[np.argmax(score)]
    # parabolic refinement of the lag
    a, b, c = ac[best - 1], ac[best], ac[best + 1]
    frac = 0.5 * (a - c) / (a - 2 * b + c + 1e-12)
    raw = sorted(zip(ac[lags], bpm), reverse=True)[:5]
    return 60 * FPS / (best + frac), [(round(float(b_), 1), float(s)) for s, b_ in raw]

def beat_track(env, period, tightness=100.0):
    """Ellis 2007: DP over the onset envelope with a log-gap penalty around `period` frames."""
    env = env / (env.std() + 1e-9)
    n = len(env)
    score, back = env.copy(), -np.ones(n, int)
    p = period
    lo, hi = int(round(0.5 * p)), int(round(2 * p))
    for i in range(hi, n):
        prev = np.arange(i - hi, i - lo + 1)
        pen = -tightness * np.log((i - prev) / p) ** 2
        j = np.argmax(score[prev] + pen)
        score[i] = env[i] + score[prev[j]] + pen[j]
        back[i] = prev[j]
    # end on the best-scoring frame in the last period
    i = n - hi + int(np.argmax(score[n - hi:]))
    beats = []
    while i >= 0:
        beats.append(i); i = back[i]
    return np.array(beats[::-1])

def chroma(mag, freqs):
    m = (freqs > 60) & (freqs < 4000)
    pc = np.round(12 * np.log2(freqs[m] / 440.0)).astype(int) % 12
    c = np.zeros((mag.shape[0], 12), np.float32)
    for k in range(12):
        c[:, k] = mag[:, m][:, pc == k].sum(axis=1)
    return c / (np.linalg.norm(c, axis=1, keepdims=True) + 1e-9)

def logbands(mag, freqs, n=24):
    edges = np.geomspace(40, 10000, n + 1)
    b = np.stack([mag[:, (freqs >= edges[k]) & (freqs < edges[k + 1])].sum(axis=1)
                  for k in range(n)], axis=1)
    b = np.log1p(b)
    return (b - b.mean(0)) / (b.std(0) + 1e-9)

def novelty(feat, half):
    """Foote checkerboard novelty on the cosine self-similarity of `feat` (rows = beats)."""
    f = feat / (np.linalg.norm(feat, axis=1, keepdims=True) + 1e-9)
    S = f @ f.T
    g = np.arange(-half, half) + 0.5
    k = np.sign(g)[:, None] * np.sign(g)[None, :] * np.exp(-(g[:, None] ** 2 + g[None, :] ** 2) / (2 * (half / 2) ** 2))
    n = len(S)
    Sp = np.pad(S, half, mode="edge")
    nov = np.array([(Sp[i:i + 2 * half, i:i + 2 * half] * k).sum() for i in range(n)])
    return np.maximum(nov, 0) / (nov.max() + 1e-9)

def ticks(mag, freqs, beats):
    """Clock-tick candidates: peaks of the > 4 kHz flux over a local threshold, each with its
    strength and its distance (s) to the nearest half-beat (beats and the midpoints between)."""
    hf = np.r_[0, np.maximum(np.diff(np.log1p(mag[:, freqs >= 4000]), axis=0), 0).sum(1)]
    thr = 2.0 * boxcar(hf, 1.0) + 0.3 * np.std(hf)
    pk = np.array([i for i in range(1, len(hf) - 1)
                   if hf[i] > thr[i] and hf[i] >= hf[i - 1] and hf[i] > hf[i + 1]])
    grid = np.sort(np.r_[beats, 0.5 * (beats[1:] + beats[:-1])]) / FPS
    t = pk / FPS
    off = np.abs(t[:, None] - grid[None, :]).min(axis=1)
    return t, norm(hf[pk] - thr[pk], 5, 95), off

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--out", default=os.path.join(HERE, "cache", "features.json"))
    a = ap.parse_args()

    y = decode(a.wav)
    dur = len(y) / SR
    print(f"decoded {a.wav}\n  {len(y)} samples @ {SR} Hz mono = {dur:.3f} s")
    hop = SR // FPS
    mag, frames = stft(y, hop, WIN)
    n = mag.shape[0]
    freqs = np.fft.rfftfreq(WIN, 1 / SR)
    print(f"  stft: {n} frames @ {FPS} fps (hop {hop}, win {WIN}) -> {n / FPS:.3f} s")

    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    cen = (mag * freqs).sum(1) / (mag.sum(1) + 1e-9)
    band = lambda f0, f1: np.sqrt((mag[:, (freqs >= f0) & (freqs < f1)] ** 2).sum(1))
    low, mid, high = band(20, 250), band(250, 2000), band(2000, 11025)
    logmag = np.log1p(mag)
    flux = np.r_[0, np.maximum(np.diff(logmag, axis=0), 0).sum(1)]

    # onsets: adaptive threshold peak picking on the flux (extract.py's rule)
    med = boxcar(flux, 0.35)
    thr = med * 1.55 + 0.6 * np.std(flux)
    onset = np.zeros(n, np.float32)
    last = -99
    for i in range(1, n - 1):
        if flux[i] > thr[i] and flux[i] >= flux[i - 1] and flux[i] > flux[i + 1] and i - last > 2:
            onset[i] = 1.0; last = i
    # strength: flux over its local median, normalised among the onsets themselves (over all
    # frames nearly every onset would saturate at 1)
    strength = np.zeros(n, np.float32)
    strength[onset > 0] = norm((flux - med)[onset > 0], 5, 95)

    env = np.maximum(flux - boxcar(flux, 1.0), 0)
    bpm, cands = tempo(env)
    beats = beat_track(env, 60 * FPS / bpm)
    ibi = np.diff(beats) / FPS
    print(f"tempo: {bpm:.2f} bpm  (top autocorrelation lags: {cands})")
    print(f"beats: {len(beats)}  first {beats[0] / FPS:.2f} s  last {beats[-1] / FPS:.2f} s  "
          f"inter-beat {ibi.mean():.3f} +/- {ibi.std():.3f} s ({60 / ibi.mean():.1f} bpm)")
    print(f"onsets: {int(onset.sum())} ({onset.sum() / dur:.2f}/s)")

    # quartet bands, raw log energy (sync.py normalises them within the pre-choruses)
    quartet = {k: np.log1p(band(f0, f1)) for k, (f0, f1) in QUARTET.items()}
    qc = np.corrcoef(np.stack(list(quartet.values())))
    print("quartet band correlation (whole song): " + ", ".join(
        f"{a_[2:]}/{b_[2:]} {qc[i, j]:.2f}" for i, a_ in enumerate(QUARTET)
        for j, b_ in enumerate(QUARTET) if j > i))

    tick_t, tick_s, tick_off = ticks(mag, freqs, beats)
    print(f"tick candidates: {len(tick_t)}, {int((tick_off <= TICK_ON_GRID).sum())} on the half-beat grid")

    # beat-synchronous features -> novelty (two scales: 8 beats and 16 beats)
    feat = np.hstack([logbands(mag, freqs), 1.5 * chroma(mag, freqs)])
    edges = np.r_[0, beats, n]
    bfeat = np.stack([feat[edges[i]:max(edges[i] + 1, edges[i + 1])].mean(0) for i in range(len(edges) - 1)])
    btimes = edges[:-1] / FPS
    nov = 0.5 * novelty(bfeat, 8) + 0.5 * novelty(bfeat, 16)
    bchroma = bfeat[:, -12:] - bfeat[:, -12:].mean(0)
    bchroma /= np.linalg.norm(bchroma, axis=1, keepdims=True) + 1e-9

    out = {"source": os.path.basename(a.wav), "sr": SR, "fps": FPS, "duration": dur, "n_frames": n,
           "tempo": round(bpm, 3), "beats": (beats / FPS).round(4).tolist(),
           "rms": norm(rms).round(4).tolist(),
           "rms_raw_dbfs": (20 * np.log10(rms + 1e-9)).round(2).tolist(),
           "onset": onset.astype(int).tolist(), "onset_strength": strength.round(4).tolist(),
           "low": norm(low).round(4).tolist(), "mid": norm(mid).round(4).tolist(),
           "high": norm(high).round(4).tolist(),
           "centroid_slow": norm(boxcar(cen, 4.0)).round(4).tolist(),
           "centroid_vslow": norm(boxcar(cen, 25.0)).round(4).tolist(),
           **{k: v.round(4).tolist() for k, v in quartet.items()},
           "ticks": {"t": tick_t.round(4).tolist(), "strength": tick_s.round(4).tolist(),
                     "grid_offset": tick_off.round(4).tolist()},
           "beat_chroma": bchroma.round(4).tolist(),
           "novelty": {"t": btimes.round(4).tolist(), "v": nov.round(4).tolist()}}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    json.dump(out, open(a.out, "w"))
    print(f"wrote {a.out} ({os.path.getsize(a.out) / 1e6:.2f} MB)")

if __name__ == "__main__":
    main()
