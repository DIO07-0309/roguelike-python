"""
──────────────────────────────────────────
程序化背景音乐引擎 — 多声部合成 + 和弦
──────────────────────────────────────────

四支 BGM:
  标题:   「英雄降临」 C大调 / 110BPM / 管弦合奏
  选关:   「命运之门」 Am小调 / 85BPM / 竖琴冥想
  地牢:   「深渊回响」 C弗里吉亚 / 75BPM / 暗流铺垫
  Boss:   「终末决战」 Cm和声小调 / 150BPM / 疾速战鼓

设计原则:
  - 零外部文件，全部 array + math 合成
  - 方波(主旋律)+三角波(和声)+噪声(鼓)+正弦(铺垫)
  - 和弦进行驱动，不靠单音
  - ADSR 包络模拟更自然的音色衰减
"""

import math
import array
import random
import pygame


# =========================================================
# 常量
# =========================================================
SR = 22050                          # 采样率
BITS = 16
MAX_AMP = 32767
BPM = {"title": 110, "select": 85, "dungeon": 75, "boss": 150}

# 音符 → 频率 (Hz) — 4个八度
NOTES = {}

for octave in range(2, 6):
    base_names = ['C', 'Db', 'D', 'Eb', 'E', 'F', 'Gb', 'G', 'Ab', 'A', 'Bb', 'B']
    for i, name in enumerate(base_names):
        NOTES[f"{name}{octave}"] = 261.63 * (2 ** (octave - 4 + (i - 0) / 12 + (2 if name in ('Gb','Ab','Bb','Db','Eb') else 0)))


# Manually set correct frequencies
def _set_notes():
    """正确计算所有音符频率。"""
    global NOTES
    NOTES = {}
    base_names_freq = {
        0: 'C', 1: 'Db', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
        6: 'Gb', 7: 'G', 8: 'Ab', 9: 'A', 10: 'Bb', 11: 'B'
    }
    for octave in range(2, 7):
        for semitone, name in base_names_freq.items():
            midi = (octave + 1) * 12 + semitone
            freq = 440.0 * (2 ** ((midi - 69) / 12))
            NOTES[f"{name}{octave}"] = freq

_set_notes()

# =========================================================
# 波形合成 (带 ADSR 包络)
# =========================================================

def _apply_adsr(data: array.array, attack: float, decay: float,
                sustain: float, release: float):
    """在音频数组上施加 ADSR 音量包络。

    参数：
        attack:  0→1 上升比例。
        decay:   1→sustain 下降比例。
        sustain: 保持电平。
        release: sustain→0 下降比例。
    """
    n = len(data)
    a_end = max(1, int(n * attack))
    d_end = max(a_end + 1, int(n * (attack + decay)))
    r_start = max(d_end, int(n * (1 - release)))
    for i in range(n):
        t = i / n
        if i < a_end:
            gain = i / a_end
        elif i < d_end:
            gain = 1 - (1 - sustain) * ((i - a_end) / (d_end - a_end))
        elif i < r_start:
            gain = sustain
        else:
            gain = sustain * (1 - (i - r_start) / max(1, n - r_start))
        data[i] = int(data[i] * gain)


def _square(freq: float, dur: float, amp: float = 0.4,
            duty: float = 0.5) -> array.array:
    """方波（可变占空比）。"""
    n = int(SR * dur)
    data = array.array('h', [0] * n)
    if freq <= 0:
        return data
    period = max(1, int(SR / freq))
    for i in range(n):
        data[i] = int(MAX_AMP * amp if (i % period) < period * duty
                      else -MAX_AMP * amp)
    return data


def _triangle(freq: float, dur: float, amp: float = 0.3) -> array.array:
    """三角波（柔和）。"""
    n = int(SR * dur)
    data = array.array('h', [0] * n)
    if freq <= 0:
        return data
    period = max(1, int(SR / freq))
    half = period // 2
    for i in range(n):
        phase = (i % period)
        if phase < half:
            val = MAX_AMP * amp * (-1 + 4 * phase / period)
        else:
            val = MAX_AMP * amp * (3 - 4 * phase / period)
        data[i] = int(val)
    return data


def _sine(freq: float, dur: float, amp: float = 0.3) -> array.array:
    """正弦波（铺垫/管弦）。"""
    n = int(SR * dur)
    data = array.array('h', [0] * n)
    if freq <= 0:
        return data
    for i in range(n):
        data[i] = int(MAX_AMP * amp * math.sin(2 * math.pi * freq * i / SR))
    return data


