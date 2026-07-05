"""
──────────────────────────────────────────
技能辅助系统 —— 范围检测等纯函数
──────────────────────────────────────────

职责：
  - 提供技能通用的目标筛选函数。
  - 与具体技能解耦，方便新增技能复用。

设计原则：
  - 全部是纯函数，不持有状态。
  - 新技能需要新范围类型时在此扩展。
"""

import pygame
from src.entities.player import Direction


def get_targets_in_cone(caster, targets: list, cone_range: int = 1) -> list:
    """获取玩家前方 3×3 菱形区域内的所有怪物。

    锥形区域基于玩家朝向：
      - UP:    玩家上方 3 行
      - DOWN:  玩家下方 3 行
      - LEFT:  玩家左侧 3 列
      - RIGHT: 玩家右侧 3 列

    参数：
        caster: 释放者（玩家）。
        targets: 候选目标列表。
        cone_range: 范围半径（瓦片数），默认 1。

    返回：
        在锥形区域内的目标列表。
    """
    hit_list = []
    px = caster.entity.rect.centerx
    py = caster.entity.rect.centery
    size = 32 * (cone_range + 1)       # 加上玩家自身一格
    # 根据朝向构建检测矩形
    if caster.direction == Direction.UP:
        zone = pygame.Rect(px - size // 2, py - size, size, size)
    elif caster.direction == Direction.DOWN:
        zone = pygame.Rect(px - size // 2, py, size, size)
    elif caster.direction == Direction.LEFT:
        zone = pygame.Rect(px - size, py - size // 2, size, size)
    else:   # RIGHT
        zone = pygame.Rect(px, py - size // 2, size, size)
    for target in targets:
        if not hasattr(target, "entity"):
            continue
        if zone.colliderect(target.entity.rect):
            hit_list.append(target)
    return hit_list
