"""
──────────────────────────────────────────
BSP 地牢生成器 —— 程序化生成房间 + 走廊
──────────────────────────────────────────

算法：Binary Space Partitioning（二分空间划分）

流程：
  1. 从地图全区域开始，交替水平/垂直切分，递归直到 ≤ 最小尺寸。
  2. 每个叶子节点放置一个随机尺寸的房间。
  3. 从叶子向上遍历 BSP 树，逐层用 L 形走廊连接兄弟区域。

参考：
  - http://www.roguebasin.com/index.php/Basic_BSP_Dungeon_generation

设计原则：
  - 生成器只输出 GameMap，不关心实体/玩家/怪物。
  - 通过 get_room_centers() 暴露房间位置，供调用方用于实体生成。
"""

import random
from src.world.game_map import GameMap
from src.world.special_room import SpecialRoom, special_room_from_index
from config import (MAP_WIDTH, MAP_HEIGHT, TILE_SIZE,
                     DUNGEON_MIN_PARTITION, DUNGEON_MIN_ROOM,
                     DUNGEON_ROOM_MARGIN, DUNGEON_CORRIDOR_MIN,
                     DUNGEON_CORRIDOR_MAX)


class BSPNode:
    """BSP 树节点 —— 一个矩形区域。

    属性：
        rect: 该节点覆盖的矩形范围（瓦片坐标）。
        left: 左/上子节点。
        right: 右/下子节点。
        room: 该节点中的房间矩形（仅叶子有值）。
    """

    def __init__(self, x: int, y: int, w: int, h: int):
        """创建 BSP 节点。

        参数：
            x, y: 矩形左上角坐标（瓦片）。
            w, h: 矩形宽高（瓦片数）。
        """
        self.x = x
        self.y = y
        self.w = w
        self.h = h
        self.left: BSPNode | None = None
        self.right: BSPNode | None = None
        self.room: tuple | None = None          # (rx, ry, rw, rh) 或 None

    def is_leaf(self) -> bool:
        """是否为叶子节点（无子节点）。"""
        return self.left is None and self.right is None

    def center(self) -> tuple[int, int]:
        """返回节点矩形中心点坐标。"""
        return self.x + self.w // 2, self.y + self.h // 2

    def room_center(self) -> tuple[int, int] | None:
        """返回该节点房间的中心点坐标，无房间则返回 None。"""
        if self.room is None:
            return None
        rx, ry, rw, rh = self.room
        return rx + rw // 2, ry + rh // 2