def _saw(freq: float, dur: float, amp: float = 0.25) -> array.array:
    """锯齿波（更有力量感）。"""
    n = int(SR * dur)
    data = array.array('h', [0] * n)
    if freq <= 0:
        return data
    period = max(1, int(SR / freq))
    for i in range(n):
        data[i] = int(MAX_AMP * amp * (1 - 2 * (i % period) / period))
    return data


def _noise(dur: float, amp: float = 0.2) -> array.array:
    """快速衰减白噪声（打击乐器）。"""
    n = int(SR * dur)
    data = array.array('h', [0] * n)
    rng = random.Random()
    for i in range(n):
        decay_factor = max(0, 1 - (i / n) * 8)
        data[i] = int(rng.randint(-MAX_AMP, MAX_AMP) * amp * decay_factor)
    return data


def _mix(*arrays: array.array) -> array.array:
    """混合多个音频数组（所有数组对齐到最短者）。"""
    if not arrays:
        return array.array('h', [])
    n = min(len(a) for a in arrays)
    result = array.array('h', [0] * n)
    count = len(arrays)
    for a in arrays:
        for i in range(n):
            val = result[i] + a[i]
            result[i] = max(-MAX_AMP, min(MAX_AMP - 1, val))
    # 归一化
    if count > 2:
        for i in range(n):
            result[i] = int(result[i] * 0.7)
    return result


def _silence(dur: float) -> array.array:
    """静音片段。"""
    return array.array('h', [0] * int(SR * dur))

# =========================================================
# 和弦库
# =========================================================

class Chord:
    """和弦 — 一组音高半音偏移。"""
    MAJOR = [0, 4, 7]
    MINOR = [0, 3, 7]
    DIM = [0, 3, 6]
    AUG = [0, 4, 8]
    SUS4 = [0, 5, 7]
    MAJ7 = [0, 4, 7, 11]
    MIN7 = [0, 3, 7, 10]

    def __init__(self, root: str, kind: list[int]):
        midi = _note_to_midi(root)
        self.notes = [midi + k for k in kind]

def _note_to_midi(note: str) -> int:
    """C4=60"""
    if note not in NOTES:
        return 60
    base_names = {0:'C',1:'Db',2:'D',3:'Eb',4:'E',5:'F',6:'Gb',7:'G',8:'Ab',9:'A',10:'Bb',11:'B'}
    for midi in range(24, 96):
        octave = midi // 12 - 1
        semitone = midi % 12
        name = base_names.get(semitone, 'C')
        if f"{name}{octave}" == note:
            return midi
    return 60

def _midi_to_freq(midi: int) -> float:
    return 440.0 * (2 ** ((midi - 69) / 12))


# =========================================================
# 鼓组
# =========================================================

def _kick() -> array.array:
    """底鼓：低频噪声 + 快速衰减。"""
    data = _noise(0.12, 0.45)
    _apply_adsr(data, 0.01, 0.05, 0.1, 0.5)
    # 叠加低频正弦
    sine = _sine(80, 0.12, 0.8)
    _apply_adsr(sine, 0.01, 0.05, 0.05, 0.4)
    return _mix(data, sine)


def _snare() -> array.array:
    """小鼓：高频噪声。"""
    data = _noise(0.08, 0.3)
    _apply_adsr(data, 0.01, 0.02, 0.05, 0.3)
    return data


def _hihat() -> array.array:
    """踩镲：短高频噪声。"""
    data = _noise(0.04, 0.15)
    _apply_adsr(data, 0.01, 0.01, 0.01, 0.15)
    return data


def _tom() -> array.array:
    """通鼓：中频正弦+saw。"""
    data = _saw(200, 0.1, 0.3)
    _apply_adsr(data, 0.01, 0.03, 0.05, 0.4)
    return data


def _timpani() -> array.array:
    """定音鼓（标题用）：低频三角波。"""
    data = _triangle(100, 0.3, 0.7)
    _apply_adsr(data, 0.02, 0.05, 0.3, 0.6)
    return data


# =========================================================
# 音序器
# =========================================================

