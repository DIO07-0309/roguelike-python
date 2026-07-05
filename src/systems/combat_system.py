"""
──────────────────────────────────────────
战斗系统 —— 伤害计算 / 攻击判定（纯函数）
──────────────────────────────────────────

职责：
  - 攻击命中判定（距离检测）。
  - 伤害公式计算。
  - 目标选择（找最近的敌人）。

设计原则：
  - 全部是纯函数，不持有状态。
  - 通过 modifiers 参数接入技能/Buff/装备修正。
  - formula 抽成独立函数，方便以后调整平衡性。
"""

import math
import random
import pygame
from src.entities.components import AttackType


def calculate_damage(attacker_atk: int, defender_def: int,
                     atk_type: AttackType = AttackType.PHYSICAL,
                     modifiers: dict | None = None) -> int:
    """计算最终伤害值。

    公式：伤害 = max(1, attacker_atk - defender_def * 0.5)
    浮动：±20%。

    参数：
        attacker_atk: 有效攻击力。
        defender_def: 有效防御力（已按类型选取）。
        atk_type: 攻击类型（物理/魔法/真实）。
        modifiers: 额外修正。

    返回：
        最终伤害值（整数，不低于 1）。
    """
    base_damage = max(1.0, attacker_atk - defender_def * 0.5)
    variance = random.uniform(0.8, 1.2)
    final_damage = base_damage * variance
    if modifiers:
        pct_mod = modifiers.get("damage_pct", 0.0)
        flat_mod = modifiers.get("damage_flat", 0)
        final_damage = final_damage * (1 + pct_mod) + flat_mod
    return max(1, int(final_damage))


def find_attack_target(
    attacker_rect: pygame.Rect,
    target_list: list,
    attack_range: float = 1.5,
) -> object | None:
    """从目标列表中选出最近且可命中的对象。

    距离 = 两矩形中心点的欧氏距离。
    attack_range 单位为瓦片数（乘以 TILE_SIZE 换算为像素）。

    参数：
        attacker_rect: 攻击者的碰撞矩形。
        target_list: 候选目标列表（每个对象需有 entity.rect）。
        attack_range: 攻击范围（瓦片数）。

    返回：
        最近目标（object）或 None（无可命中目标时）。
    """
    attack_range_px = attack_range * 32  # TILE_SIZE
    best_target = None
    best_distance = float("inf")
    for candidate in target_list:
        if not hasattr(candidate, "entity"):
            continue
        c_rect = candidate.entity.rect
        dx = attacker_rect.centerx - c_rect.centerx
        dy = attacker_rect.centery - c_rect.centery
        distance = math.hypot(dx, dy)
        if distance <= attack_range_px and distance < best_distance:
            best_target = candidate
            best_distance = distance
    return best_target
