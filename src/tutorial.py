"""
──────────────────────────────────────────
新手教程系统 — 分阶段引导玩家熟悉操作
──────────────────────────────────────────

职责：
  - 定义教程阶段枚举和每阶段的提示/完成条件。
  - 提供教程专用的小地图、无害怪物、引导道具。
  - 检测玩家行为，自动推进阶段。

设计原则：
  - 全部逻辑集中在 TutorialGuide 类中，不污染 engine。
  - 每阶段只检查一个操作，完成后自动进入下一阶段。
  - 教程怪物用"木桩 AI"（不移动不攻击）。
"""

import math
from enum import Enum, auto
from config import TILE_SIZE
from src.world.game_map import GameMap
from src.entities.ai import MonsterAI
from src.entities.monster import Monster
from src.entities.item import (DroppedItem, EquipmentItem, ConsumableItem, Rarity)
from src.entities.skill import SlashSkill


class TutorialStage(Enum):
    """教程阶段枚举 — 按学习顺序排列。"""
    WELCOME = auto()          # 欢迎
    MOVE = auto()             # WASD 移动
    ATTACK = auto()           # 空格攻击
    PICKUP = auto()           # E 拾取
    INVENTORY = auto()        # I 开背包 + U 使用
    EQUIP = auto()            # X 装备（在背包内）
    SKILL = auto()            # 1 释放技能
    COMPLETE = auto()         # 完成


# 教程专用 AI：完全不动不攻击的木桩
class DummyAI(MonsterAI):
    """教程木桩 AI —— 不移动、不攻击。"""

    def __init__(self):
        super().__init__(sight_range=0, move_speed=0, patrol_interval=999)

    def update(self, monster, player, game_map,
               delta_time: float, game_time: float,
               monsters: list | None = None):
        pass          # 什么都不做