def _render_chord(chord: Chord, dur: float, wave=_sine, amp: float = 0.2) -> array.array:
    """将和弦渲染为持续音频。"""
    data = array.array('h', [0] * int(SR * dur))
    for midi in chord.notes:
        freq = _midi_to_freq(midi)
        partial = wave(freq, dur, amp / len(chord.notes) * 2)
        data = _mix(data, partial)
    return data


def _render_sequence(seq: list, wave=_square, amp: float = 0.35,
                      duty: float = 0.5) -> array.array:
    """将 (note|None, duration) 序列渲染为音频。

    支持：单音符 "C4"、和弦 Chord 对象、None(休止)。
    """
    track = array.array('h')
    for item, dur in seq:
        if item is None:
            track.extend(_silence(dur))
        elif isinstance(item, Chord):
            track.extend(_render_chord(item, dur, wave, amp))
        elif item in NOTES:
            freq = NOTES[item]
            chunk = wave(freq, dur, amp) if wave != _square else _square(freq, dur, amp, duty)
            track.extend(chunk)
        else:
            track.extend(_silence(dur))
    # ADSR 包络
    _apply_adsr(track, 0.05, 0.1, 0.65, 0.2)
    return track


def _render_drums(pattern: list, total_samples: int) -> array.array:
    """渲染鼓点 pattern → 音频。"""
    result = array.array('h', [0] * total_samples)
    for beat_pos, drum_fn in pattern:
        pos = int(SR * beat_pos)
        if pos >= total_samples:
            continue
        sound = drum_fn()
        for i, v in enumerate(sound):
            if pos + i < total_samples:
                result[pos + i] = max(-MAX_AMP, min(MAX_AMP - 1, result[pos + i] + v))
    return result


# =========================================================
# 4支 BGM 定义
# =========================================================

# ---------- 标题「英雄降临」C大调 110BPM ----------

TITLE_CHORDS = [
    (Chord("C4", Chord.MAJOR), 1.6), (Chord("G3", Chord.MAJOR), 1.6),
    (Chord("A3", Chord.MINOR), 1.6), (Chord("F3", Chord.MAJOR), 1.6),
    (Chord("C4", Chord.MAJOR), 1.6), (Chord("G3", Chord.MAJOR), 1.6),
    (Chord("F3", Chord.MAJOR), 1.6), (Chord("C4", Chord.MAJOR), 2.4),
]

TITLE_MELODY = [
    ("C5", 0.3), ("E5", 0.2), ("G5", 0.3), ("C6", 0.4), (None, 0.2),
    ("G5", 0.2), ("E5", 0.3), ("C5", 0.3), ("D5", 0.2), (None, 0.1),
    ("C6", 0.3), ("B5", 0.2), ("A5", 0.3), ("G5", 0.2), ("E5", 0.3),
    ("F5", 0.3), ("G5", 0.3), ("C6", 0.4), (None, 0.3),
    ("C6", 0.3), ("B5", 0.2), ("C6", 0.3), ("G5", 0.4),
    ("E5", 0.3), ("C5", 0.3), ("D5", 0.3), ("C5", 0.6),
    ("C5", 0.2), ("E5", 0.2), ("G5", 0.3), ("C6", 0.3), ("E6", 0.4),
    ("D6", 0.3), ("C6", 0.3), ("G5", 0.6), (None, 0.4),
    ("G5", 0.3), ("A5", 0.2), ("C6", 0.3), ("D6", 0.3), ("E6", 0.4),
    ("D6", 0.3), ("C6", 0.3), ("G5", 0.2), ("F5", 0.2), ("E5", 0.3),
    ("C5", 0.4), ("D5", 0.3), ("C5", 0.6), (None, 0.5),
]

# TITLE bass line (rich octaves)
TITLE_BASS = [
    ("C3", 0.8), ("G2", 0.8), ("A2", 0.8), ("F2", 0.8),
    ("C3", 0.8), ("G2", 0.8), ("F2", 0.8), ("C3", 1.2),
]

# ---------- 选关「命运之门」Am小调 85BPM ----------

SELECT_CHORDS = [
    (Chord("A3", Chord.MINOR), 2.0), (Chord("F3", Chord.MAJOR), 2.0),
    (Chord("G3", Chord.MAJOR), 2.0), (Chord("E3", Chord.MINOR), 2.0),
    (Chord("A3", Chord.MINOR), 2.0), (Chord("F3", Chord.MAJOR), 1.5),
    (Chord("C4", Chord.MAJOR), 1.0), (Chord("G3", Chord.MAJOR), 1.5),
]

