"""
──────────────────────────────────────────
背包系统 —— 物品存储 / 装备 / 使用
──────────────────────────────────────────

职责：
  - 持有物品列表和装备槽位。
  - 提供拾取/丢弃/装备/卸下/使用的完整接口。
  - 供 UI 层查询内容、引擎层调用逻辑。

设计原则：
  - Inventory 是纯数据容器 + 业务逻辑，不涉及渲染。
  - 装备槽位用固定 dict 管理，方便扩展新槽位（戒指、项链等）。
"""

from src.entities.item import Item, EquipmentItem, ConsumableItem, CharmItem


class Inventory:
    """玩家背包 —— 物品存储 + 装备管理。

    属性：
        items: 存放除装备外所有道具的列表。
        equipped: 装备槽位映射 {"weapon": Item|None, "armor": Item|None}。
        max_size: 背包容量上限。
    """

    def __init__(self, max_size: int = 16):
        """初始化背包。

        参数：
            max_size: 背包格子数上限。
        """
        self.items: list[Item] = []
        self.equipped: dict[str, EquipmentItem | None] = {
            "weapon": None,
            "armor": None,
            "charm": None,
        }
        self.max_size = max_size

    # =========================================================
    #  容量查询
    # =========================================================

    def is_full(self) -> bool:
        """背包是否已满。"""
        return len(self.items) >= self.max_size

    def item_count(self) -> int:
        """当前物品数量。"""
        return len(self.items)

    # =========================================================
    #  拾取 / 丢弃
    # =========================================================

    def add(self, item: Item, player) -> bool:
        """拾取物品到背包。

        参数：
            item: 待添加的物品。
            player: 玩家实例（自动装备时需要用）。

        返回：
            True 表示添加成功。
        """
        if self.is_full():
            return False
        self.items.append(item)
        return True

    def remove(self, index: int) -> Item | None:
        """丢弃指定索引的物品。

        参数：
            index: 物品在列表中的索引。

        返回：
            被移除的 Item，或 None（索引无效时）。
        """
        if 0 <= index < len(self.items):
            return self.items.pop(index)
        return None

    # =========================================================
    #  装备 / 卸下
    # =========================================================

    def equip(self, index: int, player) -> str | None:
        """装备背包中指定索引的物品。

        若该槽位已有装备，自动卸下旧装备并放回背包。
        消耗品不可装备。

        参数：
            index: 物品索引。
            player: 玩家实例（应用属性加成）。

        返回：
            操作描述文本，或 None（操作失败时）。
        """
        if index < 0 or index >= len(self.items):
            return None
        item = self.items[index]
        if not isinstance(item, EquipmentItem):
            return f"{item.name} 不可装备"
        # 卸下旧装备
        old = self.equipped.get(item.slot)
        if old is not None:
            old.remove(player)
            self.items.append(old)
        # 穿新装备
        self.equipped[item.slot] = item
        self.items.pop(index)
        item.apply(player)
        return f"装备了 {item.get_description()}"

    def unequip(self, slot: str, player) -> str | None:
        """卸下指定槽位的装备并放回背包。

        参数：
            slot: 槽位名（"weapon" / "armor"）。
            player: 玩家实例。

        返回：
            操作描述文本，或 None（槽位为空时）。
        """
        if slot not in self.equipped:
            return None
        item = self.equipped[slot]
        if item is None:
            return None
        if self.is_full():
            return "背包已满，无法卸下"
        item.remove(player)
        self.items.append(item)
        self.equipped[slot] = None
        return f"卸下了 {item.name}"

    # =========================================================
    #  使用
    # =========================================================

    def use(self, index: int, player) -> str | None:
        """使用指定索引的消耗品。

        参数：
            index: 物品索引。
            player: 玩家实例。

        返回：
            效果描述文本，或 None（不可用时）。
        """
        if index < 0 or index >= len(self.items):
            return None
        item = self.items[index]
        if not isinstance(item, ConsumableItem):
            return f"{item.name} 无法直接使用"
        result = item.use(player)
        self.items.pop(index)             # 使用后移除
        return result
