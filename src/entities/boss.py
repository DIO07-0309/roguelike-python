"""
──────────────────────────────────────────
Boss 系统 —— BossAI 状态机 + Boss 专属技能
──────────────────────────────────────────

职责：
  - BossAI 继承 MonsterAI，新增技能释放和阶段切换。
  - BossSkill 类封装 Boss 专属的范围技能。
  - 提供 spawn_boss() 工厂函数。

设计原则：
  - Boss 不是新类 —— 复用 Monster 挂载 BossAI。
  - BossSkill 是独立冷却对象，由 BossAI 调度。
  - 阶段切换由血量百分比驱动，行为参数化。
"""

import math
import random
import pygame
from config import TILE_SIZE
from src.entities.ai import MonsterAI, AIState
from src.entities.components import AttackType


class BossSkill:
    """Boss 专属技能 —— 带冷却的主动技能模板。

    属性：
        name: 技能名。
        cooldown: 冷却时间（秒）。
        _last_use_time: 上次释放的游戏时间戳。
        fx_kind: 特效类型（"cone"/"circle"/"none"），子类覆写。
        fx_radius: 特效半径（像素）。
        fx_color: 特效颜色（RGB）。
    """

    fx_kind = "circle"
    fx_radius = 60
    fx_color = (200, 40, 40)

    def __init__(self, name: str, cooldown: float):
        self.name = name
        self.cooldown = cooldown
        self._last_use_time = -999.0

    def can_use(self, game_time: float) -> bool:
        return (game_time - self._last_use_time) >= self.cooldown

    def execute(self, boss, player, monsters: list,
                game_map, game_time: float) -> str:
        raise NotImplementedError

    def mark_used(self, game_time: float):
        self._last_use_time = game_time

    def get_fx_effect(self, boss) -> dict:
        """返回该技能的视觉特效 dict，由 BossAI 写入 effects 列表。

        参数：
            boss: Boss 怪物实例。

        返回：
            特效 dict 或 None（fx_kind="none" 时）。
        """
        if self.fx_kind == "none":
            return None
        return {
            "kind": self.fx_kind,
            "x": boss.entity.rect.centerx,
            "y": boss.entity.rect.centery,
            "radius": self.fx_radius,
            "color": self.fx_color,
            "duration": 0.5,
            "elapsed": 0.0,
        }


