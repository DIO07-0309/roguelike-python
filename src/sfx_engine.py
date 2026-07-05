"""
──────────────────────────────────────────
程序化音效引擎 — MP3文件优先 + 合成回退
──────────────────────────────────────────

所有 Sound 按需懒加载，不依赖全局状态。
使用 pygame.mixer.find_channel() 自动分配通道。
"""

import math
import array
import os
import random
import pygame


SR = 22050
MAX_AMP = 32767

# =========================================================
# 基础波形
# =========================================================

def _decay(peak=0.8, dur=0.3):
    def fn(t):
        return peak * max(0, 1 - t / dur) ** 2
    return fn

def _spike(peak=0.9, rise=0.01, dur=0.3):
    def fn(t):
        if t < rise:
            return peak * (t / rise)
        return peak * max(0, 1 - (t - rise) / (dur - rise)) ** 1.5
    return fn

def _square_samples(n, freq, amp_fn) -> array.array:
    data = array.array('h', [0] * n)
    if isinstance(freq, (int, float)):
        freq = lambda t, f=freq: f
    for i in range(n):
        t = i / SR
        f = freq(t)
        a = amp_fn(t) if callable(amp_fn) else amp_fn
        if f <= 0: continue
        period = max(1, SR / f)
        data[i] = int(MAX_AMP * a if (i % int(period)) < period // 2 else -MAX_AMP * a)
    return data

def _sine_samples(n, freq, amp_fn) -> array.array:
    data = array.array('h', [0] * n)
    if isinstance(freq, (int, float)):
        freq = lambda t, f=freq: f
    for i in range(n):
        t = i / SR
        f = freq(t)
        a = amp_fn(t) if callable(amp_fn) else amp_fn
        if f <= 0: continue
        data[i] = int(MAX_AMP * a * math.sin(2 * math.pi * f * t))
    return data

def _noise_samples(n, amp_fn) -> array.array:
    data = array.array('h', [0] * n)
    for i in range(n):
        t = i / SR
        a = amp_fn(t) if callable(amp_fn) else amp_fn
        data[i] = int(MAX_AMP * a * (random.random() * 2 - 1))
    return data

def _mix(*arrays: array.array) -> array.array:
    if not arrays: return array.array('h', [])
    n = min(len(a) for a in arrays)
    r = array.array('h', [0] * n)
    for a in arrays:
        for i in range(n):
            r[i] = max(-MAX_AMP, min(MAX_AMP - 1, r[i] + a[i]))
    return r

# =========================================================
# 合成器
# =========================================================

def _compile_melee():
    dur = 0.18; n = int(SR * dur)
    sw = _square_samples(n, lambda t: 500 - 420 * (t/dur)**0.6, _spike(0.7, 0.01, dur))
    ns = _noise_samples(n, _spike(0.25, 0.02, dur*0.5))
    return pygame.mixer.Sound(buffer=_mix(sw, ns).tobytes())

def _compile_hit():
    dur = 0.12; n = int(SR * dur)
    th = _sine_samples(n, 80, _spike(0.9, 0.005, dur))
    ns = _noise_samples(n, _spike(0.3, 0.01, dur*0.6))
    return pygame.mixer.Sound(buffer=_mix(th, ns).tobytes())

def _compile_slash():
    dur = 0.35; n = int(SR * dur)
    sw = _square_samples(n, lambda t: 800 - 650 * (t/dur)**0.5, _spike(0.8, 0.01, dur))
    ring = _sine_samples(n, lambda t: 2400 - 600 * (t/dur), _decay(0.25, dur))
    ns = _noise_samples(n, _spike(0.15, 0.005, 0.1))
    return pygame.mixer.Sound(buffer=_mix(sw, ring, ns).tobytes())

def _compile_bolt():
    dur = 0.45; n = int(SR * dur)
    result = array.array('h', [0] * n)
    rng = random.Random(42)
    for _ in range(32):
        start = rng.randint(0, n - 1)
        length = rng.randint(80, 400)
        burst = rng.random() * 0.9
        for i in range(length):
            pos = start + i
            if pos < n:
                decay = max(0, 1 - i / length) ** 3
                result[pos] = int(MAX_AMP * burst * decay * (rng.random() * 2 - 1))
    thunder = _sine_samples(n, lambda t: 45 + 20 * math.sin(t * 15), _decay(0.4, dur))
    return pygame.mixer.Sound(buffer=_mix(result, thunder).tobytes())

def _compile_heal():
    dur = 0.7; n = int(SR * dur)
    result = array.array('h', [0] * n)
    notes = [1046.5, 1318.5, 1568.0, 2093.0]
    for j, freq in enumerate(notes):
        start = int(SR * j * 0.12)
        chunk = _sine_samples(int(SR * 0.25), freq, _decay(0.45, 0.25))
        for i, v in enumerate(chunk):
            if start + i < n:
                result[start + i] = max(-MAX_AMP, min(MAX_AMP - 1, result[start + i] + v))
    wind = _sine_samples(n, 800, _decay(0.15, dur))
    pad = _sine_samples(n, 523.25, _decay(0.12, dur))
    return pygame.mixer.Sound(buffer=_mix(result, wind, pad).tobytes())

def _compile_pickup():
    dur = 0.25; n = int(SR * dur)
    c5 = _sine_samples(n, 523.25, _decay(0.35, dur))
    e5 = _sine_samples(n, 659.25, _decay(0.35, dur))
    return pygame.mixer.Sound(buffer=_mix(c5, e5).tobytes())

def _compile_levelup():
    dur = 0.5; n = int(SR * dur)
    result = array.array('h', [0] * n)
    for j, freq in enumerate([392.0, 523.25, 659.25, 784.0, 1046.5]):
        start = int(SR * j * 0.08)
        chunk = _square_samples(int(SR * 0.15), freq, _decay(0.4, 0.15))
        for i, v in enumerate(chunk):
            if start + i < n:
                result[start + i] = max(-MAX_AMP, min(MAX_AMP - 1, result[start + i] + v))
    return pygame.mixer.Sound(buffer=result.tobytes())

def _compile_victory():
    """通关号角 — C大调和弦上行 + 钟声泛音。"""
    dur = 2.5; n = int(SR * dur)
    result = array.array('h', [0] * n)
    # 第一段：C-E-G-C 琶音上行 (方波，号角感)
    brass_notes = [
        (261.63, 0.0, 0.35), (329.63, 0.2, 0.30), (392.0, 0.4, 0.30),
        (523.25, 0.6, 0.4), (659.25, 0.9, 0.25), (784.0, 1.05, 0.30),
        (1046.5, 1.25, 0.5),
    ]
    for freq, t_start, note_dur in brass_notes:
        start = int(SR * t_start)
        chunk_n = int(SR * note_dur)
        # 方波主号角
        chunk = _square_samples(chunk_n, freq, _decay(0.5, note_dur))
        for i, v in enumerate(chunk):
            if start + i < n:
                result[start + i] = max(-MAX_AMP, min(MAX_AMP - 1, result[start + i] + v))
    # 第二段：长尾和弦 C-E-G (正弦铺垫)
    pad_start = int(SR * 1.2)
    pad_n = int(SR * 1.1)
    for freq in [261.63, 329.63, 392.0]:
        pad = _sine_samples(pad_n, freq, _decay(0.35, 1.1))
        for i, v in enumerate(pad):
            pos = pad_start + i
            if pos < n:
                result[pos] = max(-MAX_AMP, min(MAX_AMP - 1, result[pos] + v))
    # 第三段：和弦终响 C-E-G-C 齐奏
    final_start = int(SR * 1.9)
    final_n = int(SR * 0.55)
    for freq in [523.25, 659.25, 784.0, 1046.5]:
        fn = _square_samples(final_n, freq, _decay(0.6, 0.55))
        for i, v in enumerate(fn):
            pos = final_start + i
            if pos < n:
                result[pos] = max(-MAX_AMP, min(MAX_AMP - 1, result[pos] + v))
    return pygame.mixer.Sound(buffer=result.tobytes())

# =========================================================
# 懒加载 + 播放
# =========================================================

_snd: dict[str, pygame.mixer.Sound] = {}

# 外部MP3路径
JOJO_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "jojo_timestop.mp3")

