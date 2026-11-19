import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

SR = 22050
OUT = Path(__file__).resolve().parent.parent / "loophole" / "data" / "sfx"


def band_noise(rng, n, lo, hi):
    spec = np.fft.rfft(rng.standard_normal(n))
    f = np.fft.rfftfreq(n, 1 / SR)
    spec[(f < lo) | (f > hi)] = 0
    x = np.fft.irfft(spec, n)
    return x / (np.abs(x).max() + 1e-12)


def engine(rng, loop=2.0, fade=0.06):
    n = int(SR * loop)
    f0 = 80.0
    cyc = round(f0 * loop)
    f0 = cyc / loop
    t = np.arange(n) / SR
    ph = 2 * np.pi * f0 * t
    x = np.zeros(n)
    for h, a in ((1, 1.0), (2, 0.62), (3, 0.45), (4, 0.3), (5, 0.22), (6, 0.12), (8, 0.07)):
        x += a * np.sin(h * ph + h * 0.7)
    fire = 0.5 + 0.5 * np.sin(ph / 2)
    x *= 0.75 + 0.25 * fire ** 3
    x += 0.18 * band_noise(rng, n, 300, 2400) * (0.4 + 0.6 * fire)
    x = np.tanh(x * 0.9)
    x -= x.mean()
    x = x / (np.sqrt(np.mean(x ** 2)) + 1e-12) * 0.2
    f = int(fade * SR)
    y = np.concatenate([x, x[:f]])
    w = np.ones(len(y))
    w[:f] = np.linspace(0, 1, f)
    w[-f:] = np.linspace(1, 0, f)
    return y * w


def skid(rng, dur=0.55):
    n = int(SR * dur)
    t = np.arange(n) / SR
    squeal = np.sin(2 * np.pi * np.cumsum(950 + 60 * np.sin(2 * np.pi * 7 * t)) / SR)
    squeal += 0.4 * np.sin(2 * np.pi * np.cumsum(1900 + 90 * np.sin(2 * np.pi * 5 * t)) / SR)
    x = 0.55 * squeal + 0.6 * band_noise(rng, n, 1200, 5000)
    env = np.minimum(1, t / 0.04) * np.minimum(1, (dur - t) / 0.12)
    x = x * env
    return np.clip(x / (np.abs(x).max() + 1e-12) * 0.32, -0.95, 0.95)


def write(name, y, man, lame):
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / f"{name}.wav"
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
        mp3 = OUT / f"{name}.mp3"
        if lame:
            subprocess.run([lame, "--quiet", "-m", "m", "-b", "48", str(wav), str(mp3)], check=True)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(wav), "-ac", "1", "-b:a", "48k", str(mp3)], check=True)
    man[name] = [SR, len(y)]
    print(name, mp3.stat().st_size // 1024, "KB")


def main():
    rng = np.random.default_rng(11)
    man_path = OUT / "manifest.json"
    man = json.loads(man_path.read_text(encoding="utf-8"))
    lame = shutil.which("lame")
    write("amb_engine", engine(rng), man, lame)
    write("skid", skid(rng), man, lame)
    man_path.write_text(json.dumps(man, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