class ConeAttack(BossSkill):
    """暗影冲击 —— 物理伤害。"""

    fx_kind = "circle"
    fx_radius = 96
    fx_color = (200, 40, 40)

    def __init__(self):
        super().__init__(name="暗影冲击", cooldown=5.0)

    def execute(self, boss, player, monsters, game_map, game_time) -> str:
        if not self._player_in_cone(boss, player):
            return f"Boss 释放了 {self.name}，但你没有被打中"
        from src.systems.combat_system import calculate_damage
        atk = int(boss.combat.get_effective_attack() * 1.8)
        dmg = calculate_damage(
            atk, player.combat.get_effective_defense(AttackType.PHYSICAL),
            AttackType.PHYSICAL)
        player.combat.take_damage(dmg)
        self.mark_used(game_time)
        return f"Boss 释放 {self.name}！造成 {dmg} 伤害"

    def _player_in_cone(self, boss, player) -> bool:
        px = boss.entity.rect.centerx
        py = boss.entity.rect.centery
        size = 64
        zone = pygame.Rect(px - size, py - size // 2, size * 2, size)
        return zone.colliderect(player.entity.rect)


class CircleAOE(BossSkill):
    """地裂 —— 魔法伤害。"""

    fx_kind = "circle"
    fx_radius = 80
    fx_color = (220, 50, 50)

    def __init__(self):
        super().__init__(name="地裂", cooldown=7.0)

    def execute(self, boss, player, monsters, game_map, game_time) -> str:
        dx = player.entity.rect.centerx - boss.entity.rect.centerx
        dy = player.entity.rect.centery - boss.entity.rect.centery
        dist = math.hypot(dx, dy)
        if dist > 80:
            return f"Boss 释放了 {self.name}，但你躲开了"
        from src.systems.combat_system import calculate_damage
        atk = int(boss.combat.get_effective_attack() * 1.2)
        dmg = calculate_damage(
            atk, player.combat.get_effective_defense(AttackType.MAGICAL),
            AttackType.MAGICAL)
        player.combat.take_damage(dmg)
        self.mark_used(game_time)
        return f"Boss 释放 {self.name}！造成 {dmg} 伤害"


class SummonMinions(BossSkill):
    """召唤小怪 —— 在 Boss 周围生成 2 只兽人。"""

    fx_kind = "circle"
    fx_radius = 64
    fx_color = (150, 50, 200)

    def __init__(self):
        super().__init__(name="召唤兽人", cooldown=15.0)

    def execute(self, boss, player, monsters, game_map, game_time) -> str:
        from src.entities.monster import spawn_monster
        count = 0
        for _ in range(2):
            offset_x = random.randint(-2, 2)
            offset_y = random.randint(-2, 2)
            spawn_x = boss.entity.position.x + offset_x * TILE_SIZE
            spawn_y = boss.entity.position.y + offset_y * TILE_SIZE
            tx, ty = game_map.pixel_to_tile(spawn_x, spawn_y)
            if game_map.is_walkable(tx, ty):
                m = spawn_monster(spawn_x, spawn_y, "orc")
                monsters.append(m)
                count += 1
        self.mark_used(game_time)
        return f"Boss 召唤了 {count} 只兽人！"


# Boss 三技能列表
BOSS_SKILLS = [ConeAttack, CircleAOE, SummonMinions]


class BossAI(MonsterAI):
    """Boss 专用 AI —— 阶段切换 + 技能释放。

    状态流转：
      IDLE/CASE/ATTACK (同普通 AI)
        +
      每帧尝试使用冷却就绪的技能
        +
      半血以下进入 ENRAGE（移速提升、冷却缩短）

    属性（新增）：
        skills: Boss 持有技能列表。
        is_enraged: 是否已进入狂暴。
    """

    def __init__(self):
        super().__init__(
            sight_range=10, move_speed=60,
            patrol_interval=3.0, attack_range=2.0,
        )
        # 初始化 Boss 技能
        skill_classes = [ConeAttack, CircleAOE, SummonMinions]
        self.skills: list[BossSkill] = [cls() for cls in skill_classes]
        self.is_enraged = False

    # =========================================================
    #  覆写 update —— 在基础行为上叠加技能 + 狂暴
    # =========================================================

    def update(self, monster, player, game_map,
               delta_time: float, game_time: float,
               monsters: list | None = None,
               effects: list | None = None):
        # 检查狂暴阶段
        if not self.is_enraged and self._hp_ratio(monster) < 0.4:
            self._enter_enrage()
        # 执行基础 AI 行为
        super().update(monster, player, game_map, delta_time,
                       game_time, monsters, effects)
        # 每帧最多尝试放一个 Boss 技能
        for skill in self.skills:
            if skill.can_use(game_time):
                if isinstance(skill, SummonMinions):
                    if self.state not in (AIState.CHASE, AIState.ATTACK):
                        continue
                ml = monsters if monsters is not None else []
                result = skill.execute(
                    monster, player, ml, game_map, game_time)
                # 写入特效
                if effects is not None:
                    from src.fx_engine import (boss_cone_fx, boss_circle_fx,
                                                boss_summon_fx)
                    mx = monster.entity.rect.centerx
                    my = monster.entity.rect.centery
                    if isinstance(skill, ConeAttack):
                        effects += boss_cone_fx(mx, my)
                    elif isinstance(skill, CircleAOE):
                        effects += boss_circle_fx(mx, my)
                    elif isinstance(skill, SummonMinions):
                        effects += boss_summon_fx(mx, my)
                break

    def _enter_enrage(self):
        """进入狂暴模式 —— 移速和攻击提速。"""
        self.is_enraged = True
        self.move_speed = int(self.move_speed * 1.6)
        # 所有技能冷却缩短 30%
        for skill in self.skills:
            skill.cooldown *= 0.7

    # =========================================================
    #  辅助
    # =========================================================

    def _hp_ratio(self, monster) -> float:
        """返回当前血量百分比。"""
        return monster.combat.current_hp / monster.combat.max_hp


# =========================================================
#  Boss 预设
# =========================================================

BOSS_PRESETS = {
    5: {
        "name": "暗影骑士",
        "max_hp": 250,
        "attack": 15,
        "physical_defense": 10,
        "magical_defense": 4,
        "color": (120, 20, 180),
        "title": "第一狱守 · 暗影骑士",
        "lore": "曾是王城最荣耀的骑士，被黑暗意志吞噬后\n成为地牢第一道门的永恒守门人。",
        "skills": "暗影冲击 · 地裂 · 召唤兽人",
    },
    10: {
        "name": "地狱火魔",
        "max_hp": 500,
        "attack": 24,
        "physical_defense": 14,
        "magical_defense": 8,
        "color": (240, 100, 20),
        "title": "第二狱守 · 地狱火魔",
        "lore": "熔岩深渊中诞生的远古恶魔，\n以灼热烈焰焚烧一切闯入者。",
        "skills": "暗影冲击 · 地裂 · 召唤兽人",
    },
    15: {
        "name": "深渊之主·终焉",
        "max_hp": 900,
        "attack": 35,
        "physical_defense": 22,
        "magical_defense": 14,
        "color": (180, 20, 20),
        "title": "终焉 · 深渊之主",
        "lore": "地牢最深处的终极存在，一切黑暗的源头。\n击败他，地牢将重获光明。",
        "skills": "暗影冲击 · 地裂 · 召唤兽人",
    },
}


def spawn_boss(tile_x: int, tile_y: int,
               floor_num: int = 5) -> "Monster":
    """按楼层创建对应 Boss。

    参数：
        tile_x, tile_y: 瓦片坐标。
        floor_num: 关卡号，用于查预设表。

    返回：
        挂载了 BossAI 的 Monster 实例。
    """
    from src.entities.monster import Monster
    cfg = BOSS_PRESETS.get(floor_num, BOSS_PRESETS[5])
    boss = Monster(
        x=tile_x * TILE_SIZE,
        y=tile_y * TILE_SIZE,
        name=cfg["name"],
        max_hp=cfg["max_hp"],
        attack=cfg["attack"],
        physical_defense=cfg.get("physical_defense", 10),
        magical_defense=cfg.get("magical_defense", 4),
        color=cfg["color"],
        ai=BossAI(),
        attack_type=AttackType.PHYSICAL,
    )
    boss.is_boss = True
    boss.entity.size = (48, 48)
    boss.entity.rect.width = 48
    boss.entity.rect.height = 48
    return boss


def get_boss_info(floor_num: int) -> dict | None:
    """获取 Boss 的介绍信息，供 BOSS_INTRO 画面使用。

    参数：
        floor_num: 关卡号。

    返回：
        Boss 预设 dict 或 None。
    """
    return BOSS_PRESETS.get(floor_num)
