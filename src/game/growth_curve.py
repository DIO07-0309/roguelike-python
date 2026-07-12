"""
D4: GrowthCurve — 难度成长曲线

统一所有难度相关计算，替代散落各处的硬编码倍率。
与 C++ growth_curve.h/.cpp 一致。
"""

from dataclasses import dataclass


@dataclass
class CurvePoint:
    monster_hp: float
    monster_atk: float
    boss_hp: float
    boss_atk: float
    elite_scale: float
    exp_scale: float
    gold_scale: float
    relic_scale: float
    arena_scale: float


class GrowthCurve:
    """全局难度曲线单例。"""

    def __init__(self):
        # 15 层曲线数据
        self._curves: list[CurvePoint] = []
        for f in range(1, 16):
            t = (f - 1) / 14.0  # 0.0 → 1.0
            # 普通层: hp 1.0→3.3, atk 1.0→2.9
            # Boss层回归 1.0
            is_boss = f in (5, 10, 15)
            self._curves.append(CurvePoint(
                monster_hp=1.0 if is_boss else 1.0 + t * 2.3,
                monster_atk=1.0 if is_boss else 1.0 + t * 1.9,
                boss_hp=1.0 + t * 1.5,
                boss_atk=1.0 + t * 2.0,
                elite_scale=1.2 + t * 0.8,
                exp_scale=1.0 + t * 2.0,
                gold_scale=1.0 + t * 1.5,
                relic_scale=0.05 + t * 0.25,
                arena_scale=0.5 + t * 1.5,
            ))

    def curve(self, floor: int) -> CurvePoint:
        return self._curves[min(14, max(0, floor - 1))]

    def hp_scale(self, floor: int) -> float:
        return self.curve(floor).monster_hp

    def atk_scale(self, floor: int) -> float:
        return self.curve(floor).monster_atk

    def exp_scale(self, floor: int) -> float:
        return self.curve(floor).exp_scale

    def gold_scale(self, floor: int) -> float:
        return self.curve(floor).gold_scale

    def arena_scale(self, floor: int) -> float:
        return self.curve(floor).arena_scale

    def elite_scale(self, floor: int) -> float:
        return self.curve(floor).elite_scale


# 全局单例
g_growth = GrowthCurve()