SELECT_MELODY = [
    (None, 0.8), ("A4", 0.5), (None, 0.3), ("C5", 0.4),
    (None, 0.6), ("E5", 0.5), (None, 0.4), ("D5", 0.3),
    (None, 0.5), ("C5", 0.4), ("B4", 0.3), ("A4", 0.6),
    (None, 0.8), ("E4", 0.5), (None, 0.3), ("G4", 0.4),
    (None, 0.6), ("A4", 0.4), (None, 0.4), ("C5", 0.3),
    (None, 0.5), ("B4", 0.4), ("A4", 0.3), ("G4", 0.6),
    (None, 0.8), ("A4", 0.5), (None, 0.3), ("C5", 0.4),
    (None, 0.5), ("E5", 0.4), (None, 0.4), ("G5", 0.3),
    ("F5", 0.4), ("E5", 0.3), ("D5", 0.3), ("C5", 0.5),
    (None, 0.8),
]

# ---------- 地牢「深渊回响」C弗里吉亚 75BPM ----------

DUNGEON_CHORDS = [
    (Chord("C3", Chord.MINOR), 3.0), (Chord("Db3", Chord.MAJOR), 3.0),
    (Chord("Eb3", Chord.MAJOR), 3.0), (Chord("C3", Chord.MINOR), 3.0),
    (Chord("C3", Chord.MINOR), 3.0), (Chord("Ab2", Chord.MAJOR), 3.0),
    (Chord("Bb2", Chord.MAJOR), 3.0), (Chord("C3", Chord.MINOR), 4.0),
]

DUNGEON_MELODY = [
    ("C4", 0.5), (None, 1.0), ("Db4", 0.4), (None, 0.8),
    ("Eb4", 0.4), (None, 1.2), ("C4", 0.6), (None, 0.6),
    ("Ab3", 0.4), (None, 1.0), ("Bb3", 0.5), (None, 0.8),
    ("C4", 0.3), ("Db4", 0.3), (None, 0.4), ("Eb4", 0.5), (None, 1.0),
    (None, 1.5), ("C4", 0.4), (None, 0.6), ("Db4", 0.3),
    ("C4", 0.4), (None, 1.0), ("Bb3", 0.5), (None, 1.2),
    ("C4", 0.4), (None, 0.6), ("Eb4", 0.3), (None, 0.5),
    ("Ab3", 0.4), (None, 0.6), ("C4", 0.5), (None, 1.5),
]

# ---------- Boss「终末决战」Cm和声小调 150BPM ----------

BOSS_CHORDS = [
    (Chord("C3", Chord.MINOR), 1.0), (Chord("Ab2", Chord.MAJOR), 1.0),
    (Chord("Bb2", Chord.MAJOR), 1.0), (Chord("G2", Chord.MAJOR), 1.0),
    (Chord("C3", Chord.MINOR), 1.0), (Chord("Ab2", Chord.MAJOR), 1.0),
    (Chord("Bb2", Chord.MAJOR), 1.0), (Chord("G2", Chord.MAJOR), 0.8),
]

BOSS_MELODY = [
    ("C4", 0.12), ("Eb4", 0.12), ("G4", 0.12), ("C5", 0.20),
    ("B4", 0.12), ("G4", 0.12), ("F4", 0.15), ("Eb4", 0.10), (None, 0.05),
    ("C4", 0.12), ("Eb4", 0.12), ("Ab4", 0.12), ("C5", 0.20),
    ("Bb4", 0.12), ("Ab4", 0.12), ("G4", 0.15), ("F4", 0.10), (None, 0.05),
    ("G4", 0.15), ("Ab4", 0.12), ("Bb4", 0.12), ("C5", 0.18),
    ("D5", 0.15), ("Eb5", 0.12), ("D5", 0.10), ("C5", 0.08), (None, 0.04),
    ("B4", 0.12), ("C5", 0.12), ("G4", 0.15), ("Eb4", 0.10), (None, 0.06),
    (None, 0.10), ("G4", 0.12), ("Ab4", 0.08), ("G4", 0.10), ("F4", 0.12),
    ("Eb4", 0.15), ("C4", 0.10), ("Eb4", 0.12), ("G4", 0.10), ("C5", 0.20),
    ("B4", 0.12), ("G4", 0.12), ("Ab4", 0.15), ("G4", 0.20),
    ("C5", 0.12), ("Eb5", 0.12), ("G5", 0.15), ("C6", 0.30),
]

