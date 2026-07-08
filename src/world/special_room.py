"""
──────────────────────────────────────────
特殊房间系统 — 祭坛/宝箱/泉水
──────────────────────────────────────────

B8: 核心数据 + 统一交互入口
B9: 内容深化（祭坛4结果池 / 宝箱品质分层 / 泉水净化）
B10: 发现提示 + 消息反馈

GameScene 只调用 execute_special_room(type, player)，不感知房间细节。
"""

import random
from enum import Enum, auto


class SpecialRoomType(Enum):
    ALTAR = auto()
    TREASURE = auto()
    FOUNTAIN = auto()


class SpecialRoom:
    """特殊房间实例 —— 挂在 GameMap.special_rooms 上。

    属性:
        cx, cy: 房间中心 tile 坐标。
        rx, ry, rw, rh: 房间矩形。
        type: 房间类型 (SpecialRoomType)。
        triggered: 是否已按 E 领取过奖励。
        discovered: 是否已走进过该房间（B10）。
    """
    __slots__ = ('cx', 'cy', 'rx', 'ry', 'rw', 'rh', 'type', 'triggered', 'discovered')

    def __init__(self, cx: int, cy: int, rx: int, ry: int,
                 rw: int, rh: int, room_type: SpecialRoomType):
        self.cx = cx
        self.cy = cy
        self.rx = rx
        self.ry = ry
        self.rw = rw
        self.rh = rh
        self.type = room_type
        self.triggered = False
        self.discovered = False


def special_room_from_index(idx: int) -> SpecialRoomType:
    """生成时用: 索引 → 类型 (0=ALTAR, 1=TREASURE, 2=FOUNTAIN)。"""
    return [SpecialRoomType.ALTAR, SpecialRoomType.TREASURE, SpecialRoomType.FOUNTAIN][idx % 3]


# ---------- B9 共享辅助: 净化负面 Buff ----------

def _cleanse_debuffs(player):
    """移除玩家身上的 poison 和 slow，保留 attack_up。"""
    player.active_buffs = [b for b in player.active_buffs
                           if b.id not in ("poison", "slow")]


# ---------- B9.1 祭坛: 4 结果池 ----------

def _altar_attack_up(player):
    from src.systems.buff_system import apply_buff
    apply_buff(player, "attack_up", 1)
    return "祭坛赐福：你的攻击力提升了。"


def _altar_heal(player):
    amount = max(1, player.combat.max_hp * 3 // 10)
    player.combat.heal(amount)
    return "祭坛赐福：你的伤势恢复了。"


def _altar_blood_power(player):
    from src.systems.buff_system import apply_buff
    loss = max(1, player.combat.current_hp * 2 // 10)
    if player.combat.current_hp - loss < 1:
        loss = player.combat.current_hp - 1
    if loss > 0:
        player.combat.take_damage(loss)
    apply_buff(player, "attack_up", 2)
    return "祭坛夺取了你的生命，但赐予了更强的力量。"


def _altar_cleanse(player):
    _cleanse_debuffs(player)
    return "祭坛的光辉净化了你身上的负面状态。"


def _exec_altar(player):
    pool = [_altar_attack_up, _altar_heal, _altar_blood_power, _altar_cleanse]
    return random.choice(pool)(player)


# ---------- B9.2 宝箱: 品质分层 ----------

def _exec_treasure(player):
    from src.entities.item import generate_random_item
    from src.systems.buff_system import apply_buff

    roll = random.randint(0, 99)
    if roll < 10:
        # 祝福宝箱 (10%)
        item = generate_random_item()
        if item:
            player.inventory.add(item, player)
        apply_buff(player, "attack_up", 1)
        return "宝箱中的力量流入了你的身体。"
    elif roll < 40:
        # 丰厚宝箱 (30%)
        a = generate_random_item()
        b = generate_random_item()
        if a:
            player.inventory.add(a, player)
        if b:
            player.inventory.add(b, player)
        return "你打开了宝箱，里面装着两件战利品！"
    else:
        # 普通宝箱 (60%)
        item = generate_random_item()
        if not item:
            return "宝箱里空空如也。"
        player.inventory.add(item, player)
        return "你打开了宝箱，获得了战利品。"


# ---------- B9.3 泉水: 回满 + 净化 ----------

def _exec_fountain(player):
    missing = player.combat.max_hp - player.combat.current_hp
    if missing > 0:
        player.combat.heal(missing)
    _cleanse_debuffs(player)
    return "泉水治愈并净化了你的身体。"


# ---------- 统一交互入口 ----------

_EXECUTORS = {
    SpecialRoomType.ALTAR: _exec_altar,
    SpecialRoomType.TREASURE: _exec_treasure,
    SpecialRoomType.FOUNTAIN: _exec_fountain,
}


def execute_special_room(room_type: SpecialRoomType, player) -> str:
    """统一交互入口 —— GameScene 只调此函数。

    参数:
        room_type: 房间类型枚举。
        player: 玩家对象。

    返回:
        提示文字（用于日志 / HUD 消息）。
    """
    fn = _EXECUTORS.get(room_type)
    if fn:
        return fn(player)
    return "未知房间。"


# ---------- 发现提示 ----------

_DISCOVERY_MESSAGES = {
    SpecialRoomType.ALTAR: "你发现了一座古老祭坛。",
    SpecialRoomType.TREASURE: "你发现了一个隐藏宝箱房。",
    SpecialRoomType.FOUNTAIN: "你发现了一处治愈泉水。",
}


def get_discovery_message(room_type: SpecialRoomType) -> str:
    """返回进入房间时的发现提示文字。"""
    return _DISCOVERY_MESSAGES.get(room_type, "")
