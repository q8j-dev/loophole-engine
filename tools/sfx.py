import io
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

import numpy as np

SR = 44100
SRC = Path(__file__).resolve().parent.parent / "vendor" / "sfx"
CACHE = Path(__file__).resolve().parent / "assets" / "sfx_cache"


@lru_cache(None)
def load(pack, name):
    CACHE.mkdir(parents=True, exist_ok=True)
    raw = CACHE / f"{pack}_{name}.f32"
    if not raw.exists():
        data = subprocess.run(["ffmpeg", "-v", "error", "-i", str(SRC / pack / f"{name}.ogg"), "-ac", "1", "-ar",
                               str(SR), "-f", "f32le", "-"], capture_output=True, check=True).stdout
        raw.write_bytes(data)
    x = np.frombuffer(raw.read_bytes(), np.float32).astype(np.float64)
    return x / max(np.abs(x).max(), 1e-9)


def S(name, n=0):
    for pack in ("sci-fi-sounds", "impact-sounds", "interface-sounds", "digital-audio"):
        for cand in (f"{name}_{n:03d}", f"{name}_{n + 1:03d}" if n == 0 else None, f"{name}{n}", name):
            if cand and (SRC / pack / f"{cand}.ogg").exists():
                return load(pack, cand).copy()
    raise FileNotFoundError(name)


def pitch(x, semis):
    r = 2 ** (semis / 12)
    n = int(len(x) / r)
    return np.interp(np.arange(n) * r, np.arange(len(x)), x)


def stretch_to(x, n):
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def eq(x, fn):
    n = 1 << int(np.ceil(np.log2(len(x) + 1)))
    X = np.fft.rfft(x, n)
    f = np.fft.rfftfreq(n, 1 / SR)
    return np.fft.irfft(X * fn(f), n)[:len(x)]


def lp(x, fc, order=2):
    return eq(x, lambda f: 1 / np.sqrt(1 + (f / fc) ** (2 * order)))


def hp(x, fc, order=2):
    return eq(x, lambda f: 1 / np.sqrt(1 + (fc / np.maximum(f, 1e-3)) ** (2 * order)))


def bell(x, fc, gain_db, q=1.0):
    g = 10 ** (gain_db / 20)
    return eq(x, lambda f: 1 + (g - 1) * np.exp(-(np.log2(np.maximum(f, 1) / fc) * q * 1.6) ** 2))


def place(length, *items):
    n = max([int(length * SR)] + [int(t * SR) + len(x) for t, x, g in items])
    out = np.zeros(n)
    for t, x, g in items:
        i = int(t * SR)
        out[i:i + len(x)] += x * g
    return out


def svf_lp(x, fc, q=0.9):
    fc = np.broadcast_to(np.asarray(fc, float), x.shape)
    f = 2 * np.sin(np.pi * np.minimum(fc, SR * 0.2) / SR)
    lo = 0.0
    bd = 0.0
    out = np.empty_like(x)
    for i in range(len(x)):
        hi = x[i] - lo - q * bd
        bd += f[i] * hi
        lo += f[i] * bd
        out[i] = lo
    return out


def env(x, a=0.002, r=0.05):
    n = len(x)
    e = np.ones(n)
    na = min(n, max(1, int(a * SR)))
    nr = min(n, max(1, int(r * SR)))
    e[:na] = np.linspace(0, 1, na)
    e[-nr:] *= np.linspace(1, 0, nr) ** 2
    return x * e


def decay(x, tau):
    return x * np.exp(-np.arange(len(x)) / (tau * SR))


def trim(x, dur):
    return env(x[:int(dur * SR)], 0.001, min(0.08, dur * 0.3))


def noise(dur, seed=0):
    return np.random.default_rng(seed).standard_normal(int(dur * SR))


def sine(freq, dur, phase=0.0):
    t = np.arange(int(dur * SR)) / SR
    f = np.broadcast_to(np.asarray(freq, float), t.shape) if np.ndim(freq) else np.full(t.shape, float(freq))
    return np.sin(2 * np.pi * np.cumsum(f) / SR + phase)


def sweep(f0, f1, dur, curve=2.0):
    t = np.linspace(0, 1, int(dur * SR))
    return f0 + (f1 - f0) * (1 - (1 - t) ** curve)


