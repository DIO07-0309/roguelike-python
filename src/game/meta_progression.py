"""
D6: MetaProgression — 局外永久成长

通关/死亡后获得 Soul + Knowledge，在技能树中解锁永久加成。
与 C++ meta_progression.h/.cpp 一致。
"""

from dataclasses import dataclass, field


@dataclass
class MetaNode:
    id: str
    name: str             # "生命力"
    desc: str             # "+2% 最大HP"
    cost_soul: int = 0
    cost_knowledge: int = 0
    max_level: int = 5
    unlocked: bool = False
    level: int = 0


_META_TREE: list[MetaNode] = [
    MetaNode("vitality", "生命力", "+2% 最大HP", cost_soul=50, max_level=5),
    MetaNode("power", "攻击力", "+2% 攻击力", cost_soul=50, max_level=5),
    MetaNode("gold", "初始金币", "+15 初始金币", cost_soul=30, max_level=3),
    MetaNode("potion", "初始药水", "+1 初始药水", cost_soul=30, max_level=3),
    MetaNode("relic", "圣物掉落", "+2% 圣物掉率", cost_knowledge=20, max_level=5),
    MetaNode("exp", "经验", "+3% 经验获取", cost_knowledge=15, max_level=5),
    MetaNode("buff_dur", "Buff持续", "+5% Buff时间", cost_knowledge=25, max_level=3),
    MetaNode("cdr", "技能冷却", "-2% 冷却缩减", cost_knowledge=30, max_level=5),
    MetaNode("build_speed", "构筑速度", "+5% Build成型速度", cost_knowledge=20, max_level=3),
    MetaNode("crit", "暴击率", "+1.5% 暴击率", cost_knowledge=25, max_level=5),
]


@dataclass
class RunSummary:
    """单局统计数据。"""
    total_kills: int = 0
    bosses_killed: int = 0
    elite_kills: int = 0
    floors_reached: int = 0
    max_combo: int = 0
    relics_collected: int = 0
    money_earned: int = 0


class MetaProgression:
    """局外永久成长管理器。"""

    def __init__(self):
        self.soul: int = 0        # 灵魂货币
        self.knowledge: int = 0   # 知识货币
        self.nodes: list[MetaNode] = _META_TREE

    def end_run(self, run: RunSummary):
        """结算单局，发放 Meta 货币。"""
        self.soul += run.total_kills * 1
        self.soul += run.bosses_killed * 20
        self.soul += run.elite_kills * 5
        self.knowledge += run.floors_reached * 3
        self.knowledge += run.bosses_killed * 10
        self.knowledge += run.relics_collected * 3

    def get_node(self, node_id: str) -> MetaNode | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def apply_all_bonuses(self, player) -> dict:
        """返回当前所有已学节点的效果汇总。"""
        bonuses = {"hp_pct": 0.0, "atk_pct": 0.0, "exp_pct": 0.0,
                   "relic_pct": 0.0, "cdr_pct": 0.0, "crit_pct": 0.0,
                   "buff_dur": 0.0, "build_speed": 0.0,
                   "start_gold": 0, "start_potions": 0}

        for node in self.nodes:
            if node.level <= 0:
                continue
            if node.id == "vitality":
                bonuses["hp_pct"] += node.level * 0.02
            elif node.id == "power":
                bonuses["atk_pct"] += node.level * 0.02
            elif node.id == "gold":
                bonuses["start_gold"] += node.level * 15
            elif node.id == "potion":
                bonuses["start_potions"] += node.level * 1
            elif node.id == "relic":
                bonuses["relic_pct"] += node.level * 0.02
            elif node.id == "exp":
                bonuses["exp_pct"] += node.level * 0.03
            elif node.id == "buff_dur":
                bonuses["buff_dur"] += node.level * 0.05
            elif node.id == "cdr":
                bonuses["cdr_pct"] -= node.level * 0.02
            elif node.id == "crit":
                bonuses["crit_pct"] += node.level * 0.015
        return bonuses


# 全局单例
g_meta = MetaProgression()
