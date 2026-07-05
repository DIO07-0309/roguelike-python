"""
──────────────────────────────────────────
游戏地图 —— 二维瓷砖网格的核心数据结构
──────────────────────────────────────────

职责：
  - 持有 Tile 的二维网格。
  - 提供像素坐标 ↔ 瓦片坐标转换。
  - 提供通行性查询（单点 + 矩形）。
  - 渲染可见瓦片（为摄像机/FOV 预留接口）。

设计原则：
  - 地图不关心实体，只负责"地形能不能走"。
  - 碰撞检测返回布尔值，由调用方决定如何响应。
  - 地图数据来源与绘制分离 —— 未来可接入 BSP 生成器。
"""

import pygame
from config import TILE_SIZE
from src.world.tile import Tile, TileType
from src.world.tile_renderer import draw_tile as draw_tile_enhanced


class GameMap:
    """地牢地图 —— 二维瓷砖网格。

    属性：
        width: 地图宽度（瓦片数）。
        height: 地图高度（瓦片数）。
        tile_size: 单个瓦片的像素边长。
        pixel_width: 地图总像素宽度 = width * tile_size。
        pixel_height: 地图总像素高度 = height * tile_size。
    """

    def __init__(self, width: int, height: int, tile_size: int = TILE_SIZE):
        """初始化空白地图（全部为墙）。

        参数：
            width: 地图列数。
            height: 地图行数。
            tile_size: 瓦片像素尺寸（默认取全局配置）。
        """
        self.width = width
        self.height = height
        self.tile_size = tile_size
        self.pixel_width = width * tile_size
        self.pixel_height = height * tile_size
        # 初始化为全墙 —— 后续通过 load_from_template 填充
        self._tiles: list[list[Tile]] = []
        self._init_blank()

    # =========================================================
    #  地图数据加载
    # =========================================================

    def load_from_template(self, template: list[str]):
        """从文本模板加载地图数据。

        模板是一个字符串列表，每行字符串长度等于地图宽度。
        '#' → 墙，'.' → 地板。

        参数：
            template: 字符串列表，每个字符代表一个瓦片。
        """
        row_count = min(len(template), self.height)
        for row_index in range(row_count):
            line = template[row_index]
            col_count = min(len(line), self.width)
            for col_index in range(col_count):
                char = line[col_index]
                if char == '#':
                    self._tiles[row_index][col_index] = Tile(TileType.WALL)
                elif char == '.':
                    self._tiles[row_index][col_index] = Tile(TileType.FLOOR)
                # 其他字符保留默认（墙）

    # =========================================================
    #  坐标转换
    # =========================================================

    def pixel_to_tile(self, pixel_x: float, pixel_y: float) -> tuple[int, int]:
        """像素坐标 → 瓦片坐标。

        参数：
            pixel_x, pixel_y: 像素坐标。

        返回：
            (tile_col, tile_row) 元组。
        """
        tile_x = int(pixel_x // self.tile_size)
        tile_y = int(pixel_y // self.tile_size)
        return tile_x, tile_y

    def tile_to_pixel(self, tile_x: int, tile_y: int) -> tuple[int, int]:
        """瓦片坐标 → 像素坐标（瓦片左上角）。

        参数：
            tile_x, tile_y: 瓦片坐标。

        返回：
            (pixel_x, pixel_y) 元组。
        """
        return tile_x * self.tile_size, tile_y * self.tile_size

    # =========================================================
    #  通行性查询
    # =========================================================

    def is_walkable(self, tile_x: int, tile_y: int) -> bool:
        """查询单个瓦片是否可行走。

        参数：
            tile_x, tile_y: 瓦片坐标。

        返回：
            True 表示可通行。
        """
        if not self._in_bounds(tile_x, tile_y):
            return False
        return self._tiles[tile_y][tile_x].is_walkable

    def is_rect_walkable(self, rect: pygame.Rect) -> bool:
        """检测一个矩形区域是否全部可行走。

        检查矩形的四个角点和四条边中点所在的瓦片，
        只要有一个落在墙上就返回 False。

        参数：
            rect: 待检测的矩形区域。

        返回：
            True 表示区域内无墙阻挡。
        """
        # 采样点：4 个角 + 4 条边中点
        check_points = [
            (rect.left, rect.top),
            (rect.right - 1, rect.top),
            (rect.left, rect.bottom - 1),
            (rect.right - 1, rect.bottom - 1),
            (rect.centerx, rect.top),
            (rect.centerx, rect.bottom - 1),
            (rect.left, rect.centery),
            (rect.right - 1, rect.centery),
        ]
        for px, py in check_points:
            tx, ty = self.pixel_to_tile(px, py)
            if not self.is_walkable(tx, ty):
                return False
        return True

    def get_blocking_tiles(self, rect: pygame.Rect) -> list[tuple[int, int]]:
        """返回矩形区域内所有不可通行的瓦片坐标 —— 用于调试/UI。

        参数：
            rect: 待检测的矩形区域。

        返回：
            不可通行的 (tile_x, tile_y) 列表。
        """
        blocking = []
        seen = set()
        check_points = [
            (rect.left, rect.top),
            (rect.right - 1, rect.top),
            (rect.left, rect.bottom - 1),
            (rect.right - 1, rect.bottom - 1),
            (rect.centerx, rect.center.y),
        ]
        for px, py in check_points:
            tx, ty = self.pixel_to_tile(px, py)
            if (tx, ty) not in seen:
                seen.add((tx, ty))
                if not self.is_walkable(tx, ty):
                    blocking.append((tx, ty))
        return blocking

    # =========================================================
    #  渲染
    # =========================================================

    def render(self, screen: pygame.Surface,
               camera_x: int = 0, camera_y: int = 0):
        """绘制地图 — 使用增强瓦片渲染器。"""
        srect = screen.get_rect()
        sc = max(0, camera_x // self.tile_size)
        sr = max(0, camera_y // self.tile_size)
        ec = min(self.width, (camera_x + srect.width) // self.tile_size + 1)
        er = min(self.height, (camera_y + srect.height) // self.tile_size + 1)
        for row in range(sr, er):
            for col in range(sc, ec):
                dx = col * self.tile_size - camera_x
                dy = row * self.tile_size - camera_y
                draw_tile_enhanced(screen, self._tiles[row][col],
                                   dx, dy, col, row, self)

    def set_tile(self, tile_x: int, tile_y: int, kind: TileType):
        """直接修改指定瓦片的类型。

        参数：
            tile_x, tile_y: 瓦片坐标。
            kind: 新地形类型。
        """
        if self._in_bounds(tile_x, tile_y):
            self._tiles[tile_y][tile_x] = Tile(kind)

    # =========================================================
    #  内部工具
    # =========================================================

    def _init_blank(self):
        """用全墙填充整个地图网格。"""
        self._tiles = [
            [Tile(TileType.WALL) for _ in range(self.width)]
            for _ in range(self.height)
        ]

    def _in_bounds(self, tile_x: int, tile_y: int) -> bool:
        """检查瓦片坐标是否在地图范围内。

        参数：
            tile_x, tile_y: 瓦片坐标。

        返回：
            True 表示坐标合法。
        """
        return 0 <= tile_x < self.width and 0 <= tile_y < self.height