@lru_cache(None)
def room_ir(size=0.55, tail=1.1, damp=3500, seed=3):
    n = int(tail * SR)
    rng = np.random.default_rng(seed)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * 6.9 / tail)
    ir = lp(ir, damp, 1) * 0.6 + ir * 0.4 * np.exp(-t * 20)
    for k in range(9):
        d = int((0.004 + 0.011 * k * size + rng.random() * 0.004) * SR)
        if d < n:
            ir[d] += (0.7 ** k) * (1 if k % 2 == 0 else -1) * 2.5
    ir[0] = 0
    return ir / np.sqrt(np.sum(ir ** 2))


def reverb(x, wet=0.25, tail=1.1, damp=3500, pre=0.012):
    ir = room_ir(0.55, tail, damp)
    n = 1 << int(np.ceil(np.log2(len(x) + len(ir) + int(pre * SR))))
    y = np.fft.irfft(np.fft.rfft(x, n) * np.fft.rfft(np.concatenate([np.zeros(int(pre * SR)), ir]), n), n)
    out = np.zeros(len(x) + len(ir) + int(pre * SR))
    out[:len(x)] += x * (1 - wet * 0.35)
    out += y[:len(out)] * wet
    k = len(out)
    while k > len(x) and abs(out[k - 1]) < 1e-4:
        k -= 1
    return env(out[:max(k, len(x))], 0.0005, 0.04)


def master(x, peak=0.9, drive=1.2):
    x = x - np.mean(x)
    x = x / max(np.abs(x).max(), 1e-9)
    x = np.tanh(x * drive) / np.tanh(drive)
    return x * peak


def rev(x):
    return x[::-1].copy()


def snd_portal(hi):
    sh = 3 if hi else -2
    zap = pitch(S("laserLarge", 1 if hi else 3), sh)
    zap = hp(zap, 180)
    body = pitch(S("forceField", 2), sh + 5)
    body = bell(lp(body, 6000), 1800, 4, 1.2)
    sub = sine(sweep(140 if hi else 110, 48, 0.35, 3), 0.35) * np.exp(-np.arange(int(0.35 * SR)) / (0.09 * SR))
    tick = hp(S("impactPlate_light", 1), 1200)
    swirl = rev(lp(pitch(S("forceField", 4), sh), 3000))
    swirl = env(swirl[-int(0.32 * SR):], 0.18, 0.05)
    x = place(1.0, (0.0, zap, 0.85), (0.0, body, 0.45), (0.0, sub, 0.7), (0.0, tick, 0.18), (0.16, swirl, 0.35))
    return master(reverb(x, 0.22, 1.0), 0.85, 1.4)


def snd_land_portal():
    a = lp(pitch(S("forceField", 3), -7), 2500)
    return master(reverb(decay(a, 0.25), 0.3), 0.6)


def snd_deny():
    e = lp(pitch(S("error", 4), -2), 5000)
    buzz = sine(92, 0.22) * 0.5 + np.sign(sine(92, 0.22)) * 0.2
    buzz = lp(env(buzz, 0.004, 0.06), 1400)
    t = hp(S("impactTin_medium", 2), 400)
    x = place(0.6, (0.0, e, 0.55), (0.0, buzz, 0.5), (0.0, t, 0.35))
    return master(reverb(x, 0.15, 0.7), 0.6, 1.6)


def snd_whoosh():
    n = noise(0.75, 4)
    ff = sweep(250, 6000, 0.75, 1.5)
    w = svf_lp(n, ff, 0.35)
    w = w / max(np.abs(w).max(), 1e-9)
    w = w * np.sin(np.linspace(0, np.pi, len(w))) ** 1.5
    field = rev(lp(pitch(S("forceField", 1), 4), 7000))
    field = env(field[-int(0.5 * SR):], 0.2, 0.08)
    thump = sine(sweep(90, 40, 0.4), 0.4) * np.exp(-np.arange(int(0.4 * SR)) / (0.08 * SR))
    x = place(1.0, (0.0, w, 0.55), (0.12, field, 0.5), (0.42, thump, 0.65))
    return master(reverb(x, 0.25, 1.1), 0.8, 1.3)


