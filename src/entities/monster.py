"""
──────────────────────────────────────────
怪物类 —— 敌方实体，用于验证战斗系统
──────────────────────────────────────────

职责：
  - 持有实体 + 战斗属性组件。
  - 渲染自身。
  - 受伤与死亡处理。

设计原则：
  - 怪物 = Entity（位置） + CombatStats（战斗） + MonsterAI（行为）的组合。
  - AI 是可替换组件 —— Boss 可传入自定义 MonsterAI 子类。
  - 通过 spawn 工厂函数创建，方便以后接入 JSON 配置。
"""

import pygame
from src.entities.entity import Entity
from src.entities.components import CombatStats, AttackType
from src.entities.ai import MonsterAI
from src.systems.combat_system import calculate_damage


class Monster:
    """地牢怪物 —— 组合实体与战斗属性。"""

    DEFAULT_HP = 20
    DEFAULT_ATK = 4
    DEFAULT_PDEF = 1
    DEFAULT_MDEF = 0
    DEFAULT_SIZE = 28
    DEFAULT_COLOR = (200, 80, 80)
    ATTACK_COOLDOWN = 1.5

    def __init__(self, x: float, y: float,
                 name: str = "史莱姆",
                 max_hp: int = DEFAULT_HP,
                 attack: int = DEFAULT_ATK,
                 physical_defense: int = DEFAULT_PDEF,
                 magical_defense: int = DEFAULT_MDEF,
                 color: tuple = DEFAULT_COLOR,
                 ai: MonsterAI | None = None,
                 attack_type: AttackType = AttackType.PHYSICAL):
        """创建怪物。

        参数：
            x, y: 像素坐标。
            name: 怪物名称。
            max_hp: 最大生命值。
            attack: 攻击力。
            physical_defense: 物理防御。
            magical_defense: 魔法防御。
            color: 渲染颜色。
            ai: AI 组件实例。
            attack_type: 攻击类型（物理/魔法）。
        """
        self.entity = Entity(x, y, self.DEFAULT_SIZE, self.DEFAULT_SIZE)
        self.combat = CombatStats(max_hp, attack,
                                  physical_defense, magical_defense)
        self.name = name
        self.color = color
        self._last_attack_time = 0.0
        self.ai = ai if ai is not None else MonsterAI()
        self.is_boss = False
        self.attack_type = attack_type

    # =========================================================
    #  战斗接口
    # =========================================================

    def take_damage(self, amount: int) -> bool:
        """受到伤害 —— 委托给战斗组件。

        参数：
            amount: 伤害值。

        返回：
            True 表示怪物死亡。
        """
        self.combat.take_damage(amount)
        return not self.combat.is_alive

    def can_attack(self, game_time: float) -> bool:
        """检查攻击冷却是否就绪。

        参数：
            game_time: 当前游戏运行时间（秒）。

        返回：
            True 表示可以攻击。
        """
        return (game_time - self._last_attack_time) >= self.ATTACK_COOLDOWN

    def update_ai(self, player, game_map, delta_time: float,
                  game_time: float, monsters: list | None = None,
                  effects: list | None = None):
        """委托 AI 组件更新行为 —— 状态决策 + 巡逻/追击/攻击执行。

        参数：
            player: 玩家实例。
            game_map: 地图实例。
            delta_time: 帧耗时。
            game_time: 游戏运行时间。
            monsters: 怪物列表。
            effects: 攻击特效列表（由引擎传入）。
        """
        self.ai.update(self, player, game_map, delta_time,
                       game_time, monsters, effects)

    def attack_target(self, target, game_time: float = 0.0) -> int:
        """攻击目标 —— 使用怪物自身的 attack_type。

        参数：
            target: 被攻击目标。
            game_time: 时间戳。

        返回：
            实际伤害值。
        """
        effective_atk = self.combat.get_effective_attack()
        target_def = target.combat.get_effective_defense(self.attack_type)
        damage = calculate_damage(effective_atk, target_def, self.attack_type)
        target.combat.take_damage(damage)
        self._last_attack_time = game_time
        return damage

    # =========================================================
    #  渲染
    # =========================================================

    def render(self, screen: pygame.Surface,
               camera_x: int = 0, camera_y: int = 0):
        """绘制怪物（阴影 + 血条 + boss光晕 + 种族细节）。"""
        dr = self.entity.rect.move(-camera_x, -camera_y)
        # Boss 光晕
        if self.is_boss:
            import math, time
            pulse = int(3 + abs(math.sin(time.time() * 6)) * 5)
            glow = dr.inflate(pulse * 2, pulse * 2)
            pygame.draw.rect(screen, (60, 5, 5), glow, 3, border_radius=8)
        # 阴影
        sh = dr.inflate(-2, -2).move(2, 3)
        pygame.draw.ellipse(screen, (0, 0, 0, 80), sh)
        # 身体
        r = 4
        pygame.draw.rect(screen, self.color, dr, border_radius=r)
        # 高光
        hl = self._lighten_color(self.color, 60)
        pygame.draw.rect(screen, hl, (dr.x + 3, dr.y + 2, dr.w - 6, 6), border_radius=3)
        # 眼睛
        self._draw_monster_eyes(screen, dr)
        # 边框
        bc = (255, 180, 30) if self.is_boss else (0, 0, 0)
        pygame.draw.rect(screen, bc, dr, 2, border_radius=r)
        # 血条（非Boss且受伤时）
        if not self.is_boss and self.combat.current_hp < self.combat.max_hp:
            ratio = self.combat.current_hp / self.combat.max_hp
            bwy, bwx, bwh = dr.y - 8, dr.x, 4
            pygame.draw.rect(screen, (40, 10, 10), (bwx, bwy, dr.w, bwh))
            if ratio > 0.5:
                hc = (200, 40, 40)
            else:
                hc = (200, 20, 20)
            pygame.draw.rect(screen, hc, (bwx, bwy, int(dr.w * ratio), bwh))

    def _draw_monster_eyes(self, screen, dr: pygame.Rect):
        """绘制怪物眼睛。"""
        if "史莱姆" in self.name:
            # 大圆眼
            ey = dr.y + dr.h // 2 - 2
            pygame.draw.circle(screen, (255, 255, 255),
                               (dr.x + dr.w // 3, ey), 5)
            pygame.draw.circle(screen, (255, 255, 255),
                               (dr.x + dr.w * 2 // 3, ey), 5)
            pygame.draw.circle(screen, (20, 20, 20),
                               (dr.x + dr.w // 3 + 1, ey + 1), 3)
            pygame.draw.circle(screen, (20, 20, 20),
                               (dr.x + dr.w * 2 // 3 + 1, ey + 1), 3)
        elif "兽人" in self.name:
            # 三角怒眼
            ey = dr.y + dr.h // 2 - 1
            for sx in [dr.x + 5, dr.x + dr.w - 9]:
                pts = [(sx, ey), (sx + 5, ey + 2), (sx, ey + 5)]
                pygame.draw.polygon(screen, (255, 50, 50), pts)

    @staticmethod
    def _lighten_color(c: tuple, amt: int) -> tuple:
        return tuple(min(255, v + amt) for v in c[:3])


def spawn_monster(x: int, y: int, monster_type: str = "slime") -> Monster:
    """工厂函数 —— 根据类型创建怪物。

    当前支持的类型只定义了"slime"，后续读取 JSON 配置。
    这是一个便捷入口，方便地图生成时调用。

    参数：
        x, y: 像素坐标。
        monster_type: 怪物类型标识符。

    返回：
        Monster 实例。
    """
    presets = {
        "slime": {"name": "史莱姆", "max_hp": 15, "attack": 3,
                  "physical_defense": 0, "magical_defense": 1,
                  "color": (100, 180, 100),
                  "attack_type": AttackType.PHYSICAL},
        "orc": {"name": "兽人", "max_hp": 30, "attack": 7,
                "physical_defense": 3, "magical_defense": 1,
                "color": (200, 80, 80),
                "attack_type": AttackType.PHYSICAL},
    }
    cfg = presets.get(monster_type, presets["slime"])
    return Monster(x, y, **cfg)
