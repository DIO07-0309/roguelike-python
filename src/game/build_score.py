"""
G5 sync: BuildScore — 12 BuildType (C++ parity)
"""
from enum import Enum, auto
from src.game.build_tag import BuildTag


class BuildType(Enum):
    NONE = 0
    BERSERKER = auto()      # MELEE+COMBO+HEAVY
    FIRE_MAGE = auto()      # FIRE+AOE+DOT
    POISON_MASTER = auto()  # POISON+DOT
    TIME_MASTER = auto()    # TIME+SUPPORT
    SUPPORT = auto()        # HEAL+SUPPORT+DEFENSE
    PROJECTILE = auto()     # PROJECTILE+RANGED
    # ── G5 sync: new builds ──
    ICE_MAGE = auto()       # ICE+AOE
    LIGHTNING_MAGE = auto() # LIGHTNING+AOE
    BLEED_BLADE = auto()    # BLEED+MELEE+DOT
    SHADOW_STRIKER = auto() # MELEE+COMBO+TIME
    JUGGERNAUT = auto()     # DEFENSE+HEAVY+HEAL
    SUMMON_LORD = auto()    # SUMMON+SUPPORT


_BUILD_NAMES = {
    BuildType.BERSERKER: "狂战士",
    BuildType.FIRE_MAGE: "火法师",
    BuildType.POISON_MASTER: "毒术大师",
    BuildType.TIME_MASTER: "时间术士",
    BuildType.SUPPORT: "辅助者",
    BuildType.PROJECTILE: "弹幕射手",
    BuildType.ICE_MAGE: "冰霜法师",
    BuildType.LIGHTNING_MAGE: "雷电法师",
    BuildType.BLEED_BLADE: "流血剑士",
    BuildType.SHADOW_STRIKER: "暗影刺客",
    BuildType.JUGGERNAUT: "重装守卫",
    BuildType.SUMMON_LORD: "召唤领主",
    BuildType.NONE: "无构筑",
}


class BuildScore:
    def __init__(self):
        self._counts: dict[BuildTag, int] = {}
        for tag in BuildTag:
            if tag != BuildTag.NONE: self._counts[tag] = 0

    def add(self, tag: BuildTag, weight: int = 1):
        if tag in self._counts: self._counts[tag] += weight

    def add_tags(self, tags: list[BuildTag], weight: int = 1):
        for t in tags: self.add(t, weight)

    def get_count(self, tag: BuildTag) -> int:
        return self._counts.get(tag, 0)

    def identify(self) -> BuildType:
        c = self._counts
        if c[BuildTag.MELEE] >= 3 and c[BuildTag.COMBO] >= 2 and c[BuildTag.HEAVY] >= 1:
            return BuildType.BERSERKER
        if c[BuildTag.FIRE] >= 3 and c[BuildTag.AOE] >= 2 and c[BuildTag.DOT] >= 1:
            return BuildType.FIRE_MAGE
        if c[BuildTag.POISON] >= 3 and c[BuildTag.DOT] >= 2:
            return BuildType.POISON_MASTER
        if c[BuildTag.TIME] >= 2 and c[BuildTag.SUPPORT] >= 2:
            return BuildType.TIME_MASTER
        if c[BuildTag.HEAL] >= 2 and c[BuildTag.SUPPORT] >= 2 and c[BuildTag.DEFENSE] >= 2:
            return BuildType.SUPPORT
        if c[BuildTag.PROJECTILE] >= 3 and c[BuildTag.RANGED] >= 2:
            return BuildType.PROJECTILE
        # ── G5 sync ──
        if c[BuildTag.ICE] >= 3 and c[BuildTag.AOE] >= 2:
            return BuildType.ICE_MAGE
        if c[BuildTag.LIGHTNING] >= 3 and c[BuildTag.AOE] >= 2:
            return BuildType.LIGHTNING_MAGE
        if c[BuildTag.BLEED] >= 3 and c[BuildTag.MELEE] >= 2 and c[BuildTag.DOT] >= 1:
            return BuildType.BLEED_BLADE
        if c[BuildTag.MELEE] >= 3 and c[BuildTag.TIME] >= 2:
            return BuildType.SHADOW_STRIKER
        if c[BuildTag.DEFENSE] >= 3 and c[BuildTag.HEAVY] >= 2 and c[BuildTag.HEAL] >= 2:
            return BuildType.JUGGERNAUT
        if c[BuildTag.SUMMON] >= 2 and c[BuildTag.SUPPORT] >= 2:
            return BuildType.SUMMON_LORD
        return BuildType.NONE

    def build_name(self) -> str:
        return _BUILD_NAMES.get(self.identify(), "未知")

    def progress(self, bt: BuildType) -> float:
        c = self._counts
        thresholds = {BuildType.BERSERKER:(BuildTag.MELEE,6),BuildType.FIRE_MAGE:(BuildTag.FIRE,5),
            BuildType.POISON_MASTER:(BuildTag.POISON,5),BuildType.TIME_MASTER:(BuildTag.TIME,4),
            BuildType.SUPPORT:(BuildTag.HEAL,4),BuildType.PROJECTILE:(BuildTag.PROJECTILE,4),
            BuildType.ICE_MAGE:(BuildTag.ICE,5),BuildType.LIGHTNING_MAGE:(BuildTag.LIGHTNING,5),
            BuildType.BLEED_BLADE:(BuildTag.BLEED,5),BuildType.SHADOW_STRIKER:(BuildTag.MELEE,5),
            BuildType.JUGGERNAUT:(BuildTag.DEFENSE,5),BuildType.SUMMON_LORD:(BuildTag.SUMMON,3)}
        t = thresholds.get(bt)
        return min(1.0, c.get(t[0], 0) / t[1]) if t else 0.0


def calculate_build(player) -> BuildScore:
    bs = BuildScore()
    if not player: return bs
    from src.systems.relic_system import get_relic_def
    from src.systems.buff_system import get_buff_def
    for sk in getattr(getattr(player, "skills", None), "active_skills", []):
        for t in getattr(sk, "tags", []) or []: bs.add(t, 1)
    for pk in getattr(getattr(player, "skills", None), "passives", []):
        for t in getattr(pk, "tags", []) or []: bs.add(t, 1)
    for r in getattr(player, "relics", []):
        d = get_relic_def(r.id) if hasattr(r, "id") else None
        if d and hasattr(d, "tags"):
            for t in d.tags: bs.add(t, 2)
    for b in getattr(player, "active_buffs", []):
        d = get_buff_def(b.id)
        if d and d.tags:
            for t in d.tags: bs.add(t, b.stacks)
    return bs


def has_confirmed_build(player) -> bool:
    return calculate_build(player).identify() != BuildType.NONE