def snd_boost():
    n = noise(0.9, 11)
    ff = sweep(400, 9000, 0.9, 0.6)
    w = svf_lp(n, ff, 0.5)
    w = w / max(np.abs(w).max(), 1e-9) * np.exp(-np.arange(len(w)) / (0.35 * SR))
    tone = sine(sweep(180, 720, 0.6, 0.7), 0.6) * np.exp(-np.arange(int(0.6 * SR)) / (0.2 * SR))
    tone2 = sine(sweep(360, 1440, 0.6, 0.7), 0.6) * np.exp(-np.arange(int(0.6 * SR)) / (0.12 * SR))
    thump = sine(sweep(110, 38, 0.35), 0.35) * np.exp(-np.arange(int(0.35 * SR)) / (0.07 * SR))
    x = place(1.1, (0.0, w, 0.6), (0.0, tone, 0.35), (0.0, tone2, 0.18), (0.0, thump, 0.8))
    return lp(master(reverb(x, 0.3, 1.2), 0.85, 1.6), 9000, 4)


def snd_updraft():
    n = noise(1.3, 21)
    ff = sweep(150, 2200, 1.3, 0.8)
    w = svf_lp(n, ff, 0.6)
    w = w / max(np.abs(w).max(), 1e-9) * np.sin(np.linspace(0, np.pi, len(w))) ** 0.8
    flut = 0.75 + 0.25 * np.sin(np.arange(len(w)) / SR * 2 * np.pi * 13)
    return master(reverb(w * flut, 0.3, 1.4), 0.6, 1.2)


def snd_lift():
    dur = 6.6
    n = int(dur * SR)
    t = np.arange(n) / SR
    ramp = np.clip(t / 1.2, 0, 1) * np.clip((dur - t) / 1.0, 0, 1)
    spd = np.sin(np.clip((t - 0.4) / (dur - 1.2), 0, 1) * np.pi)
    hum = np.sin(2 * np.pi * np.cumsum(48 + 10 * spd) / SR) * 0.5 + np.sin(2 * np.pi * np.cumsum(96 + 20 * spd) / SR) * 0.25
    whine = np.sin(2 * np.pi * np.cumsum(420 + 380 * spd) / SR) * 0.05 * spd
    wind = svf_lp(noise(dur, 31), 300 + 1600 * spd, 0.4)
    wind = wind / max(np.abs(wind).max(), 1e-9) * (0.15 + 0.5 * spd)
    rattle = (noise(dur, 32) * (np.sin(2 * np.pi * 7.3 * t) > 0.92)) * 0.25 * spd
    clunk0 = sine(sweep(80, 40, 0.5), 0.5) * np.exp(-np.arange(int(0.5 * SR)) / (0.06 * SR))
    x = (hum * 0.6 + whine + wind + lp(rattle, 2500)) * ramp
    x = x + place(dur, (0.05, clunk0, 0.9), (dur - 0.7, clunk0, 0.8))[:n]
    return master(reverb(x, 0.35, 2.4), 0.75, 1.3) * 0.45


def snd_alarm():
    dur = 4.6
    t = np.arange(int(dur * SR)) / SR
    f = np.where((t % 1.15) < 0.575, 620.0, 465.0)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sign(np.sin(ph)) * 0.25 + np.sin(ph) * 0.5 + np.sin(2 * ph) * 0.2
    gate = np.clip(((t % 0.575) / 0.02), 0, 1) * np.clip(((0.575 - t % 0.575) / 0.03), 0, 1)
    x = lp(tone * gate, 3500) * np.clip((dur - t) / 0.6, 0, 1)
    return lp(master(reverb(x, 0.45, 2.2), 0.6, 1.2), 7000, 3)


