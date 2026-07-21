"""
Relic System — B11/B12 (Python port)
局内圣物：JSON配置驱动、宝箱掉落、被动效果、存档恢复、HUD展示
"""
import json
import os
import sys
import random
from dataclasses import dataclass, field


# ---- RelicInstance (挂 Player 上) ----
@dataclass
class RelicInstance:
    id: str = ""


# ---- RelicDef (配置定义) ----
@dataclass
class RelicDef:
    id: str = ""
    name: str = ""         # "血纹护符"
    short_name: str = ""   # "血"
    desc: str = ""         # 效果描述
    rarity: str = "common" # common|rare|epic
    param: float = 0.0
    param2: int = 0
    hud_color: tuple = (200, 200, 200)
    tags: list = field(default_factory=list)  # G5.8 patch: BuildTag values


# ---- Config table ----
_g_relic: dict[str, RelicDef] = {}


def load_relic_defs(path: str = "resources/relics.json") -> bool:
    """加载 relics.json 配置表。"""
    global _g_relic
    # B12.6-fix: 多路径尝试 (兼容 dev / PyInstaller --onedir / --onefile)
    if not os.path.exists(path):
        candidates = []
        meipass = getattr(sys, '_MEIPASS', '')
        if meipass:
            candidates.append(meipass)
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
            candidates.append(exe_dir)
            candidates.append(os.path.join(exe_dir, '_internal'))
        for base in candidates:
            alt = os.path.join(base, path)
            if os.path.exists(alt):
                path = alt
                break
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"[RELIC] ERROR loading {path}: {e}")
        return False

    loaded = 0
    for obj in data:
        rid = obj.get("id", "")
        if not rid:
            continue
        # G5.8: parse string tags → BuildTag enum values
        from src.game.build_tag import build_tags_from_strings
        raw_tags = obj.get("tags", [])
        relic_tags = build_tags_from_strings(raw_tags) if raw_tags else []
        d = RelicDef(
            id=rid,
            name=obj.get("name", rid),
            short_name=obj.get("short_name", rid),
            desc=obj.get("desc", ""),
            rarity=obj.get("rarity", "common"),
            param=obj.get("param", 0.0),
            param2=obj.get("param2", 0),
            hud_color=tuple(obj.get("hud_color", [200, 200, 200])),
            tags=relic_tags,
        )
        _g_relic[rid] = d
        loaded += 1
    print(f"[RELIC] Loaded {loaded} relics (total {len(_g_relic)} in table)")
    return loaded > 0


def get_relic_def(rid: str) -> RelicDef | None:
    return _g_relic.get(rid)


def player_has_relic(player, rid: str) -> bool:
    if not player or not hasattr(player, 'relics'):
        return False
    return any(r.id == rid for r in player.relics)


def get_all_relic_ids() -> list[str]:
    return list(_g_relic.keys())


def get_relic_short_name(rid: str) -> str:
    d = _g_relic.get(rid)
    return d.short_name if d else rid


def get_relic_display_name(rid: str) -> str:
    d = _g_relic.get(rid)
    return d.name if d else rid


def get_relic_hud_color(rid: str) -> tuple:
    d = _g_relic.get(rid)
    return d.hud_color if d else (200, 200, 200)


# ---- Rarity weight (B12) ----
def _rarity_level_int(rarity: str) -> int:
    return {"common": 0, "rare": 1, "epic": 2, "legendary": 3}.get(rarity, 0)

def _rarity_weight(rarity: str) -> int:
    return {"common": 100, "rare": 40, "epic": 10, "legendary": 3}.get(rarity, 100)


# ---- Unified relic grant (B12) ----
def try_grant_random_relic(player, drop_chance: float) -> str:
    """按 drop_chance 判定是否掉落，再按 rarity 权重抽 relic。返回提示文字或空串。"""
    if not player:
        return ""
    if random.random() >= drop_chance:
        return ""
    if not _g_relic:
        print("[RELIC] ERROR: _g_relic is empty! load_relic_defs may have failed.")
        return ""

    all_ids = get_all_relic_ids()
    # 按 rarity 收集未持有 relic
    slots = {"common": [], "rare": [], "epic": [], "legendary": []}
    total_w = 0
    for rid in all_ids:
        if player_has_relic(player, rid):
            continue
        d = _g_relic.get(rid)
        if not d:
            continue
        if d.rarity not in slots:
            slots[d.rarity] = []
        slots[d.rarity].append(rid)
        if slots[d.rarity]:
            total_w += _rarity_weight(d.rarity)

    if total_w == 0:
        return ""  # 全收集

    # 轮盘选 rarity
    roll = random.randint(0, total_w - 1)
    chosen_rarity = None
    for rar in ["common", "rare", "epic", "legendary"]:
        if not slots[rar]:
            continue
        w = len(slots[rar]) * _rarity_weight(rar)  # B12.6-fix: per-rarity total weight
        if roll < w:
            chosen_rarity = rar
            break
        roll -= w

    # 回退
    candidates = slots.get(chosen_rarity, []) if chosen_rarity else []
    if not candidates:
        candidates = [rid for rids in slots.values() for rid in rids]
    if not candidates:
        return ""

    chosen = random.choice(candidates)
    player.relics.append(RelicInstance(id=chosen))
    d = _g_relic.get(chosen)
    # M18: 标记到全局图鉴
    from src.systems.relic_archive import g_relic_archive
    g_relic_archive.mark_obtained(chosen, _rarity_level_int(d.rarity if d else "common"))
    name = d.name if d else chosen
    return f"你获得了圣物：{name}。"