_COMPILERS = {
    "melee": _compile_melee, "hit": _compile_hit, "slash": _compile_slash,
    "bolt": _compile_bolt, "heal": _compile_heal, "pickup": _compile_pickup,
    "levelup": _compile_levelup, "victory": _compile_victory,
}

def _get_or_load(name: str) -> pygame.mixer.Sound | None:
    if name in _snd:
        return _snd[name]
    snd = None
    # timestop 从外部MP3
    if name == "timestop" and os.path.exists(JOJO_PATH):
        snd = pygame.mixer.Sound(JOJO_PATH)
    if snd is None and name in _COMPILERS:
        snd = _COMPILERS[name]()
    if snd is not None:
        _snd[name] = snd
    return snd

def play_sfx(name: str, volume: float = 0.6):
    """播放音效 (name = melee/hit/slash/bolt/heal/timestop/pickup/levelup)。"""
    try:
        snd = _get_or_load(name)
        if snd is None:
            return
        ch = pygame.mixer.find_channel()
        if ch is None:
            ch = pygame.mixer.Channel(1)
        ch.set_volume(volume)
        ch.play(snd)
    except Exception as e:
        print(f"[SFX] {name}: {e}")

def init_sfx():
    """初始化混音器 (main.py 调用)。"""
    if not pygame.mixer.get_init():
        pygame.mixer.init(frequency=SR, size=-16, channels=2, buffer=512)
    print("[SFX] ready")
