"""
──────────────────────────────────────────
怪物 AI 组件 —— 状态机驱动的行为系统
──────────────────────────────────────────

职责：
  - 管理怪物的行为状态（IDLE / CHASE / ATTACK）。
  - 每帧根据玩家距离决定状态切换。
  - 在对应状态下执行巡逻、追击、攻击逻辑。

设计原则：
  - AI 是一个独立的可替换组件，不耦合 Monster 内部细节。
  - Boss 可通过替换 ai 实例实现不同行为模式。
  - 移动和攻击委托给 Monster 的已有接口，AI 只做决策。
"""

import math
import random
from enum import Enum, auto
from config import (TILE_SIZE, PLAYER_ATTACK_RANGE,
                     MONSTER_SIGHT_RANGE, MONSTER_MOVE_SPEED,
                     MONSTER_PATROL_INTERVAL)


class AIState(Enum):
    """怪物 AI 状态枚举。"""
    IDLE = auto()               # 巡逻：随机方向移动
    CHASE = auto()              # 追击：向玩家移动
    ATTACK = auto()             # 攻击：站定并尝试攻击


class MonsterAI:
    """通用怪物 AI —— 状态机驱动的行为组件。

    属性：
        state: 当前行为状态（AIState 枚举值）。
        sight_range: 发现玩家的距离阈值（瓦片数）。
        move_speed: 移动速度（像素/秒）。
        patrol_interval: 巡逻时切换随机方向的间隔（秒）。
        _patrol_timer: 当前巡逻方向剩余时间（秒）。
        _patrol_dir: 当前巡逻方向向量 (dx, dy)，归一化。
    """

    def __init__(self,
                 sight_range: int = MONSTER_SIGHT_RANGE,
                 move_speed: int = MONSTER_MOVE_SPEED,
                 patrol_interval: float = MONSTER_PATROL_INTERVAL,
                 attack_range: float = PLAYER_ATTACK_RANGE):
        """创建 AI 组件。

        参数：
            sight_range: 视野范围（瓦片数）。
            move_speed: 移动速度（像素/秒），通常慢于玩家。
            patrol_interval: 巡逻方向持续时长（秒）。
            attack_range: 攻击触发距离（瓦片数）。
        """
        self.state = AIState.IDLE
        self.sight_range = sight_range
        self.move_speed = move_speed
        self.patrol_interval = patrol_interval
        self.attack_range = attack_range
        self._patrol_timer = 0.0
        self._patrol_dir = (0.0, 0.0)
        self._pick_new_patrol_direction()

    # =========================================================
    #  主更新入口
    # =========================================================

    def update(self, monster, player, game_map,
               delta_time: float, game_time: float,
               monsters: list | None = None,
               effects: list | None = None):
        """每帧更新 AI —— 状态机决策 + 行为执行。

        effects 由引擎传入，攻击命中时写入特效 dict。

        参数：
            monster: 宿主怪物实例。
            player: 玩家实例。
            game_map: 地图实例。
            delta_time: 帧耗时。
            game_time: 游戏运行时间。
            monsters: 怪物列表（Boss 召唤技能需要）。
            effects: 攻击特效列表（引擎持有）。
        """
        if not monster.combat.is_alive:
            return
        self._decide_state(monster, player)
        if self.state == AIState.IDLE:
            self._execute_idle(monster, game_map, delta_time)
        elif self.state == AIState.CHASE:
            self._execute_chase(monster, player, game_map, delta_time)
        elif self.state == AIState.ATTACK:
            self._execute_attack(monster, player, game_time, effects)

    # =========================================================
    #  状态决策
    # =========================================================

    def _decide_state(self, monster, player):
        """根据与玩家的距离决定当前行为状态。

        参数：
            monster: 宿主怪物。
            player: 玩家。
        """
        dist = self._distance_to(monster, player)
        attack_range_px = self.attack_range * TILE_SIZE
        sight_range_px = self.sight_range * TILE_SIZE

        if dist <= attack_range_px:
            self.state = AIState.ATTACK
        elif dist <= sight_range_px:
            self.state = AIState.CHASE
        else:
            self.state = AIState.IDLE

    # =========================================================
    #  各状态行为
    # =========================================================

    def _execute_idle(self, monster, game_map, delta_time: float):
        """IDLE 状态 —— 沿随机方向移动，定时切换方向。

        参数：
            monster: 宿主怪物。
            game_map: 地图（用于碰撞检测）。
            delta_time: 帧耗时。
        """
        self._patrol_timer -= delta_time
        if self._patrol_timer <= 0:
            self._pick_new_patrol_direction()
            self._patrol_timer = self.patrol_interval
        self._apply_movement(monster, game_map,
                             self._patrol_dir[0], self._patrol_dir[1],
                             delta_time)

    def _execute_chase(self, monster, player, game_map, delta_time: float):
        """CHASE 状态 —— 向玩家最后已知位置移动。

        参数：
            monster: 宿主怪物。
            player: 玩家。
            game_map: 地图（用于碰撞检测）。
            delta_time: 帧耗时。
        """
        dx = player.entity.rect.centerx - monster.entity.rect.centerx
        dy = player.entity.rect.centery - monster.entity.rect.centery
        dist = math.hypot(dx, dy)
        if dist < 1:
            return                          # 已经重合，无需移动
        move_x = dx / dist
        move_y = dy / dist
        self._apply_movement(monster, game_map, move_x, move_y, delta_time)

    def _execute_attack(self, monster, player, game_time: float,
                        effects: list | None = None):
        """ATTACK 状态 —— 冷却就绪时攻击玩家 + 白色闪烁特效。

        参数：
            monster: 宿主怪物。
            player: 玩家。
            game_time: 游戏时间戳。
            effects: 特效列表。
        """
        if monster.can_attack(game_time):
            monster.attack_target(player, game_time)
            if effects is not None:
                from src.fx_engine import monsters_attack_fx
                effects += monsters_attack_fx(
                    monster.entity.rect.centerx, monster.entity.rect.centery,
                    player.entity.rect.centerx, player.entity.rect.centery,
                    monster.color if hasattr(monster, "color") else (255, 255, 255))

    # =========================================================
    #  移动工具
    # =========================================================

    def _apply_movement(self, monster, game_map,
                        move_x: float, move_y: float, delta_time: float):
        """分轴移动 + 地图碰撞检测（与玩家移动逻辑一致）。

        先试 X 轴，受阻回退；再试 Y 轴，受阻回退。实现沿墙滑动。

        参数：
            monster: 要移动的怪物。
            game_map: 地图（碰撞检测用）。
            move_x, move_y: 移动方向向量（归一化）。
            delta_time: 帧耗时。
        """
        entity = monster.entity
        speed = self.move_speed

        # X 轴
        entity.position.x += move_x * speed * delta_time
        entity.sync_rect()
        if not game_map.is_rect_walkable(entity.rect):
            entity.position.x -= move_x * speed * delta_time
            entity.sync_rect()

        # Y 轴
        entity.position.y += move_y * speed * delta_time
        entity.sync_rect()
        if not game_map.is_rect_walkable(entity.rect):
            entity.position.y -= move_y * speed * delta_time
            entity.sync_rect()

    # =========================================================
    #  辅助工具
    # =========================================================

    def _distance_to(self, monster, player) -> float:
        """计算怪物与玩家的中心点距离（像素）。

        参数：
            monster: 宿主怪物。
            player: 玩家。

        返回：
            欧氏距离（像素）。
        """
        dx = monster.entity.rect.centerx - player.entity.rect.centerx
        dy = monster.entity.rect.centery - player.entity.rect.centery
        return math.hypot(dx, dy)

    def _pick_new_patrol_direction(self):
        """随机选择一个巡逻方向（不下、左、右、停）并归一化。

        30% 概率停留（方向为 0），让怪物显得不那么机械。
        """
        if random.random() < 0.3:
            self._patrol_dir = (0.0, 0.0)
            return
        # 八方向中随机选一
        candidates = [
            (-1, -1), (0, -1), (1, -1),
            (-1,  0),          (1,  0),
            (-1,  1), (0,  1), (1,  1),
        ]
        dx, dy = random.choice(candidates)
        length = math.hypot(dx, dy)
        if length > 0:
            dx /= length
            dy /= length
        self._patrol_dir = (dx, dy)