def snd_rumble():
    dur = 7.0
    n = int(dur * SR)
    t = np.arange(n) / SR
    rum = lp(noise(dur, 51), 120, 3)
    rum = rum / max(np.abs(rum).max(), 1e-9) * (0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t))
    groan = lp(pitch(S("impactMetal_heavy", 2), -14), 900)
    grind = svf_lp(noise(dur, 52), 300 + 200 * np.sin(2 * np.pi * 0.3 * t), 0.7)
    grind = grind / max(np.abs(grind).max(), 1e-9)
    x = rum * 0.8 * np.clip(t / 0.6, 0, 1) * np.clip((dur - t) / 2.0, 0, 1) + grind * 0.18 * np.clip((t - 1.5) / 1.0, 0, 1) * np.clip((dur - t) / 1.5, 0, 1)
    x = x + place(dur, (0.3, groan, 0.7), (2.4, groan, 0.5), (4.1, groan, 0.45))[:n]
    return lp(master(reverb(x, 0.35, 2.4), 0.8, 1.4), 6000, 3)


def step(k):
    s = S("footstep_concrete", k)
    s = bell(hp(s, 70), 160, 3, 1.2)
    s = bell(s, 3200, -3, 1.0)
    s = pitch(s, [-1.2, 0.4, -0.5, 0.9, -0.2][k])
    s = trim(s, 0.32)
    return master(reverb(s, 0.12, 0.6, 3000), 0.55, 1.1)


def snd_jump():
    s = trim(S("footstep_concrete", 3), 0.2)
    cloth = hp(lp(noise(0.16, 7), 3000), 600) * np.exp(-np.arange(int(0.16 * SR)) / (0.05 * SR))
    servo = lp(pitch(S("phaserUp", 2), -10), 2500) * 0.3
    x = place(0.4, (0.0, s, 0.8), (0.0, cloth, 0.25), (0.01, trim(servo, 0.18), 0.4))
    return master(reverb(x, 0.1, 0.5), 0.45, 1.1)


def snd_land():
    a = trim(S("footstep_concrete", 1), 0.3)
    b = trim(pitch(S("footstep_concrete", 4), -3), 0.3)
    thud = lp(S("impactSoft_heavy", 1), 900)
    sub = sine(sweep(75, 38, 0.25), 0.25) * np.exp(-np.arange(int(0.25 * SR)) / (0.05 * SR))
    x = place(0.6, (0.0, a, 0.7), (0.018, b, 0.6), (0.0, thud, 0.6), (0.0, sub, 0.55))
    return master(reverb(x, 0.14, 0.7), 0.7, 1.4)


def snd_pickup():
    grab = hp(pitch(S("forceField", 0), 7), 300)
    grab = env(grab[:int(0.45 * SR)], 0.01, 0.15)
    clk = trim(S("switch", 3), 0.12)
    mag = trim(lp(pitch(S("impactMetal_light", 2), -4), 4000), 0.3)
    hum = sine(sweep(220, 330, 0.3), 0.3) * 0.3 * np.exp(-np.arange(int(0.3 * SR)) / (0.12 * SR))
    x = place(0.7, (0.0, clk, 0.45), (0.0, grab, 0.45), (0.02, mag, 0.5), (0.0, hum, 0.25))
    return master(reverb(x, 0.18, 0.8), 0.65, 1.3)


def snd_release():
    rel = rev(hp(pitch(S("forceField", 0), 2), 300))
    rel = env(rel[-int(0.3 * SR):], 0.1, 0.06)
    clk = trim(S("switch", 5), 0.1)
    x = place(0.5, (0.0, rel, 0.45), (0.22, clk, 0.4))
    return master(reverb(x, 0.18, 0.8), 0.55, 1.2)


def snd_cube_hit():
    a = S("impactMetal_heavy", 2)
    b = lp(pitch(S("impactPlate_heavy", 0), -5), 2500)
    body = sine(118, 0.5) * 0.4 + sine(181, 0.5) * 0.25 + sine(263, 0.5) * 0.15
    body = body * np.exp(-np.arange(len(body)) / (0.09 * SR))
    x = place(1.0, (0.0, a, 0.7), (0.0, b, 0.6), (0.0, body, 0.5))
    return master(reverb(x, 0.2, 0.9), 0.75, 1.5)


def snd_button():
    clunk = lp(pitch(S("impactPlate_heavy", 3), -6), 3000)
    lock = trim(S("switch", 6), 0.15)
    hiss = hp(lp(noise(0.5, 9), 7000), 1500) * np.exp(-np.arange(int(0.5 * SR)) / (0.12 * SR))
    chime = pitch(S("confirmation", 1), -5)
    x = place(1.4, (0.0, clunk, 0.9), (0.02, lock, 0.45), (0.04, hiss, 0.12), (0.18, chime, 0.4))
    return master(reverb(x, 0.22, 1.1), 0.8, 1.4)


