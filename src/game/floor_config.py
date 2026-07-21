"""
D1: FloorConfig / ChapterConfig / FloorNarrative — 统一楼层配置

G6.2: Data extracted to resources/floor_config.json + floor_narrative.json.
Query API unchanged.
"""

import json, os, sys
from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
#  FloorConfig — 单层难度/敌人/特殊房间/BGM 配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class FloorConfig:
    floor: int                    # 1-15
    chapter: int                  # 0=地牢入口, 1=幽暗深渊, 2=熔岩炼狱
    chapter_label: str            # "地牢入口" / "幽暗深渊" / "熔岩炼狱"
    story_msg: str | None         # 首次进入剧情文字 (None=无)
    hp_mult: float                # 怪物 HP 倍率
    atk_mult: float               # 怪物 ATK 倍率
    monster_count: int            # 基础怪物数量
    special_room_count: int       # 特殊房间数量
    is_boss: bool                 # Boss 层
    is_rest_floor: bool           # 休息层
    bgm: str                      # "dungeon" | "boss"


# ═══════════════════════════════════════════════════════════════
#  ChapterConfig — 章节定义
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChapterConfig:
    chapter: int
    name: str                     # "地牢入口"
    start_floor: int
    end_floor: int


# ═══════════════════════════════════════════════════════════════
#  FloorNarrative — 楼层叙事 (D4 Step3)
# ═══════════════════════════════════════════════════════════════

@dataclass
class FloorNarrative:
    floor: int
    title: str                    # 楼层名称 e.g. "沉睡牢狱"
    subtitle: str                 # 英文副标题
    description: str | None       # 1-2句环境描写
    enter_dialogue: str | None    # 首次进入独白
    exit_dialogue: str | None     # 离开楼层独白
    boss_hint: str | None         # Boss前3层伏笔
    narrations: list[str | None]  # 3-5条环境旁白
    ambience: str                 # 环境音效 hook (D5接入)
    ambient_color: tuple          # (r, g, b) 环境色调


# ═══════════════════════════════════════════════════════════════
#  NarrativeState — 旁白状态
# ═══════════════════════════════════════════════════════════════

@dataclass
class NarrativeState:
    floor_intro_played: list[bool] = field(default_factory=lambda: [False] * 15)
    last_narration_idx: int = -1
    narration_timer: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  JSON-backed data tables (G6.2: extracted from hardcoded lists)
# ═══════════════════════════════════════════════════════════════

_FLOORS: list[FloorConfig] | None = None
_CHAPTERS: list[ChapterConfig] | None = None
_NARRATIVES: list[FloorNarrative] | None = None


def _resolve(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


def _ensure_loaded():
    global _FLOORS, _CHAPTERS, _NARRATIVES
    if _FLOORS is not None:
        return
    # Load floor config
    try:
        with open(_resolve("resources/floor_config.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []
    _FLOORS = []
    for obj in data:
        _FLOORS.append(FloorConfig(
            floor=obj["floor"], chapter=obj["chapter"], chapter_label=obj["label"],
            story_msg=obj.get("story"), hp_mult=obj["hp"], atk_mult=obj["atk"],
            monster_count=obj["monsters"], special_room_count=obj["special"],
            is_boss=obj["boss"], is_rest_floor=obj["rest"], bgm=obj["bgm"],
        ))
    # Chapters derived from floor data
    _CHAPTERS = [
        ChapterConfig(0, "地牢入口", 1, 5),
        ChapterConfig(1, "幽暗深渊", 6, 10),
        ChapterConfig(2, "熔岩炼狱", 11, 15),
    ]
    # Load narrative
    try:
        with open(_resolve("resources/floor_narrative.json"), "r", encoding="utf-8") as f:
            ndata = json.load(f)
    except Exception:
        ndata = []
    _NARRATIVES = []
    for obj in ndata:
        _NARRATIVES.append(FloorNarrative(
            floor=obj["floor"], title=obj["title"], subtitle=obj["subtitle"],
            description=obj.get("desc"), enter_dialogue=obj.get("enter"),
            exit_dialogue=obj.get("exit"), boss_hint=obj.get("boss_hint"),
            narrations=obj.get("narrations", []),
            ambience=obj.get("ambience", "silence"),
            ambient_color=tuple(obj.get("ambient_color", [60, 40, 40])),
        ))
    print(f"[Floor] Loaded {len(_FLOORS)} configs + {len(_NARRATIVES)} narratives from JSON")


# ═══════════════════════════════════════════════════════════════
#  查询接口 (unchanged API)
# ═══════════════════════════════════════════════════════════════

def get_floor_config(floor: int) -> FloorConfig:
    """返回 1-based 楼层配置。"""
    _ensure_loaded()
    if floor < 1 or floor > 15:
        return _FLOORS[0]
    return _FLOORS[floor - 1]


def get_chapter_config(chapter: int) -> ChapterConfig:
    """返回 0-based 章节配置。"""
    if chapter < 0 or chapter >= len(_CHAPTERS):
        return _CHAPTERS[0]
    return _CHAPTERS[chapter]


def get_chapter_for_floor(floor: int) -> int:
    return get_floor_config(floor).chapter


def get_floor_narrative(floor: int) -> FloorNarrative | None:
    """返回 1-based 楼层叙事。"""
    _ensure_loaded()
    if floor < 1 or floor > 15:
        return _NARRATIVES[0]
    return _NARRATIVES[floor - 1]


def get_chapter_title(chapter: int) -> str:
    titles = {0: "第一章: 地牢入口", 1: "第二章: 幽暗深渊", 2: "第三章: 熔岩炼狱"}
    return titles.get(chapter, "???")


def get_chapter_subtitle(chapter: int) -> str:
    subtitles = {0: "Chapter I: The Dungeon Gate",
                 1: "Chapter II: The Dark Abyss",
                 2: "Chapter III: The Lava Inferno"}
    return subtitles.get(chapter, "???")


def pick_random_narration(floor: int, state: NarrativeState) -> str | None:
    """从楼层旁白池中随机选取一条。避免与上次重复。"""
    import random
    fn = get_floor_narrative(floor)
    if not fn:
        return None
    pool = [n for n in fn.narrations if n is not None]
    if not pool:
        return None
    idx = random.randint(0, len(pool) - 1)
    if len(pool) >= 2 and idx == state.last_narration_idx:
        idx = (idx + 1) % len(pool)
    state.last_narration_idx = idx
    return pool[idx]