class TutorialGuide:
    """新手教程向导 — 管理阶段、提示和条件检测。

    属性：
        stage: 当前教程阶段。
        move_distance: 玩家累计移动距离（用于判断"移动"完成）。
        _last_pos: 上一帧玩家位置。
        attack_hits: 玩家对木桩的攻击次数。
        picked_up: 是否已拾取物品。
        item_used: 是否已在背包中使用物品。
        equipped: 是否已装备物品。
        skill_used: 是否已释放技能。
    """

    def __init__(self):
        self.stage = TutorialStage.WELCOME
        self.move_distance = 0.0
        self._last_pos = (0.0, 0.0)
        self._last_pos_set = False
        self.attack_hits = 0
        self.picked_up = False
        self.item_used = False
        self.equipped = False
        self.skill_used = False

    # =========================================================
    #  阶段脚本：提示文字 + 完成条件
    # =========================================================

    def get_stage_instructions(self) -> list[str]:
        """返回当前阶段的提示文字列表，每行一条。"""
        scripts = {
            TutorialStage.WELCOME: [
                "══════════════════════════════════════",
                "  欢迎来到 Roguelike 新手教程！",
                "",
                "  ┌──── 按键功能一览 ────┐",
                "  │ W 上移  S 下移       │",
                "  │ A 左移  D 右移       │",
                "  │ ↑↓←→  切换朝向       │",
                "  │ 空格   攻击最近敌人    │",
                "  │ E      拾取地面物品    │",
                "  │ I      打开/关闭背包   │",
                "  │ 1-4    释放主动技能    │",
                "  │ U(背包) 使用药水      │",
                "  │ X(背包) 装备武器/护甲 │",
                "  │ D(背包) 丢弃物品      │",
                "  │ Esc   退出  T  跳过    │",
                "  └───────────────────────┘",
                "  攻击时会出现金色范围圈",
                "  按 Enter 或 空格 开始练习！",
                "══════════════════════════════════════",
            ],
            TutorialStage.MOVE: [
                "═══════════════════════════════════",
                "  第 1 步：移动",
                "",
                "  按键    功能",
                "  ─────  ─────────────────",
                "  W       向上移动",
                "  S       向下移动",
                "  A       向左移动",
                "  D       向右移动",
                "  ↑↓←→   只改朝向不移动",
                "",
                "  试着在地图中走几步吧！",
                "═══════════════════════════════════",
            ],
            TutorialStage.ATTACK: [
                "═══════════════════════════════════",
                "  第 2 步：普通攻击",
                "",
                "  按键    功能",
                "  ─────  ─────────────────",
                "  空格    攻击范围内最近的敌人",
                "",
                "  走近绿色木桩按 空格 攻击！",
                "  (金色圆圈 = 攻击范围)",
                "═══════════════════════════════════",
            ],
            TutorialStage.PICKUP: [
                "═══════════════════════════════════",
                "  第 3 步：拾取物品",
                "",
                "  按键    功能",
                "  ─────  ─────────────────",
                "  E       拾取脚下最近的战利品",
                "",
                "  击杀怪物会掉落装备/药水",
                "  走过去按 E 键捡起来！",
                "═══════════════════════════════════",
            ],
            TutorialStage.INVENTORY: [
                "═══════════════════════════════════",
                "  第 4 步：背包与使用物品",
                "",
                "  按键    功能",
                "  ─────  ─────────────────",
                "  I       打开/关闭背包面板",
                "  ↑↓      移动光标选择物品",
                "  U       使用选中物品（药水回血）",
                "  X       装备选中武器或护甲",
                "  D       丢弃选中物品",
                "  Esc     关闭背包",
                "",
                "  按 I 打开背包 → ↑↓ 选中药水",
                "  → 按 U 使用它来回血！",
                "═══════════════════════════════════",
            ],
            TutorialStage.EQUIP: [
                "═══════════════════════════════════",
                "  第 5 步：装备武器/护甲",
                "",
                "  按键    功能",
                "  ─────  ─────────────────",
                "  X(背包) 穿上选中装备",
                "          自动替换同槽位旧装备",
                "",
                "  装备后 HUD 左上角 ATK/DEF 会变化",
                "",
                "  按 I 打开背包 → ↑↓ 选中武器",
                "  → 按 X 装备它！",
                "═══════════════════════════════════",
            ],
            TutorialStage.SKILL: [
                "═══════════════════════════════════",
                "  第 6 步：使用技能",
                "",
                "  按键    功能",
                "  ─────  ─────────────────",
                "  1-4     释放对应槽位的主动技能",
                "",
                "  ── 游戏中共有 6 种技能 ──",
                "  主动技能（1-4 释放，可升到 Lv5）：",
                "  [斩击] 前方扇形物理伤害  ATK×1.5  CD 2s",
                "  [神罚] 远程单体魔法伤害 ATK×2.5  CD 5s",
                "  [自愈] 恢复自身生命   MaxHP×20% CD 8s",
                "  [TheWorld] 时停5秒 伤害结算 CD20s",
                "",
                "  物理攻击受物理防御减免",
                "  魔法攻击受魔法防御减免",
                "  被动技能（习得后常驻生效）：",
                "  [铁壁] 永久 +DEF    [狂暴] 永久 +ATK",
                "",
                "  每次觉醒不会重复获得已掌握的技能！",
                "",
                "  杀怪有 15% 概率习得新技能！",
                "  你已习得【斩击】，走到木桩旁",
                "  按 数字 1 释放！",
                "═══════════════════════════════════",
            ],
            TutorialStage.COMPLETE: [
                "═══════════════════════════════════",
                "  恭喜！你已完成所有基础训练！",
                "",
                "  ┌──── 完整按键速查 ────┐",
                "  │ W A S D  上下左右移动 │",
                "  │ ↑↓←→    切换朝向     │",
                "  │ 空格     普通攻击     │",
                "  │ 1-4      主动技能     │",
                "  │ E        拾取物品     │",
                "  │ I        打开背包     │",
                "  │ T        进入教程     │",
                "  │ Enter    确认/开始    │",
                "  │ Esc      返回/退出    │",
                "  └───────────────────────┘",
                "      背包内        地图界面",
                "  │ ↑↓ 选择光标  │ E 拾取     │",
                "  │ X  装备物品  │            │",
                "  │ U  使用药水  │            │",
                "  │ D  丢弃物品  │            │",
                "  │ I  关闭背包  │            │",
                "",
                "  按 Enter 返回标题 · 开始冒险！",
                "═══════════════════════════════════",
            ],
        }
        return scripts.get(self.stage, [])

    # =========================================================
    #  条件检测 — 每帧由 engine 调用
    # =========================================================

    def check_and_advance(self, player, engine_state: dict):
        """检测当前阶段完成条件，满足则推进。

        参数：
            player: 玩家实例。
            engine_state: {
                "game_time": float,
                "inventory_open": bool,
                "monsters": list,
                "ground_items": list,
            }
        """
        if self.stage == TutorialStage.WELCOME:
            pass        # 等 Enter

        elif self.stage == TutorialStage.MOVE:
            self._check_move(player)

        elif self.stage == TutorialStage.ATTACK:
            self._check_attack(engine_state.get("monsters", []))

        elif self.stage == TutorialStage.PICKUP:
            self._check_pickup(player, engine_state.get("ground_items", []))

        elif self.stage == TutorialStage.INVENTORY:
            self._check_inventory_use(player)

        elif self.stage == TutorialStage.EQUIP:
            self._check_equip(player)

        elif self.stage == TutorialStage.SKILL:
            self._check_skill()

    def advance_stage(self):
        """手动推进到下一阶段。"""
        stages = list(TutorialStage)
        idx = stages.index(self.stage)
        if idx < len(stages) - 1:
            self.stage = stages[idx + 1]
            # 重置本阶段相关计数器
            if self.stage == TutorialStage.ATTACK:
                self.attack_hits = 0
            if self.stage == TutorialStage.MOVE:
                self.move_distance = 0.0
                self._last_pos_set = False

    # =========================================================
    #  各阶段检测逻辑
    # =========================================================

    def _check_move(self, player):
        """累计移动距离超过 120 像素（约 4 格）则过关。"""
        px, py = player.entity.position.x, player.entity.position.y
        if not self._last_pos_set:
            self._last_pos = (px, py)
            self._last_pos_set = True
            return
        dx = px - self._last_pos[0]
        dy = py - self._last_pos[1]
        self.move_distance += math.hypot(dx, dy)
        self._last_pos = (px, py)
        if self.move_distance > 120:
            self.advance_stage()

    def _check_attack(self, monsters: list):
        """已攻击 1 次即过关（检查木桩是否掉血）。"""
        for m in monsters:
            if m.combat.current_hp < m.combat.max_hp:
                self.attack_hits += 1
                m.combat.current_hp = m.combat.max_hp    # 重置 HP 以便练习
                break
        if self.attack_hits >= 1:
            self.advance_stage()

    def _check_pickup(self, player, ground_items: list):
        """地面物品消失（被拾取）则过关。"""
        if len(ground_items) < 2:          # 初始 2 个，捡了至少 1 个
            self.picked_up = True
            self.advance_stage()

    def _check_inventory_use(self, player):
        """检测玩家是否在背包中使用过药水（HP > 初始值）。"""
        if player.combat.current_hp > 90:
            self.item_used = True
            self.advance_stage()

    def _check_equip(self, player):
        """检测玩家是否已装备武器。"""
        if player.inventory.equipped.get("weapon") is not None:
            self.equipped = True
            self.advance_stage()

    def _check_skill(self):
        """检测技能是否被使用过（由引擎通知）。"""
        if self.skill_used:
            self.advance_stage()

    def notify_skill_used(self):
        """引擎调用此方法通知技能已被释放。"""
        self.skill_used = True


