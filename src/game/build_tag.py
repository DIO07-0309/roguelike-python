"""
D3: BuildTag — 构筑标签系统

所有 Skill/Relic/Buff/Boss 的底层统一标签。
与 C++ build_tag.h 完全一致。
"""

from enum import Enum, auto


class BuildTag(Enum):
    NONE = 0
    MELEE = auto()       # 近战
    RANGED = auto()      # 远程
    MAGIC = auto()       # 法术
    FIRE = auto()        # 火焰
    ICE = auto()         # 冰霜
    LIGHTNING = auto()   # 雷电
    POISON = auto()      # 中毒
    BLEED = auto()       # 流血
    SUMMON = auto()      # 召唤
    COMBO = auto()       # 连击
    HEAVY = auto()       # 重击
    AOE = auto()         # 范围伤害
    PROJECTILE = auto()  # 弹幕
    HEAL = auto()        # 恢复
    TIME = auto()        # 时间
    DEFENSE = auto()     # 防御
    SUPPORT = auto()     # 辅助
    DOT = auto()         # 持续伤害
    KNOCKBACK = auto()   # 击退


_TAG_NAMES = {
    BuildTag.MELEE: "近战",
    BuildTag.RANGED: "远程",
    BuildTag.MAGIC: "法术",
    BuildTag.FIRE: "火焰",
    BuildTag.ICE: "冰霜",
    BuildTag.LIGHTNING: "雷电",
    BuildTag.POISON: "中毒",
    BuildTag.BLEED: "流血",
    BuildTag.SUMMON: "召唤",
    BuildTag.COMBO: "连击",
    BuildTag.HEAVY: "重击",
    BuildTag.AOE: "范围",
    BuildTag.PROJECTILE: "弹幕",
    BuildTag.HEAL: "恢复",
    BuildTag.TIME: "时间",
    BuildTag.DEFENSE: "防御",
    BuildTag.SUPPORT: "辅助",
    BuildTag.DOT: "持续",
    BuildTag.KNOCKBACK: "击退",
}


def build_tag_name(tag: BuildTag) -> str:
    return _TAG_NAMES.get(tag, "?")


def has_tag(tags: list[BuildTag], tag: BuildTag) -> bool:
    return tag in tags


def has_any_tag(tags: list[BuildTag], *targets: BuildTag) -> bool:
    return any(t in tags for t in targets)