def snd_unpress():
    clunk = lp(pitch(S("impactPlate_medium", 1), -3), 3000)
    tone = pitch(S("phaserDown", 1), -9)
    x = place(0.8, (0.0, clunk, 0.7), (0.08, trim(lp(tone, 3000), 0.4), 0.3))
    return master(reverb(x, 0.2, 0.9), 0.6, 1.3)


def snd_door(open_):
    base = S("doorOpen" if open_ else "doorClose", 1)
    base = lp(bell(pitch(base, -4), 120, 4, 1.0), 6500, 4)
    servo = lp(pitch(S("spaceEngineSmall", 2), -7 if open_ else -10), 1800)
    servo = env(servo[:int(1.0 * SR)], 0.12, 0.35)
    hiss = hp(lp(noise(0.9, 11), 9000), 2500) * np.exp(-np.arange(int(0.9 * SR)) / (0.25 * SR))
    slam = lp(pitch(S("impactMetal_heavy", 4), -7), 2000)
    if open_:
        x = place(1.8, (0.0, hiss, 0.15), (0.0, servo, 0.45), (0.02, base, 0.7), (0.95, slam, 0.45))
    else:
        x = place(1.8, (0.0, servo, 0.4), (0.0, base, 0.7), (0.7, slam, 0.75), (0.72, hiss, 0.1))
    return master(reverb(x, 0.25, 1.3), 0.75, 1.3)


def snd_die():
    sl = lp(pitch(S("slime", 0), -3), 4000)
    boom = lp(S("lowFrequency_explosion", 0), 700)
    gl = hp(S("glitch", 2), 500)
    fizz = hp(noise(1.0, 13), 3000) * np.exp(-np.arange(SR) / (0.3 * SR)) * (0.5 + 0.5 * np.sin(np.arange(SR) * 0.02))
    x = place(1.8, (0.0, sl, 0.8), (0.0, boom, 0.6), (0.05, gl, 0.3), (0.0, fizz, 0.12))
    return master(reverb(x, 0.3, 1.3), 0.85, 1.6)


def snd_done():
    notes = [(0.0, 523.25), (0.11, 659.25), (0.22, 783.99), (0.36, 1046.5)]
    out = np.zeros(int(2.6 * SR))
    for t, f in notes:
        d = 2.2 - t
        n = int(d * SR)
        tt = np.arange(n) / SR
        v = (np.sin(2 * np.pi * f * tt) + 0.35 * np.sin(2 * np.pi * f * 2.01 * tt) * np.exp(-tt * 5) +
             0.15 * np.sin(2 * np.pi * f * 3.0 * tt) * np.exp(-tt * 9))
        v *= np.exp(-tt * 1.6) * np.minimum(1, tt * 200)
        i = int(t * SR)
        out[i:i + n] += v * 0.3
    pad = (sine(261.63, 2.6) + sine(329.6, 2.6) * 0.7 + sine(392.0, 2.6) * 0.6)
    pad = lp(pad, 1200) * np.sin(np.linspace(0, np.pi, len(pad))) ** 2 * 0.12
    conf = pitch(S("confirmation", 3), -2)
    x = place(2.6, (0.0, out, 1.0), (0.0, pad, 1.0), (0.0, conf, 0.3))
    return master(reverb(x, 0.4, 2.0, 5000), 0.75, 1.1)


def snd_arrive():
    x = rev(lp(pitch(S("forceField", 3), -3), 5000))
    x = env(x[-int(0.7 * SR):], 0.4, 0.05)
    tone = pitch(S("phaserDown", 2), -5)
    y = place(1.4, (0.0, x, 0.5), (0.62, trim(lp(tone, 4000), 0.5), 0.3))
    return master(reverb(y, 0.35, 1.5), 0.55, 1.1)


def snd_click():
    a = S("select", 2)
    b = hp(S("tick", 1), 2000)
    x = place(0.2, (0.0, a, 0.8), (0.0, b, 0.3))
    return master(reverb(x, 0.12, 0.5), 0.5, 1.0)


