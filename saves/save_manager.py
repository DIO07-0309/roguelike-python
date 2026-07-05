"""
──────────────────────────────────────────
存档管理 —— JSON 序列化游戏状态
──────────────────────────────────────────

职责：
  - 保存/读取玩家进度到 saves/save.json。
  - 序列化 Player（等级/属性/技能/背包/装备）。
  - 清理存档。

设计原则：
  - 只存必要数据，地图和怪物不存（每次重新生成）。
  - 存档不绑定 Python 对象，全部用基础类型。
"""

import json
import os
import sys
from config import (MAX_FLOORS, PLAYER_MAX_HP, PLAYER_ATTACK,
                     PLAYER_PHYSICAL_DEFENSE, PLAYER_MAGICAL_DEFENSE)


def _get_save_dir() -> str:
    """获取存档目录（兼容开发环境和 PyInstaller 打包后的 exe）。

    PyInstaller 打包后，__file__ 指向 _internal 临时目录，
    存档应该放在 exe 同级的 saves/ 目录下以确保持久化。
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后：exe 所在目录下的 saves/
        base = os.path.dirname(sys.executable)
    else:
        # 开发环境：saves/ 目录（当前模块的父目录）
        base = os.path.dirname(os.path.dirname(__file__))
    return os.path.join(base, "saves")


SAVE_DIR = _get_save_dir()
SAVE_PATH = os.path.join(SAVE_DIR, "save.json")


# =========================================================
#  序列化 / 反序列化
# =========================================================

def _serialize_player(player) -> dict:
    """将 Player 对象转为纯数据字典。

    参数：
        player: Player 实例。

    返回：
        可 JSON 序列化的 dict。
    """
    c = player.combat
    inv = player.inventory
    # 主动技能（类名+等级）
    active_data = [(type(s).__name__, s.level) for s in player.skills.active_skills]
    passive_data = [(type(s).__name__, s.level) for s in player.skills.passives]
    # 背包物品
    items_list = []
    for item in inv.items:
        item_data = _serialize_item(item)
        if item_data:
            items_list.append(item_data)
    # 装备
    equipped_data = {}
    for slot, eq in inv.equipped.items():
        if eq:
            equipped_data[slot] = _serialize_item(eq)
    return {
        "level": player.level,
        "xp": player.xp,
        "xp_to_next": player.xp_to_next,
        "max_hp": c.max_hp,
        "current_hp": c.current_hp,
        "attack": c.attack,
        "physical_defense": c.physical_defense,
        "magical_defense": c.magical_defense,
        "active_skills": active_data,
        "passive_skills": passive_data,
        "inventory_items": items_list,
        "equipped": equipped_data,
    }


def _serialize_item(item) -> dict | None:
    """将 Item 转为纯数据 dict。

    参数：
        item: Item 实例。

    返回：
        dict 或 None。
    """
    from src.entities.item import EquipmentItem, ConsumableItem, CharmItem
    data = {
        "base_name": item.base_name,
        "rarity": item.rarity.name,
        "tile_char": item.tile_char,
    }
    if isinstance(item, CharmItem):
        data["type"] = "charm"
        data["slot"] = "charm"
        data["skill_class_name"] = item.skill_class_name
        data["cd_bonus"] = item.cd_bonus
        data["power_bonus"] = item.power_bonus
    elif isinstance(item, EquipmentItem):
        data["type"] = "equipment"
        data["slot"] = item.slot
        data["atk"] = item.stat_bonus.get("atk", 0)
        data["pdef"] = item.stat_bonus.get("pdef", 0)
        data["mdef"] = item.stat_bonus.get("mdef", 0)
        data["defense_type"] = item.defense_type
    elif isinstance(item, ConsumableItem):
        data["type"] = "consumable"
        data["effect_type"] = item.effect_type
        data["effect_value"] = item.effect_value
    return data


def _deserialize_player(data: dict):
    """从字典恢复 Player 对象。

    参数：
        data: 序列化后的玩家数据 dict。

    返回：
        恢复的 Player 实例。
    """
    from src.entities.player import Player
    from src.entities.components import CombatStats
    from src.entities.skill import (ALL_ACTIVE_SKILLS, ALL_PASSIVE_SKILLS)
    from src.entities.item import (Item, EquipmentItem, ConsumableItem, Rarity)
    from config import PLAYER_SPEED
    import config
    # 创建玩家基础
    p = Player(0, 0, PLAYER_SPEED,
               data["max_hp"], data["attack"],
               data["physical_defense"], data["magical_defense"])
    c = p.combat
    c.current_hp = data["current_hp"]
    p.level = data["level"]
    p.xp = data["xp"]
    p.xp_to_next = data["xp_to_next"]
    # 恢复技能（兼容旧格式 str 和新格式 tuple（name, level））
    cls_map = {c.__name__: c for c in ALL_ACTIVE_SKILLS + ALL_PASSIVE_SKILLS}
    for entry in data.get("active_skills", []):
        if isinstance(entry, (list, tuple)):
            name, lv = entry
        else:
            name, lv = entry, 1   # 旧格式兼容
        if name in cls_map:
            sk = cls_map[name]()
            sk.level = min(lv, sk.max_level)
            # 触发逐级升级回调还原属性
            for _ in range(1, lv):
                sk._on_level_up()
            p.skills.learn(sk)
    for entry in data.get("passive_skills", []):
        if isinstance(entry, (list, tuple)):
            name, lv = entry
        else:
            name, lv = entry, 1
        if name in cls_map:
            pk = cls_map[name]()
            pk.level = min(lv, pk.max_level)
            for _ in range(1, lv):
                pk._on_level_up()
            p.skills.learn(pk)
    p.skills.apply_all_passives(p)
    # 恢复背包
    p.inventory.items = []
    for d in data.get("inventory_items", []):
        item = _deserialize_item(d)
        if item:
            p.inventory.items.append(item)
    # 恢复装备
    for slot, d in data.get("equipped", {}).items():
        item = _deserialize_item(d)
        if isinstance(item, EquipmentItem):
            p.inventory.equipped[slot] = item
            item.apply(p)
    return p


def _deserialize_item(data: dict):
    """从字典恢复 Item。

    参数：
        data: 物品数据 dict。

    返回：
        Item 实例或 None。
    """
    from src.entities.item import (EquipmentItem, ConsumableItem, CharmItem, Rarity)
    rarity = Rarity[data["rarity"]]
    if data.get("type") == "charm":
        return CharmItem(
            data["base_name"], rarity,
            data["skill_class_name"],
            data["cd_bonus"], data["power_bonus"])
    elif data.get("type") == "equipment":
        return EquipmentItem(
            data["base_name"], rarity, data["slot"],
            atk_bonus=data.get("atk", 0),
            pdef_bonus=data.get("pdef", 0),
            mdef_bonus=data.get("mdef", 0),
            defense_type=data.get("defense_type", "physical"))
    elif data.get("type") == "consumable":
        return ConsumableItem(
            data["base_name"], rarity,
            data["effect_type"], int(data["effect_value"] / rarity.multiplier))
    return None


# =========================================================
#  公开接口
# =========================================================

def save_game(player, current_floor: int,
              max_unlocked_floor: int) -> bool:
    """保存游戏进度到 JSON。

    参数：
        player: 玩家实例。
        current_floor: 当前关卡号。
        max_unlocked_floor: 已解锁的最高关卡。

    返回：
        True 表示保存成功。
    """
    data = {
        "current_floor": current_floor,
        "max_unlocked_floor": max_unlocked_floor,
        "player": _serialize_player(player),
    }
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def load_save() -> dict | None:
    """读取存档文件。

    返回：
        (player, current_floor, max_unlocked_floor) 或 None。
    """
    if not os.path.exists(SAVE_PATH):
        return None
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        player = _deserialize_player(data["player"])
        return {
            "player": player,
            "current_floor": data["current_floor"],
            "max_unlocked_floor": data["max_unlocked_floor"],
        }
    except Exception:
        return None


def delete_save():
    """删除存档文件。"""
    if os.path.exists(SAVE_PATH):
        os.remove(SAVE_PATH)


def save_exists() -> bool:
    """检查是否有存档。"""
    return os.path.exists(SAVE_PATH)