BOSS_BASS = [
    ("C2", 0.25), ("C2", 0.25), ("Ab1", 0.25), ("Ab1", 0.25),
    ("Bb1", 0.25), ("Bb1", 0.25), ("G1", 0.25), ("G1", 0.25),
]


# =========================================================
# BGM 编译器
# =========================================================

def _compile_bgm(chords: list, melody: list,
                 bass: list | None = None,
                 bpm: int = 110,
                 melody_wave: str = "square",
                 chord_wave: str = "sine",
                 bass_wave: str = "triangle",
                 drum_style: str = "standard") -> pygame.mixer.Sound:
    """编译完整 BGM 循环 → pygame Sound。

    参数：
        chords:     [(Chord, duration), ...] 和弦进行。
        melody:     [(note|Chord|None, duration), ...] 主旋律。
        bass:       [(note, duration), ...] 低音线 (可选)。
        bpm:        速度。
        melody_wave: 旋律波形 "square"/"sine"/"saw"/"triangle"。
        chord_wave:  和弦波形。
        bass_wave:   低音波形。
        drum_style:  鼓组风格 "standard"/"orchestral"/"sparse"/"heavy"。
    """
    # 时间倍率
    beat_dur = 60.0 / bpm

    # 和弦铺底
    chords_seq = [(c, dur * beat_dur * 4) for c, dur in chords]
    wave_fn = {"square": _square, "sine": _sine, "triangle": _triangle, "saw": _saw}
    chord_track = _render_sequence(chords_seq, wave=wave_fn.get(chord_wave, _sine), amp=0.18)
    _apply_adsr(chord_track, 0.1, 0.1, 0.5, 0.3)

    # 主旋律
    melody_seq = [(n, dur * beat_dur * 4) for n, dur in melody]
    mw = wave_fn.get(melody_wave, _square)
    melody_track = _render_sequence(melody_seq, wave=mw, amp=0.35)
    if len(melody_track) < len(chord_track):
        melody_track = _loop_array(melody_track, len(chord_track))

    # 低音
    bass_track = array.array('h', [0] * len(chord_track))
    if bass:
        bass_seq = [(n, dur * beat_dur * 4) for n, dur in bass]
        bw = wave_fn.get(bass_wave, _triangle)
        bass_track = _render_sequence(bass_seq, wave=bw, amp=0.5)
        if len(bass_track) < len(chord_track):
            bass_track = _loop_array(bass_track, len(chord_track))
    else:
        # 从和弦提取根音
        bass_data = array.array('h', [0] * len(chord_track))
        pos = 0
        for c, dur in chords_seq:
            samples = int(SR * dur)
            if c.notes:
                freq = _midi_to_freq(c.notes[0] - 12)
                chunk = _triangle(freq, dur, 0.4)
                _apply_adsr(chunk, 0.05, 0.1, 0.5, 0.3)
                for i, v in enumerate(chunk):
                    if pos + i < len(bass_data):
                        bass_data[pos + i] = v
            pos += samples
        bass_track = bass_data

    # 鼓组
    drums = _build_drum_pattern(len(chord_track), beat_dur, drum_style)

    # 混合
    mixed = _mix(chord_track, melody_track, bass_track, drums)
    return pygame.mixer.Sound(buffer=mixed.tobytes())


