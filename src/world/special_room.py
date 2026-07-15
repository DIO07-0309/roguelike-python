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
    SHOP = auto()
    BLACKSMITH = auto()
    LIBRARY = auto()
    GAMBLER = auto()
    SHRINE = auto()
    SECRET = auto()


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
    """生成时用: 索引 → 类型 (0-8 轮转 9 种)。"""
    return list(SpecialRoomType)[idx % 9]


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
    # B12: sage_leaf — 祭坛治疗 +10
    from src.systems.relic_system import player_has_relic
    if player_has_relic(player, "sage_leaf"):
        amount += 10
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
    from src.systems.relic_system import player_has_relic, try_grant_random_relic

    roll = random.randint(0, 99)
    msg = ""

    if roll < 10:
        item = generate_random_item()
        if item:
            player.inventory.add(item, player)
        apply_buff(player, "attack_up", 1)
        msg = "宝箱中的力量流入了你的身体。"
    elif roll < 40:
        a = generate_random_item()
        b = generate_random_item()
        if a: player.inventory.add(a, player)
        if b: player.inventory.add(b, player)
        msg = "你打开了宝箱，里面装着两件战利品！"
    else:
        item = generate_random_item()
        if not item:
            msg = "宝箱里空空如也。"
        else:
            player.inventory.add(item, player)
            msg = "你打开了宝箱，获得了战利品。"

    # B12: 宝箱品质分级 relic 掉率 (普通10% / 丰厚20% / 祝福35%)
    relic_chance = 0.35 if roll < 10 else 0.20 if roll < 40 else 0.10
    if player_has_relic(player, "merchant_coin"):
        relic_chance = min(0.95, relic_chance + 0.15)
    relic_msg = try_grant_random_relic(player, relic_chance)
    if relic_msg:
        msg += " " + relic_msg

    # B11: golden_dice — 额外物品
    if player_has_relic(player, "golden_dice"):
        extra = generate_random_item()
        if extra and player.inventory.add(extra, player):
            msg += " 金色骰子额外赐予了一件物品。"

    # B12: merchant_coin — 额外物品 (与 golden_dice 叠加)
    if player_has_relic(player, "merchant_coin"):
        extra = generate_random_item()
        if extra and player.inventory.add(extra, player):
            msg += " 商人硬币额外带来了一件物品。"

    return msg


# ---------- B9.3 泉水: 回满 + 净化 ----------

def _exec_fountain(player):
    missing = player.combat.max_hp - player.combat.current_hp
    if missing < 0:
        missing = 0
    # B12: sage_leaf — 泉水治疗 +10
    from src.systems.relic_system import player_has_relic
    if player_has_relic(player, "sage_leaf"):
        missing += 10
    if missing > 0:
        player.combat.heal(missing)
    _cleanse_debuffs(player)
    return "泉水治愈并净化了你的身体。"


# ---------- D8: 6 new room types ----------

def _exec_shop(player):
    """商店: 2件稀有+物品。"""
    from src.entities.item import generate_random_item, Rarity
    count = 0
    for _ in range(2):
        item = generate_random_item()
        tries = 0
        while item and item.rarity.value < Rarity.RARE.value and tries < 5:
            item = generate_random_item(); tries += 1
        if item and player.inventory.add(item, player):
            count += 1
    if count == 0:
        return "商店今天没有特别的货物。"
    return f"商店为你提供了{count}件货物。"

def _exec_blacksmith(player):
    """铁匠: 1件随机装备。"""
    from src.entities.item import EquipmentItem, Rarity
    eq = EquipmentItem("铁匠制品", Rarity.RARE, "weapon", atk_bonus=8, pdef_bonus=2, mdef_bonus=0)
    player.inventory.add(eq, player)
    return "铁匠为你打造了一件新装备。"

def _exec_library(player):
    """图书馆: 随机技能升级1级。"""
    active = player.skills.active_skills
    if not active:
        return "图书馆里空无一人——你还没有技能可以研习。"
    sk = random.choice(active)
    if sk.level < sk.max_level:
        sk._on_level_up()
        sk.level += 1
        return f"{sk.name} 升级了！"
    return "你研习了古籍，但没有获得新的领悟。"

def _exec_gambler(player):
    """赌徒: 60%胜率 (golden_dice→85%)。"""
    from src.entities.item import generate_random_item
    from src.systems.relic_system import player_has_relic
    win = random.random() < (0.85 if player_has_relic(player, "golden_dice") else 0.60)
    if win:
        item = generate_random_item()
        if item:
            player.inventory.add(item, player)
            return "赌徒咧嘴一笑：运气不错！"
        return "赌徒摊手：今天没货了。"
    loss = max(1, player.combat.current_hp // 5)
    player.combat.take_damage(loss)
    return f"赌徒摇头：命运不站在你这边。受到 {loss} 伤害。"

def _exec_shrine(player):
    """神殿: 祝福/治疗/relic。"""
    from src.systems.buff_system import apply_buff
    from src.systems.relic_system import player_has_relic, try_grant_random_relic
    r = random.randint(0, 2)
    if r == 0:
        apply_buff(player, "blessing", 2)
        return "神殿的光辉笼罩着你——你获得了祝福。"
    elif r == 1:
        heal = player.combat.max_hp // 2
        player.combat.heal(heal)
        return "神殿的力量治愈了你。"
    else:
        msg = try_grant_random_relic(player, 0.50)
        return f"神殿赐予了你一件圣物！{msg}" if msg else "神殿默默凝视着你。"

def _exec_secret(player):
    """隐藏房: 1 relic + 50%传说装备。"""
    from src.entities.item import EquipmentItem, Rarity
    from src.systems.relic_system import try_grant_random_relic
    msg = try_grant_random_relic(player, 1.0)
    extra = ""
    if random.random() < 0.50:
        eq = EquipmentItem("秘宝", Rarity.LEGENDARY, "weapon", atk_bonus=20, pdef_bonus=5, mdef_bonus=3)
        if player.inventory.add(eq, player):
            extra = " 而且找到了一件传说秘宝。"
    return f"你发现了一间隐藏房间！{msg}{extra}"


# ---------- 统一交互入口 ----------

_EXECUTORS = {
    SpecialRoomType.ALTAR: _exec_altar,
    SpecialRoomType.TREASURE: _exec_treasure,
    SpecialRoomType.FOUNTAIN: _exec_fountain,
    SpecialRoomType.SHOP: _exec_shop,
    SpecialRoomType.BLACKSMITH: _exec_blacksmith,
    SpecialRoomType.LIBRARY: _exec_library,
    SpecialRoomType.GAMBLER: _exec_gambler,
    SpecialRoomType.SHRINE: _exec_shrine,
    SpecialRoomType.SECRET: _exec_secret,
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
    SpecialRoomType.SHOP: "你发现了一间神秘商店。",
    SpecialRoomType.BLACKSMITH: "你发现了一间铁匠铺。",
    SpecialRoomType.LIBRARY: "你发现了一间古老的图书馆。",
    SpecialRoomType.GAMBLER: "你发现了一个赌徒的房间。",
    SpecialRoomType.SHRINE: "你发现了一座神圣的神殿。",
    SpecialRoomType.SECRET: "你发现了一间隐藏密室！",
}


def get_discovery_message(room_type: SpecialRoomType) -> str:
    """返回进入房间时的发现提示文字。"""
    return _DISCOVERY_MESSAGES.get(room_type, "")
