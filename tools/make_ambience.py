import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 22050
LOOP = 12.0
FADE = 0.4
N = int(SR * LOOP)
OUT = Path(__file__).resolve().parent.parent / "loophole" / "data" / "sfx"


def shaped_noise(rng, lo, hi, slope=0.0, n=N):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    band = np.exp(-0.5 * (np.log(np.maximum(f, 1) / np.sqrt(lo * hi)) / (np.log(hi / lo) / 2.6)) ** 2)
    tilt = np.where(f > 0, (np.maximum(f, 1) / 1000.0) ** (-slope / 2), 0)
    x = np.fft.irfft(spec * band * tilt, n)
    return x / (np.abs(x).max() + 1e-12)


def periodic_env(rng, cycles, depth, n=N):
    t = np.arange(n) / n
    e = np.zeros(n)
    for c in cycles:
        e += rng.uniform(0.4, 1.0) * np.sin(2 * np.pi * (c * t + rng.random()))
    e /= np.abs(e).max() + 1e-12
    return 1.0 - depth + depth * (0.5 + 0.5 * e)


def place(buf, sig, at):
    idx = (at + np.arange(len(sig))) % len(buf)
    np.add.at(buf, idx, sig)


def sweep(f0, f1, dur, curve=1.0, harm=0.15):
    n = int(dur * SR)
    t = np.linspace(0, 1, n)
    f = f0 + (f1 - f0) * t ** curve
    ph = 2 * np.pi * np.cumsum(f) / SR
    env = np.sin(np.pi * t) ** 1.5
    return env * (np.sin(ph) + harm * np.sin(2 * ph))


def wind(rng):
    x = shaped_noise(rng, 70, 700, slope=1.2) * periodic_env(rng, [1, 2, 3, 5], 0.75)
    for fc, cyc in ((420, [2, 3]), (610, [3, 5]), (880, [4, 7])):
        x += 0.22 * shaped_noise(rng, fc * 0.93, fc * 1.07) * periodic_env(rng, cyc, 1.0) ** 2
    return x


def water(rng):
    x = 0.04 * shaped_noise(rng, 1800, 7000) * periodic_env(rng, [7, 11, 13], 0.6)
    at = 0
    while at < N:
        dur = rng.uniform(0.7, 1.4)
        n = int(dur * SR)
        t = np.arange(n) / SR
        env = (1 - np.exp(-t / 0.12)) * np.exp(-t / (dur * 0.35))
        slosh = shaped_noise(rng, 180, 900, slope=0.6, n=n) * env * rng.uniform(0.5, 1.0)
        splash = shaped_noise(rng, 1200, 4500, n=n) * np.exp(-t / 0.09) * (1 - np.exp(-t / 0.01)) * rng.uniform(0.1, 0.35)
        place(x, slosh + splash, at)
        at += int(rng.uniform(1.3, 2.8) * SR)
    return x


def birds(rng):
    x = 0.02 * shaped_noise(rng, 1500, 7000) * periodic_env(rng, [1, 2, 4], 0.7)
    t = 0.3
    while t < LOOP:
        kind = rng.integers(0, 4)
        amp = rng.uniform(0.25, 1.0)
        base = rng.uniform(0.85, 1.2)
        call = []
        if kind == 0:
            for _ in range(rng.integers(4, 9)):
                call.append(sweep(4600 * base, 3100 * base, 0.045))
                call.append(np.zeros(int(0.03 * SR)))
        elif kind == 1:
            call += [sweep(2500 * base, 3400 * base, 0.24, 0.6), np.zeros(int(0.05 * SR)), sweep(2300 * base, 2200 * base, 0.2)]
        elif kind == 2:
            for _ in range(3):
                call += [sweep(3000 * base, 5200 * base, 0.08, 2.0), np.zeros(int(0.11 * SR))]
        else:
            call += [sweep(3600 * base, 3550 * base, 0.35, 1.0, 0.05) * (1 + 0.6 * np.sin(np.linspace(0, 2 * np.pi * 28, int(0.35 * SR))))]
        sig = np.concatenate(call) * amp
        wet = np.zeros(len(sig) + int(0.25 * SR))
        wet[:len(sig)] += sig
        for d, g in ((0.043, 0.25), (0.091, 0.15), (0.17, 0.08)):
            k = int(d * SR)
            wet[k:k + len(sig)] += sig * g
        place(x, wet * 0.5, int(t * SR))
        t += rng.uniform(0.5, 1.8)
    return x


def fire(rng):
    x = 0.45 * shaped_noise(rng, 40, 260, slope=1.0) * periodic_env(rng, [1, 3, 4, 6], 0.6)
    x += 0.12 * shaped_noise(rng, 600, 3000) * periodic_env(rng, [5, 9], 0.8)
    rate = periodic_env(rng, [2, 3], 0.8)
    for i in range(N):
        if rng.random() < 18.0 / SR * rate[i]:
            n = int(rng.uniform(0.002, 0.012) * SR) + 1
            pop = rng.standard_normal(n) * np.exp(-np.arange(n) / (n / 4)) * rng.uniform(0.2, 1.0) ** 2
            place(x, pop, i)
    return x


def hum(rng):
    t = np.arange(N) / SR
    x = np.zeros(N)
    for h, a in ((60, 1.0), (120, 0.55), (180, 0.3), (240, 0.18), (300, 0.08)):
        x += a * np.sin(2 * np.pi * h * t + rng.random() * 6.28)
    x *= periodic_env(rng, [1, 2], 0.15)
    x = 0.5 * x / np.abs(x).max() + 0.35 * shaped_noise(rng, 90, 500, slope=0.8)
    return x


def finish(x, level):
    x = x - x.mean()
    x = x / (np.sqrt(np.mean(x ** 2)) + 1e-12) * level
    x = np.clip(x, -0.95, 0.95)
    f = int(FADE * SR)
    y = np.concatenate([x, x[:f]])
    w = np.ones(len(y))
    w[:f] = np.linspace(0, 1, f)
    w[-f:] = np.linspace(1, 0, f)
    return y * w


def main():
    rng = np.random.default_rng(7)
    sounds = {"wind": (wind, 0.16), "water": (water, 0.17), "birds": (birds, 0.13), "fire": (fire, 0.17),
              "hum": (hum, 0.15)}
    man_path = OUT / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    lame = shutil.which("lame")
    with tempfile.TemporaryDirectory() as tmp:
        for name, (fn, level) in sounds.items():
            y = finish(fn(rng), level)
            wav = Path(tmp) / f"{name}.wav"
            with wave.open(str(wav), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes((y * 32767).astype("<i2").tobytes())
            mp3 = OUT / f"amb_{name}.mp3"
            if lame:
                subprocess.run([lame, "--quiet", "-m", "m", "-b", "48", str(wav), str(mp3)], check=True)
            else:
                subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "48k", str(mp3)],
                               check=True)
            man[f"amb_{name}"] = [SR, len(y)]
            print(name, mp3.stat().st_size // 1024, "KB")
    man_path.write_text(json.dumps(man, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