def snd_hover():
    return master(trim(lp(S("tick", 1), 6000), 0.08), 0.25, 1.0)


def snd_ambience():
    dur = 8.0
    n = int(dur * SR)
    hum = sine(50, dur) * 0.5 + sine(100, dur) * 0.3 + sine(150.3, dur) * 0.12 + sine(60.2, dur) * 0.15
    air = lp(hp(noise(dur, 21), 120), 900) * 0.35
    air2 = lp(noise(dur, 22), 200) * 0.5
    mod = 1 + 0.12 * np.sin(np.arange(n) / SR * 2 * np.pi * 0.25)
    eng = lp(stretch_to(S("spaceEngineLow", 1), n), 400) * 0.25
    x = (hum * 0.25 + air + air2 + eng) * mod
    fade = int(0.5 * SR)
    head = x[:fade].copy()
    x = x[fade:]
    w = np.linspace(0, 1, fade)
    x[-fade:] = x[-fade:] * (1 - w) + head * w
    return master(x, 0.2, 1.0)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def snd_music(sr=22050, chords=None, bar=8.0, seed=5, skip=0.38, gain=0.5):
    chords = chords or [[38, 50, 53, 57, 60, 64], [34, 46, 50, 53, 57, 62], [31, 43, 50, 53, 58, 62], [33, 45, 50, 52, 55, 61]]
    total = bar * len(chords)
    n = int(total * sr)
    out = np.zeros(n)
    t_all = np.arange(n) / sr
    rng = np.random.default_rng(seed)
    for ci, ch in enumerate(chords):
        t0 = ci * bar
        seg = int((bar + 4.0) * sr)
        t = np.arange(seg) / sr
        envp = np.minimum(1, t / 2.2) * np.clip((bar + 4.0 - t) / 4.0, 0, 1) ** 1.5
        cut = 700 + 500 * np.sin(2 * np.pi * (t / 11.0 + ci * 0.3))
        pad = np.zeros(seg)
        for note in ch[1:]:
            f0 = midi(note)
            for det in (-0.07, 0.0, 0.07):
                f = f0 * 2 ** (det / 12)
                ph = rng.random() * 6.28
                for h in range(1, int(1800 / f) + 1):
                    g = 1.0 / h * np.exp(-(h * f) / cut * 1.3)
                    pad += np.sin(2 * np.pi * f * h * t + ph * h) * g
        pad *= envp * 0.02
        bass = np.sin(2 * np.pi * midi(ch[0]) * t) * 0.18 + np.sin(2 * np.pi * midi(ch[0]) * 2 * t) * 0.04
        bass *= envp
        i0 = int(t0 * sr)
        for k, x in enumerate((pad, bass)):
            idx = (i0 + np.arange(seg)) % n
            np.add.at(out, idx, x)
    arp = np.zeros(n)
    step = 0.5
    for k in range(int(total / step)):
        if rng.random() < skip:
            continue
        ci = int(k * step / bar)
        ch = chords[ci]
        note = ch[2 + rng.integers(0, len(ch) - 2)] + 12
        f = midi(note)
        d = int(1.6 * sr)
        tt = np.arange(d) / sr
        v = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2 * tt) * np.exp(-tt * 8)) * np.exp(-tt * 3.2)
        v *= np.minimum(1, tt * 120) ** 2 * (0.05 + 0.04 * rng.random())
        idx = (int(k * step * sr) + np.arange(d)) % n
        np.add.at(arp, idx, v)
    dl = int(0.375 * sr)
    echo = np.zeros(n)
    fb = arp.copy()
    for r in range(5):
        fb = np.roll(fb, dl) * 0.45
        echo += fb
    arp = arp + lp(echo, 2500)
    mix = out + arp
    mixl = np.concatenate([mix, mix])
    ir_n = int(3.5 * sr)
    rng2 = np.random.default_rng(9)
    tt = np.arange(ir_n) / sr
    ir = rng2.standard_normal(ir_n) * np.exp(-tt * 6.9 / 3.5)
    ir = ir / np.sqrt(np.sum(ir ** 2))
    m = 1 << int(np.ceil(np.log2(len(mixl) + ir_n)))
    wet = np.fft.irfft(np.fft.rfft(mixl, m) * np.fft.rfft(ir, m), m)[:len(mixl)]
    wet = wet[n:2 * n]
    y = mix * 0.7 + wet * 0.55
    y = y - y.mean()
    y = y / np.abs(y).max()
    return np.tanh(y * 1.1) / np.tanh(1.1) * gain


