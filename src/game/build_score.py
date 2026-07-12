"""
D3: BuildScore — 构筑评分与流派识别

从玩家所有系统收集 BuildTag 并累计，识别最强流派。
与 C++ build_score.cpp 一致。
"""

from enum import Enum, auto
from src.game.build_tag import BuildTag, has_tag, has_any_tag, build_tag_name


class BuildType(Enum):
    NONE = 0
    BERSERKER = auto()      # 狂战士: MELEE+COMBO+HEAVY
    FIRE_MAGE = auto()      # 火法师: FIRE+AOE+DOT
    POISON_MASTER = auto()  # 毒术大师: POISON+DOT
    TIME_WIZARD = auto()    # 时间术士: TIME+SUPPORT
    SUPPORTER = auto()      # 辅助者: HEAL+SUPPORT+DEFENSE
    BARRAGE_SHOOTER = auto()  # 弹幕射手: PROJECTILE+RANGED


_BUILD_NAMES = {
    BuildType.BERSERKER: "狂战士",
    BuildType.FIRE_MAGE: "火法师",
    BuildType.POISON_MASTER: "毒术大师",
    BuildType.TIME_WIZARD: "时间术士",
    BuildType.SUPPORTER: "辅助者",
    BuildType.BARRAGE_SHOOTER: "弹幕射手",
    BuildType.NONE: "无构筑",
}


class BuildScore:
    """收集并统计玩家的 BuildTag 分布。"""

    def __init__(self):
        self._counts: dict[BuildTag, int] = {}
        for tag in BuildTag:
            if tag != BuildTag.NONE:
                self._counts[tag] = 0

    def add(self, tag: BuildTag, weight: int = 1):
        if tag in self._counts:
            self._counts[tag] += weight

    def add_tags(self, tags: list[BuildTag], weight: int = 1):
        for t in tags:
            self.add(t, weight)

    def get_count(self, tag: BuildTag) -> int:
        return self._counts.get(tag, 0)

    def identify(self) -> BuildType:
        c = self._counts
        # 狂战士: MELEE>=3 + COMBO>=2 + HEAVY>=1
        if c[BuildTag.MELEE] >= 3 and c[BuildTag.COMBO] >= 2 and c[BuildTag.HEAVY] >= 1:
            return BuildType.BERSERKER
        # 火法师: FIRE>=3 + AOE>=2 + DOT>=1
        if c[BuildTag.FIRE] >= 3 and c[BuildTag.AOE] >= 2 and c[BuildTag.DOT] >= 1:
            return BuildType.FIRE_MAGE
        # 毒术大师: POISON>=3 + DOT>=2
        if c[BuildTag.POISON] >= 3 and c[BuildTag.DOT] >= 2:
            return BuildType.POISON_MASTER
        # 时间术士: TIME>=2 + SUPPORT>=2
        if c[BuildTag.TIME] >= 2 and c[BuildTag.SUPPORT] >= 2:
            return BuildType.TIME_WIZARD
        # 辅助者: HEAL>=2 + SUPPORT>=2 + DEFENSE>=2
        if c[BuildTag.HEAL] >= 2 and c[BuildTag.SUPPORT] >= 2 and c[BuildTag.DEFENSE] >= 2:
            return BuildType.SUPPORTER
        # 弹幕射手: PROJECTILE>=3 + RANGED>=2
        if c[BuildTag.PROJECTILE] >= 3 and c[BuildTag.RANGED] >= 2:
            return BuildType.BARRAGE_SHOOTER
        return BuildType.NONE

    def build_name(self) -> str:
        return _BUILD_NAMES.get(self.identify(), "未知")


def calculate_build(player) -> BuildScore:
    """从玩家的技能/圣物/Buff 收集标签。"""
    bs = BuildScore()
    if not player:
        return bs

    # 技能标签
    for sk in player.skills.active_skills:
        tags = getattr(sk, 'build_tags', [])
        bs.add_tags(tags)

    # 被动技能标签
    for pk in player.skills.passives:
        tags = getattr(pk, 'build_tags', [])
        bs.add_tags(tags)

    # 圣物标签 (D4: 从 relic def 的 favorite_tags 读取)
    for r in getattr(player, 'relics', []):
        from src.systems.relic_system import get_relic_def
        d = get_relic_def(r.id)
        if d and hasattr(d, 'build_tags'):
            bs.add_tags(d.build_tags)

    return bs