def _build_drum_pattern(total_samples: int, beat_dur: float,
                        style: str) -> array.array:
    """根据风格生成鼓点循环。"""
    kicks = []
    snares = []
    hats = []
    toms = []

    beats_per_bar = 4
    bar_samples = int(SR * beat_dur * beats_per_bar)
    n_bars = (total_samples // bar_samples) + 1

    if style == "orchestral":
        # 定音鼓为主
        for bar in range(n_bars):
            for beat in range(beats_per_bar):
                t = bar * bar_samples + beat * int(SR * beat_dur)
                if beat == 0 or beat == 2:
                    kicks.append((t / SR, _timpani))
                elif beat == 1 or beat == 3:
                    kicks.append((t / SR, _timpani))
    elif style == "heavy":
        # 快速双踩
        for bar in range(n_bars):
            for beat in range(beats_per_bar):
                t = bar * bar_samples + beat * int(SR * beat_dur)
                kicks.append((t / SR, _kick))
                if beat % 2 == 0:
                    snares.append((t / SR, _snare))
            # 8分踩镲
            for eighth in range(beats_per_bar * 2):
                t = bar * bar_samples + eighth * int(SR * beat_dur / 2)
                hats.append((t / SR, _hihat))
    elif style == "sparse":
        for bar in range(n_bars):
            kicks.append((bar * bar_samples / SR, _kick))
            if bar % 2 == 0:
                t = bar * bar_samples + int(SR * beat_dur * 2)
                snares.append((t / SR, _snare))
    else:  # standard
        for bar in range(n_bars):
            for beat in range(beats_per_bar):
                t = bar * bar_samples + beat * int(SR * beat_dur)
                if beat % 2 == 0:
                    kicks.append((t / SR, _kick))
                else:
                    snares.append((t / SR, _snare))
                # 踩镲 8分
                hats.append((t / SR, _hihat))
                hats.append((t + int(SR * beat_dur / 2)) / SR, _hihat)

    all_events = kicks + snares + hats + toms
    return _render_drums(all_events, total_samples)


def _loop_array(a: array.array, target_len: int) -> array.array:
    """将数组循环到目标长度。"""
    if len(a) == 0:
        return array.array('h', [0] * target_len)
    result = array.array('h', [0] * target_len)
    for i in range(target_len):
        result[i] = a[i % len(a)]
    return result


# =========================================================
# 公开接口
# =========================================================

_bgm_cache: dict[str, pygame.mixer.Sound] = {}
_bgm_channel: pygame.mixer.Channel | None = None
_bgm_loaded: set[str] = set()


def init_bgm():
    """初始化混音器（主入口调用一次）。"""
    global _bgm_channel
    try:
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=SR, size=-16, channels=8, buffer=1024)
        _bgm_channel = pygame.mixer.Channel(0)
        print("[BGM] Mixer ready")
    except Exception as e:
        print(f"[BGM] Init error: {e}")


def _ensure_loaded(name: str):
    """懒加载指定 BGM。"""
    if name in _bgm_loaded or name in _bgm_cache:
        return
    try:
        if name == "title":
            snd = _compile_bgm(TITLE_CHORDS, TITLE_MELODY, TITLE_BASS,
                               bpm=BPM["title"], melody_wave="square",
                               chord_wave="sine", bass_wave="triangle",
                               drum_style="orchestral")
        elif name == "select":
            snd = _compile_bgm(SELECT_CHORDS, SELECT_MELODY,
                               bpm=BPM["select"], melody_wave="triangle",
                               chord_wave="sine", drum_style="sparse")
        elif name == "dungeon":
            snd = _compile_bgm(DUNGEON_CHORDS, DUNGEON_MELODY,
                               bpm=BPM["dungeon"], melody_wave="square",
                               chord_wave="sine", drum_style="sparse")
        elif name == "boss":
            snd = _compile_bgm(BOSS_CHORDS, BOSS_MELODY, BOSS_BASS,
                               bpm=BPM["boss"], melody_wave="saw",
                               chord_wave="sine", bass_wave="square",
                               drum_style="heavy")
        else:
            return
        _bgm_cache[name] = snd
        _bgm_loaded.add(name)
        print(f"[BGM] {name} ready")
    except Exception as e:
        print(f"[BGM] Error loading {name}: {e}")
        import traceback
        traceback.print_exc()


def play_bgm(name: str, volume: float = 0.45):
    """播放指定 BGM（循环）。

    参数：
        name: "title" | "select" | "dungeon" | "boss"。
        volume: 音量 (0.0~1.0)。
    """
    _ensure_loaded(name)
    if name in _bgm_cache and _bgm_channel:
        _bgm_channel.play(_bgm_cache[name], loops=-1)
        _bgm_channel.set_volume(volume)


def play_title_bgm():
    play_bgm("title", 0.40)

def play_select_bgm():
    play_bgm("select", 0.35)

def play_dungeon_bgm():
    play_bgm("dungeon", 0.42)

def play_boss_bgm():
    play_bgm("boss", 0.50)

def stop_bgm():
    if _bgm_channel:
        _bgm_channel.fadeout(400)