# =========================================================
#  教程地图建造
# =========================================================

def build_tutorial_map() -> GameMap:
    """创建教程专用小地图 —— 一个 5x7 的封闭房间。

    返回：
        加载了教程地形的 GameMap。
    """
    w, h = 12, 9
    game_map = GameMap(w, h, TILE_SIZE)
    template = []
    for row in range(h):
        line = ""
        for col in range(w):
            if row == 0 or row == h - 1 or col == 0 or col == w - 1:
                line += '#'
            else:
                line += '.'
        template.append(line)
    game_map.load_from_template(template)
    return game_map


def create_tutorial_dummy(tile_x: int, tile_y: int) -> Monster:
    """创建教程木桩 —— 站着不动、不会攻击的练习目标。

    参数：
        tile_x, tile_y: 瓦片坐标。

    返回：
        挂载 DummyAI 的 Monster 实例。
    """
    px = tile_x * TILE_SIZE
    py = tile_y * TILE_SIZE
    dummy = Monster(px, py, name="训练木桩",
                    max_hp=9999, attack=0,
                    physical_defense=0, magical_defense=0,
                    color=(60, 180, 60), ai=DummyAI())
    return dummy


def create_tutorial_items(tile_x: int, tile_y: int) -> list[DroppedItem]:
    """在指定瓦片位置生成教程道具（药水 + 武器）。

    参数：
        tile_x, tile_y: 放置药水的瓦片坐标。

    返回：
        DroppedItem 列表：[药水, 武器]。
    """
    potion = ConsumableItem("初级生命药水", Rarity.COMMON, "heal", 20)
    weapon = EquipmentItem("训练用短剑", Rarity.COMMON,
                           "weapon", atk_bonus=4, pdef_bonus=1, mdef_bonus=0)
    return [
        DroppedItem(potion, tile_x, tile_y),
        DroppedItem(weapon, tile_x + 1, tile_y),
    ]


def give_tutorial_skill(player) -> bool:
    """给玩家一个教程技能（斩击）。

    参数：
        player: Player 实例。

    返回：
        True 表示成功。
    """
    skill = SlashSkill()
    return player.skills.learn(skill)
