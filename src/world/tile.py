"""
──────────────────────────────────────────
瓷砖定义 —— 地图最小单元的类型与属性
──────────────────────────────────────────

职责：
  - 定义地形类型枚举（地板/墙/楼梯）。
  - 封装通行走和透光属性。
  - 为后续 BSP 随机生成提供基础。
"""

from enum import Enum, auto


class TileType(Enum):
    """地形类型枚举 —— 地图最小单元的分类。"""
    FLOOR = auto()           # 地板（可行走）
    WALL = auto()            # 墙壁（不可行走、不可透光）
    STAIRS_DOWN = auto()     # 下行楼梯（可行走，通往下一层）


class Tile:
    """单块瓷砖 —— 持有类型和通行/透光标记。

    属性：
        kind: 地形类型（TileType 枚举值）。
        is_walkable: 是否允许实体经过。
        is_transparent: 是否透光（为视野系统预留）。
    """

    def __init__(self, kind: TileType):
        """创建瓷砖。

        参数：
            kind: 地形类型。
        """
        self.kind = kind
        # 根据类型自动设定属性 —— 方便后续扩展更多类型
        if kind == TileType.FLOOR:
            self.is_walkable = True
            self.is_transparent = True
        elif kind == TileType.STAIRS_DOWN:
            self.is_walkable = True
            self.is_transparent = True
        elif kind == TileType.WALL:
            self.is_walkable = False
            self.is_transparent = False
        else:
            self.is_walkable = False
            self.is_transparent = False

    def __repr__(self):
        """调试用字符串表示。"""
        return f"Tile({self.kind.name})"
