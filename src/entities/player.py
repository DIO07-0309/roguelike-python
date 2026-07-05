"""
──────────────────────────────────────────
玩家类 —— 处理移动、朝向、动画/碰撞接口
──────────────────────────────────────────

职责：
  - 响应 WASD 键盘输入，移动角色。
  - 响应方向键，切换朝向（不移动）。
  - 提供动画播放接口（预留，后续接精灵图）。
  - 提供碰撞检测接口（预留，后续接地图形）。

设计原则：
  - 玩家不直接操作 pygame 事件 —— 由 GameEngine 传递按键状态。
  - 移动逻辑和渲染分离，Player 只存朝向状态，渲染器负责绘制。
"""

from enum import Enum, auto
import math
import pygame
from src.entities.entity import Entity
from src.entities.components import CombatStats, AttackType
from src.systems.combat_system import calculate_damage
from src.systems.inventory_system import Inventory
from src.entities.skill import SkillManager


class Direction(Enum):
    """角色朝向枚举 —— 四方向。"""
    DOWN = auto()       # 向下（默认朝向）
    UP = auto()         # 向上
    LEFT = auto()       # 向左
    RIGHT = auto()      # 向右


class Player:
    """玩家角色 —— 持有实体、移动速度、朝向状态。

    属性：
        entity: 底层实体（位置 / 尺寸 / 碰撞框）。
        speed: 移动速度（像素/秒）。
        direction: 当前朝向（Direction 枚举）。
        is_moving: 当前帧是否在移动中（用于动画切换）。
    """

    # ---- 尺寸常量 ----
    PLAYER_WIDTH = 32
    PLAYER_HEIGHT = 32
    ATTACK_COOLDOWN = 0.5                # 攻击冷却（秒）

    def __init__(self, start_x: float, start_y: float, speed: int,
                 max_hp: int = 100, attack: int = 10,
                 physical_defense: int = 3, magical_defense: int = 1,
                 inv_capacity: int = 16):
        """创建玩家。

        参数：
            start_x, start_y: 初始像素坐标。
            speed: 移动速度。
            max_hp: 最大生命值。
            attack: 基础攻击力。
            physical_defense: 物理防御力。
            magical_defense: 魔法防御力。
            inv_capacity: 背包格数。
        """
        self.entity = Entity(start_x, start_y,
                             self.PLAYER_WIDTH, self.PLAYER_HEIGHT)
        self.speed = speed
        self.direction = Direction.DOWN
        self.is_moving = False
        self.combat = CombatStats(max_hp, attack,
                                  physical_defense, magical_defense)
        self._last_attack_time = -999.0
        # 玩家的攻击类型：普攻为物理
        self.attack_type = AttackType.PHYSICAL
        # 背包系统
        self.inventory = Inventory(inv_capacity)
        # 技能系统
        self.skills = SkillManager()
        # 等级系统
        self.level = 1
        self.xp = 0
        self.xp_to_next = self._calc_xp_for_level(2)

    def reset_attack_timers(self):
        """重置所有攻击和技能的冷却时间戳。

        用于进入新楼层时，确保攻击和技能立即可用。
        """
        self._last_attack_time = -999.0
        for skill in self.skills.active_skills:
            skill._last_use_time = -999.0

    # =========================================================
    #  等级系统
    # =========================================================

    @staticmethod
    def _calc_xp_for_level(lvl: int) -> int:
        """计算升到指定等级所需的总经验。

        公式：lvl² × 20，如 Lv1→Lv2 需 80 XP。

        参数：
            lvl: 目标等级。

        返回：
            总经验值。
        """
        return lvl * lvl * 20

    def give_xp(self, amount: int) -> bool:
        """获得经验，检查是否升级。

        升级时：HP 回满，ATK+2，DEF+1，MaxHP+10。
        若主动技能未满 4 个，自动习得一个不重复的新技能。

        参数：
            amount: 获得的经验值。

        返回：
            True 表示升级了。
        """
        self.xp += amount
        if self.xp < self.xp_to_next:
            return False
        self.level += 1
        self.xp -= self.xp_to_next
        self.xp_to_next = self._calc_xp_for_level(self.level + 1)
        self.combat.attack += 2
        self.combat.physical_defense += 1
        self.combat.magical_defense += 1
        self.combat.max_hp += 10
        self.combat.current_hp = self.combat.max_hp
        # 升级奖励：技能未满→必学新；已满→随机升级一项
        import random
        from src.entities.skill import random_skill, get_learned_skill_names
        upgradeable = [s for s in self.skills.active_skills if s.can_upgrade()]
        can_learn = self.skills.can_learn()
        if can_learn:
            self._learn_new_skill()
        elif upgradeable:
            random.choice(upgradeable).upgrade()
        return True

    def _learn_new_skill(self):
        """学习一个新主动技能（不重复，优先填满4槽）。"""
        from src.entities.skill import random_active_skill, get_learned_skill_names
        names = get_learned_skill_names(self.skills)
        new_skill = random_active_skill(names)
        self.skills.learn(new_skill)
        self.skills.apply_all_passives(self)

    def get_level_info(self) -> tuple[int, int, int]:
        """返回 (等级, 当前经验, 升级所需经验)。"""
        return self.level, self.xp, self.xp_to_next

    def auto_level_to(self, target_level: int):
        """自动升级到目标等级（用于选关补偿）。"""
        while self.level < target_level:
            self.xp = self.xp_to_next   # 强制达标
            self.give_xp(0)             # 触发升级

    # =========================================================
    #  输入处理
    # =========================================================

    def handle_input(self, keys: pygame.key.ScancodeWrapper):
        """响应键盘输入 —— WASD 移动，方向键改朝向。

        参数：
            keys: pygame.key.get_pressed() 返回的按键状态字典。
        """
        move_x = 0
        move_y = 0

        # ---- WASD 移动 ----
        if keys[pygame.K_w]:
            move_y -= 1
            self.direction = Direction.UP
        elif keys[pygame.K_s]:
            move_y += 1
            self.direction = Direction.DOWN
        if keys[pygame.K_a]:
            move_x -= 1
            self.direction = Direction.LEFT
        elif keys[pygame.K_d]:
            move_x += 1
            self.direction = Direction.RIGHT

        # ---- 方向键仅改朝向（不移动） ----
        if keys[pygame.K_UP]:
            self.direction = Direction.UP
        elif keys[pygame.K_DOWN]:
            self.direction = Direction.DOWN
        if keys[pygame.K_LEFT]:
            self.direction = Direction.LEFT
        elif keys[pygame.K_RIGHT]:
            self.direction = Direction.RIGHT

        # 归一化斜向移动，避免速度过快
        if move_x != 0 and move_y != 0:
            factor = math.sqrt(2) / 2
            move_x *= factor
            move_y *= factor

        self.is_moving = (move_x != 0 or move_y != 0)
        return move_x, move_y

    # =========================================================
    #  更新 & 渲染
    # =========================================================

    def update(self, delta_time: float):
        """更新玩家逻辑。

        参数：
            delta_time: 上一帧耗时（秒）。
        """
        # 当前帧更新逻辑很简单 —— 后续动画 ticker 放这里
        pass

    def render(self, screen: pygame.Surface,
               camera_x: int = 0, camera_y: int = 0):
        """绘制玩家（阴影 + 圆角身体 + 朝向瞳孔）。"""
        dr = self.entity.rect.move(-camera_x, -camera_y)
        # 1. 阴影
        shadow = dr.inflate(-4, -4).move(3, 4)
        pygame.draw.ellipse(screen, (0, 0, 0, 100), shadow)
        # 2. 身体（圆角矩形）
        body = pygame.Rect(dr.x + 3, dr.y + 2, dr.w - 6, dr.h - 4)
        pygame.draw.rect(screen, (40, 160, 40), body, border_radius=6)
        # 身体高光
        pygame.draw.rect(screen, (80, 210, 80),
                         (dr.x + 5, dr.y + 3, dr.w - 10, 8), border_radius=3)
        # 3. 护肩（双角）
        pygame.draw.rect(screen, (100, 180, 100),
                         (dr.x, dr.y + 8, 6, 16), border_radius=2)
        pygame.draw.rect(screen, (100, 180, 100),
                         (dr.right - 6, dr.y + 8, 6, 16), border_radius=2)
        # 4. 朝向瞳孔
        self._draw_player_eye(screen, dr)

    def _draw_player_eye(self, screen, dr: pygame.Rect):
        """绘制带方向的瞳孔（白眼球+黑瞳孔偏移）。"""
        cx, cy = dr.centerx, dr.centery
        # 白色眼球
        pygame.draw.circle(screen, (255, 255, 255), (cx, cy), 5)
        # 瞳孔偏移
        offsets = {Direction.UP: (0, -3), Direction.DOWN: (0, 3),
                   Direction.LEFT: (-3, 0), Direction.RIGHT: (3, 0)}
        ox, oy = offsets.get(self.direction, (0, 3))
        pygame.draw.circle(screen, (20, 20, 20), (cx + ox, cy + oy), 3)

    def _get_direction_triangle(self, draw_rect: pygame.Rect = None):
        """根据当前朝向计算指示三角的三个顶点。

        参数：
            draw_rect: 绘制时的矩形位置（含摄像机偏移）。
                      为 None 时使用 entity.rect。

        返回：
            3 个 (x, y) 坐标的列表，或 None（朝向未设置时）。
        """
        if draw_rect is None:
            draw_rect = self.entity.rect
        cx = draw_rect.centerx
        cy = draw_rect.centery
        size = 8
        # 每个朝向对应的三角顶点
        triangles = {
            Direction.UP:    [(cx, cy - size), (cx - size, cy + size), (cx + size, cy + size)],
            Direction.DOWN:  [(cx, cy + size), (cx - size, cy - size), (cx + size, cy - size)],
            Direction.LEFT:  [(cx - size, cy), (cx + size, cy - size), (cx + size, cy + size)],
            Direction.RIGHT: [(cx + size, cy), (cx - size, cy - size), (cx - size, cy + size)],
        }
        return triangles.get(self.direction)

    # =========================================================
    #  动画接口（预留 —— 后续接入精灵帧动画）
    # =========================================================

    def play_animation(self, animation_name: str):
        """播放指定动画（预留接口）。

        参数：
            animation_name: 动画名称，如 "walk"、"idle"、"attack"。
        """
        # TODO: 精灵图加载后实现帧切换逻辑
        pass

    def get_current_frame(self) -> pygame.Surface | None:
        """获取当前动画帧（预留接口）。

        返回：
            当前帧 Surface 或 None（未实现时）。
        """
        # TODO: 返回动画帧 Surface
        return None

    # =========================================================
    #  碰撞接口（预留 —— 后续接入地图碰撞网格）
    # =========================================================

    def check_collision(self, obstacles: list) -> bool:
        """检测是否与障碍物碰撞（预留接口）。

        参数：
            obstacles: 障碍物矩形列表。

        返回：
            True 表示碰撞，False 表示可通行。
        """
        # TODO: 与地图墙体碰撞网格对接
        return False

    def on_collision(self, other):
        """碰撞回调（预留接口）。

        参数：
            other: 碰撞到的对象。
        """
        # TODO: 处理碰撞后的逻辑（推开、弹回等）
        pass

    # =========================================================
    #  战斗接口
    # =========================================================

    def can_attack(self, game_time: float) -> bool:
        """检查玩家攻击冷却是否就绪。

        参数：
            game_time: 当前游戏运行时间（秒）。

        返回：
            True 表示可以攻击。
        """
        return (game_time - self._last_attack_time) >= self.ATTACK_COOLDOWN

    def attack(self, target, game_time: float = 0.0) -> int:
        """攻击目标 —— 计算伤害并应用（玩家普攻=物理）。

        参数：
            target: 攻击目标。
            game_time: 当前游戏时间戳。

        返回：
            造成的实际伤害值。
        """
        effective_atk = self.combat.get_effective_attack()
        target_def = target.combat.get_effective_defense(self.attack_type)
        damage = calculate_damage(effective_atk, target_def, self.attack_type)
        target.combat.take_damage(damage)
        self._last_attack_time = game_time
        return damage

    def take_damage(self, amount: int) -> bool:
        """受到伤害 —— 委托给战斗组件。

        参数：
            amount: 伤害值。

        返回：
            True 表示玩家死亡。
        """
        self.combat.take_damage(amount)
        return not self.combat.is_alive