def snd_ridemus(sr=22050):
    x = snd_music(sr, [[45, 57, 61, 64, 69, 73], [41, 53, 57, 60, 65, 69], [43, 55, 59, 62, 67, 71]], 2.6, 11, 0.15, 0.27)
    n = len(x)
    t = np.arange(n) / sr
    return x * np.clip(t / 0.8, 0, 1) * np.clip((n / sr - t) / 1.5, 0, 1)


def snd_finale(sr=22050):
    return snd_music(sr, [[38, 50, 54, 57, 62, 66], [43, 55, 59, 62, 67, 71], [47, 59, 62, 66, 71, 74],
                          [45, 57, 61, 64, 69, 73], [43, 55, 58, 62, 67, 70], [45, 57, 61, 64, 69, 76]], 5.0, 21, 0.2, 0.36)


def snd_rush():
    dur = 2.4
    n = int(dur * SR)
    t = np.arange(n) / SR
    sw = svf_lp(noise(dur, 41), 200 + 5000 * (t / dur) ** 2, 0.5)
    sw = sw / max(np.abs(sw).max(), 1e-9) * (t / dur) ** 1.5 * np.clip((dur - t) / 0.3, 0, 1)
    ch = sum(np.sin(2 * np.pi * midi(m) * t) for m in (57, 61, 64, 69)) * 0.1 * (t / dur) ** 2
    return master(reverb(sw * 0.6 + ch, 0.3, 1.6), 0.6, 1.2) * 0.7


def sounds():
    out = {
        "portal1": snd_portal(True), "portal2": snd_portal(False), "deny": snd_deny(), "whoosh": snd_whoosh(),
        "jump": snd_jump(), "land": snd_land(), "pickup": snd_pickup(), "release": snd_release(),
        "cubehit": snd_cube_hit(), "button": snd_button(), "unpress": snd_unpress(), "door": snd_door(True),
        "doorclose": snd_door(False), "die": snd_die(), "done": snd_done(), "arrive": snd_arrive(),
        "click": snd_click(), "amb": snd_ambience(), "boost": snd_boost(), "updraft": snd_updraft(), "lift": snd_lift(), "rush": snd_rush(), "alarm": snd_alarm(), "rumble": snd_rumble(),
    }
    for k in range(5):
        out[f"step{k + 1}"] = step(k)
    return out


def wav(x, sr=SR):
    pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16)
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return b.getvalue(), len(pcm)


def assets(asset_fn):
    out = []
    items = [(n, x, SR) for n, x in sounds().items()]
    items.append(("music", snd_music(22050), 22050))
    items.append(("ridemus", snd_ridemus(22050), 22050))
    items.append(("finale", snd_finale(22050), 22050))
    for n, x, sr in items:
        data, count = wav(x, sr)
        md5, fn = asset_fn(data, "wav")
        out.append({"name": n, "assetId": md5, "dataFormat": "wav", "format": "", "rate": sr, "sampleCount": count,
                    "md5ext": fn})
    import vo
    for n, data, count in vo.mp3_assets():
        md5, fn = asset_fn(data, "mp3")
        out.append({"name": n, "assetId": md5, "dataFormat": "mp3", "format": "", "rate": 22050, "sampleCount": count,
                    "md5ext": fn})
    return out


if __name__ == "__main__":
    import sys
    d = Path(sys.argv[1] if len(sys.argv) > 1 else "sfx_out")
    d.mkdir(exist_ok=True)
    for n, x in sounds().items():
        (d / f"{n}.wav").write_bytes(wav(x)[0])
        rms = np.sqrt(np.mean(x ** 2))
        print(f"{n:10s} {len(x) / SR:5.2f}s peak {np.abs(x).max():.2f} rms {rms:.3f}")