class DungeonGenerator:
    """BSP 地牢生成器 —— 输出可用的 GameMap。

    属性：
        width, height: 地图尺寸（瓦片数）。
        tile_size: 瓦片像素尺寸。
        min_partition: 分区递归停止的最小尺寸。
        min_room: 房间的最小尺寸（宽/高）。
        room_margin: 房间与叶子区域边界的间距（瓦片数）。
    """

    def __init__(self,
                 width: int = MAP_WIDTH,
                 height: int = MAP_HEIGHT,
                 tile_size: int = TILE_SIZE,
                 min_partition: int = DUNGEON_MIN_PARTITION,
                 min_room: int = DUNGEON_MIN_ROOM,
                 room_margin: int = DUNGEON_ROOM_MARGIN):
        """初始化生成器。

        参数：
            width, height: 地图尺寸。
            tile_size: 瓦片像素尺寸。
            min_partition: 最小分区尺寸。
            min_room: 最小房间尺寸。
            room_margin: 房间边距。
        """
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.min_partition = min_partition
        self.min_room = min_room
        self.room_margin = room_margin
        self._root: BSPNode | None = None
        self._rooms: list[tuple[int, int, int, int]] = []
        self._special_rooms: list[SpecialRoom] = []   # B8: 特殊房间列表
        self._rng: random.Random | None = None        # B8: seed 驱动本地随机

    # =========================================================
    #  公共接口
    # =========================================================

    def generate(self, seed: int = 0, biome_id: str = "") -> GameMap:
        """执行完整生成流程 → 返回可用的 GameMap。

        seed=0: 使用全局 random（随机体验）。
        seed!=0: 使用本地 Random(seed)，同 seed 同地图（B8）。
        biome_id: G6.2 — 用于为该 Biome 注入地标房间。

        返回：
            生成好的 GameMap 实例（墙壁 + 地板 + L形走廊）。
        """
        self._rooms = []
        self._corridors: list[tuple[int, int, int, int]] = []
        self._special_rooms = []
        if seed != 0:
            self._rng = random.Random(seed)
        else:
            self._rng = None

        # 1. 构建 BSP 树
        self._root = BSPNode(0, 0, self.width, self.height)
        self._partition(self._root)
        # 2. 在每个叶子节点放房间
        self._create_rooms(self._root)
        # 3. 连接所有兄弟房间
        self._connect_rooms(self._root)
        # 4. 转化为瓦片网格
        game_map = GameMap(self.width, self.height, self.tile_size)
        template = self._build_template()
        game_map.load_from_template(template)
        # 5. B8: 分配特殊房间 (G6.2: biome landmarks mixed in)
        self._assign_special_rooms(biome_id)
        game_map.special_rooms = self._special_rooms
        return game_map

    def get_room_centers(self) -> list[tuple[int, int]]:
        """返回所有房间的瓦片中心点坐标。

        第一个房间可作为玩家出生点，
        其余房间可用于怪物生成。

        返回：
            [(tile_x, tile_y), ...] 列表。
        """
        centers = []
        for room in self._rooms:
            rx, ry, rw, rh = room
            centers.append((rx + rw // 2, ry + rh // 2))
        return centers

    def get_special_rooms(self) -> list[SpecialRoom]:
        """返回特殊房间列表 (B8)。"""
        return self._special_rooms

    # =========================================================
    #  Seed 驱动随机 (B8)
    # =========================================================

    def _randint(self, a: int, b: int) -> int:
        """seed≠0 时走本地 rng，否则走全局 random。"""
        if self._rng is not None:
            return self._rng.randint(a, b)
        return random.randint(a, b)

    def _randchoice(self, seq):
        """seed≠0 时走本地 rng，否则走全局 random。"""
        if self._rng is not None:
            return self._rng.choice(seq)
        return random.choice(seq)

    def _randrandom(self) -> float:
        """seed≠0 时走本地 rng，否则走全局 random.random。"""
        if self._rng is not None:
            return self._rng.random()
        return random.random()

    # =========================================================
    #  特殊房间分配 (B8)
    # =========================================================

    def _assign_special_rooms(self, biome_id: str = ""):
        """从 _rooms 中挑选 2~3 个为特殊房间，排除玩家房和楼梯房。

        G6.2: ~50% chance per slot → biome landmark, else normal special room.
        """
        from src.world.special_room import SpecialRoomType
        if len(self._rooms) < 4:
            return

        # Load landmarks for this biome (lazy import)
        landmarks = []
        if biome_id:
            try:
                from src.game.landmark import get_landmarks_for_biome
                landmarks = get_landmarks_for_biome(biome_id)
            except Exception:
                pass

        # Exclude rooms[0] (player) and rooms[-1] (stairs)
        candidates = list(range(1, len(self._rooms) - 1))
        # Fisher-Yates shuffle
        for i in range(len(candidates) - 1, 0, -1):
            j = self._randint(0, i)
            candidates[i], candidates[j] = candidates[j], candidates[i]

        normal_idx = 0
        placed_landmarks: set[str] = set()
        count = min(3, len(candidates))
        for i in range(count):
            rx, ry, rw, rh = self._rooms[candidates[i]]
            # G6.2: ~50% biome landmark (if available)
            if landmarks and self._randint(0, 1) == 0:
                # Weighted pick, excluding already-placed landmarks
                avail = [lm for lm in landmarks if lm.id not in placed_landmarks]
                if avail:
                    weights = [lm.weight for lm in avail]
                    pick = random.choices(avail, weights=weights)[0]
                    placed_landmarks.add(pick.id)
                    sr = SpecialRoom(
                        cx=rx + rw // 2, cy=ry + rh // 2,
                        rx=rx, ry=ry, rw=rw, rh=rh,
                        room_type=SpecialRoomType.LANDMARK,
                        landmark_id=pick.id, biome_id=biome_id,
                    )
                    self._special_rooms.append(sr)
                    continue
            # Fallback: normal special room (round-robin)
            sr = SpecialRoom(
                cx=rx + rw // 2,
                cy=ry + rh // 2,
                rx=rx, ry=ry, rw=rw, rh=rh,
                room_type=special_room_from_index(normal_idx),
            )
            normal_idx += 1
            self._special_rooms.append(sr)

    # =========================================================
    #  核心算法
    # =========================================================

    def _partition(self, node: BSPNode):
        """递归 BSP 切分 —— 交替水平/垂直切一刀。

        参数：
            node: 当前需要切分的 BSP 节点。
        """
        # 决定切分方向
        if node.w > node.h:
            split_axis_is_vertical = True
        elif node.h > node.w:
            split_axis_is_vertical = False
        else:
            split_axis_is_vertical = self._randchoice([True, False])

        # 计算可用切分范围，空间不足则停止
        region_size = node.w if split_axis_is_vertical else node.h
        if region_size < self.min_partition * 2:
            return

        split_min = self.min_partition
        split_max = region_size - self.min_partition
        split_pos = self._randint(split_min, split_max)

        self._create_child_nodes(node, split_axis_is_vertical, split_pos)
        self._partition(node.left)
        self._partition(node.right)

    def _create_child_nodes(self, node: BSPNode,
                            vertical: bool, split_pos: int):
        """根据切分方向和位置创建左右子节点。

        参数：
            node: 父节点。
            vertical: True 为垂直切，False 为水平切。
            split_pos: 切分线在 x 或 y 上的偏移。
        """
        if vertical:
            node.left = BSPNode(node.x, node.y, split_pos, node.h)
            node.right = BSPNode(node.x + split_pos, node.y,
                                 node.w - split_pos, node.h)
        else:
            node.left = BSPNode(node.x, node.y, node.w, split_pos)
            node.right = BSPNode(node.x, node.y + split_pos,
                                 node.w, node.h - split_pos)

    def _create_rooms(self, node: BSPNode):
        """递归在 BSP 叶子节点中放置随机尺寸的房间。

        参数：
            node: BSP 树节点。
        """
        # 非叶子递归进去
        if not node.is_leaf():
            if node.left:
                self._create_rooms(node.left)
            if node.right:
                self._create_rooms(node.right)
            return
        # 叶子节点：在区域内随机一个房间
        room_w = self._randint(self.min_room, max(self.min_room + 1, node.w - 2 * self.room_margin))
        room_h = self._randint(self.min_room, max(self.min_room + 1, node.h - 2 * self.room_margin))
        room_x = node.x + self._randint(self.room_margin, max(self.room_margin, node.w - room_w - self.room_margin))
        room_y = node.y + self._randint(self.room_margin, max(self.room_margin, node.h - room_h - self.room_margin))
        node.room = (room_x, room_y, room_w, room_h)
        self._rooms.append(node.room)

    def _connect_rooms(self, node: BSPNode):
        """递归连接 BSP 树中兄弟子区域的房间。

        只有当左右子树分别有房间时，才取各自的其中一个房间中心，
        用 L 形走廊连接。保证整个地图连通。

        参数：
            node: BSP 树节点。
        """
        if node.is_leaf():
            return
        # 先递归连接子树内部
        if node.left:
            self._connect_rooms(node.left)
        if node.right:
            self._connect_rooms(node.right)
        # 取左右子区域各一个房间
        if node.left is None or node.right is None:
            return
        room_a = self._pick_room(node.left)
        room_b = self._pick_room(node.right)
        if room_a and room_b:
            cx1, cy1 = room_a
            cx2, cy2 = room_b
            self._corridors.append((cx1, cy1, cx2, cy2))

    def _pick_room(self, node: BSPNode) -> tuple[int, int] | None:
        """从节点子树中随机选取一个房间的中心点。

        参数：
            node: BSP 树节点。

        返回：
            房间中心点 (cx, cy) 或 None。
        """
        if node.is_leaf():
            return node.room_center()
        # 随机从左右子树选一个
        children = [n for n in (node.left, node.right) if n is not None]
        if not children:
            return None
        return self._pick_room(self._randchoice(children))

    # =========================================================
    #  走廊绘制
    # =========================================================

    def _build_template(self) -> list[str]:
        """将房间和走廊写入 text template，返回给 GameMap。

        返回：
            字符串列表，'#'=墙，'.'=地板。
        """
        # 初始化为全墙
        grid = [['#' for _ in range(self.width)] for _ in range(self.height)]
        # 绘制所有房间地板
        for rx, ry, rw, rh in self._rooms:
            self._carve_rect(grid, rx, ry, rw, rh)
        # 绘制所有走廊
        for cx1, cy1, cx2, cy2 in self._corridors:
            self._carve_corridor(grid, cx1, cy1, cx2, cy2)
        # 转字符串
        return [''.join(row) for row in grid]

    def _carve_rect(self, grid: list[list[str]],
                    x: int, y: int, w: int, h: int):
        """在网格中挖出矩形地板。

        参数：
            grid: 字符网格。
            x, y: 矩形左上角。
            w, h: 矩形宽高。
        """
        for row in range(y, min(y + h, self.height)):
            for col in range(x, min(x + w, self.width)):
                grid[row][col] = '.'

    def _carve_corridor(self, grid: list[list[str]],
                        x1: int, y1: int, x2: int, y2: int):
        """挖一条 L 形走廊（先水平再垂直）。

        走廊宽度随机（DUNGEON_CORRIDOR_MIN ~ MAX），用菱形笔触实现。
        50% 概率交换路径顺序（先垂直再水平），增加变化。

        参数：
            grid: 字符网格。
            x1, y1: 起点坐标。
            x2, y2: 终点坐标。
        """
        width = self._randint(DUNGEON_CORRIDOR_MIN, DUNGEON_CORRIDOR_MAX)
        if self._randrandom() < 0.5:
            self._carve_line(grid, x1, y1, x2, y1, width)       # 水平段
            self._carve_line(grid, x2, y1, x2, y2, width)       # 垂直段
        else:
            self._carve_line(grid, x1, y1, x1, y2, width)       # 垂直段
            self._carve_line(grid, x1, y2, x2, y2, width)       # 水平段

    def _carve_line(self, grid: list[list[str]],
                    x1: int, y1: int, x2: int, y2: int,
                    width: int):
        """挖一条直线（水平或垂直），带宽度。

        使用菱形区域挖法：对直线上的每个点，挖出以它为圆心、
        半径为 width 的菱形区域。

        参数：
            grid: 字符网格。
            x1, y1: 起点。
            x2, y2: 终点。
            width: 走廊半宽。
        """
        if x1 == x2:
            # 垂直线
            step = 1 if y2 >= y1 else -1
            for y in range(y1, y2 + step, step):
                self._carve_diamond(grid, x1, y, width)
        else:
            # 水平线
            step = 1 if x2 >= x1 else -1
            for x in range(x1, x2 + step, step):
                self._carve_diamond(grid, x, y1, width)

    def _carve_diamond(self, grid: list[list[str]],
                       cx: int, cy: int, radius: int):
        """挖一个菱形区域（曼哈顿距离 ≤ radius 的瓦片）。

        参数：
            grid: 字符网格。
            cx, cy: 菱形中心。
            radius: 曼哈顿距离半径。
        """
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if abs(dx) + abs(dy) > radius:
                    continue
                tx = cx + dx
                ty = cy + dy
                if 0 <= tx < self.width and 0 <= ty < self.height:
                    grid[ty][tx] = '.'
