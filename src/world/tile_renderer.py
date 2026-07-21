"""
──────────────────────────────────────────
专业级地牢瓦片渲染器 — 3D墙、地板变异、光影
──────────────────────────────────────────

渲染特性：
  - 3D立体墙壁（顶面亮+侧面暗+砖缝+青苔）
  - 地板纹理（石板拼缝+区域色差+灰尘）
  - 墙壁投影（邻墙在地板上投射阴影）
  - 楼梯光柱脉冲效果
  - 区域自动检测（房间/走廊颜色不同）
"""

import math
import time
import pygame
from config import TILE_SIZE
from src.world.tile import Tile, TileType

TS = TILE_SIZE

# ── Default palette (Forgotten Prison) ──────────────────────
_DEFAULT_PALETTE = {
    "wall_top": (72, 68, 62), "wall_face": (42, 38, 34),
    "wall_brick": (50, 46, 42), "wall_moss": (55, 70, 40),
    "wall_highlight": (90, 85, 78),
    "floor_base": (115, 108, 95), "floor_joint": (95, 88, 75),
    "floor_dirt": (100, 93, 80), "floor_b": (105, 100, 88),
    "floor_c": (110, 102, 92), "grid_line": (50, 45, 38),
}

# G6.1: Active palette — mutated by Biome at floor entry
_active_palette = dict(_DEFAULT_PALETTE)


def set_tile_palette(palette: dict):
    """G6.1: Inject biome tile colors. Keys not present keep defaults."""
    global _active_palette
    for k, v in palette.items():
        if k in _DEFAULT_PALETTE:
            _active_palette[k] = tuple(v) if isinstance(v, list) else v


def _pal(k: str) -> tuple:
    """Resolve a palette key, falling back to default."""
    return _active_palette.get(k, _DEFAULT_PALETTE.get(k, (128, 128, 128)))


# ── Legacy color constants (kept for backward compat) ───────
WALL_TOP = _pal("wall_top")
WALL_FACE = _pal("wall_face")
WALL_BRICK = _pal("wall_brick")
WALL_MOSS = _pal("wall_moss")
WALL_HIGHLIGHT = _pal("wall_highlight")
FLOOR_BASE = _pal("floor_base")
FLOOR_JOINT = _pal("floor_joint")
FLOOR_DIRT = _pal("floor_dirt")
FLOOR_B = _pal("floor_b")
FLOOR_C = _pal("floor_c")
GRID_LINE = _pal("grid_line")

# Non-biome constants (unchanged across floors)
SHADOW = (0, 0, 0, 40)
STAIR_BASE = (130, 100, 30)
STAIR_HIGHLIGHT = (200, 170, 50)
STAIR_STEP = (90, 70, 20)

# ---- 缓存 ----
_floor_cache: dict[tuple, pygame.Surface] = {}
_wall_cache: dict[tuple, pygame.Surface] = {}


def _make_surface(fill_color, size: int) -> pygame.Surface:
    """创建并填充一个新 Surface。"""
    s = pygame.Surface((size, size))
    s.fill(fill_color)
    return s


# =========================================================
#  地板
# =========================================================

def draw_floor(screen: pygame.Surface, x: int, y: int,
               col: int, row: int, seed: int):
    """绘制带石板纹理的地板。

    参数：
        screen: 渲染目标。
        x, y: 像素坐标。
        col, row: 瓦片坐标。
        seed: 确定性随机种子（地图不变，纹理不变）。
    """
    fb, fb2, fc2, fj2 = _pal("floor_base"), _pal("floor_b"), _pal("floor_c"), _pal("floor_joint")
    zone = (col // 5 + row // 3) % 3
    if zone == 0:
        base = (fb[0] + (col * 3 + row * 7) % 8,
                fb[1] + (col * 5 + row * 3) % 6,
                fb[2] + (col * 7 + row * 5) % 6)
    elif zone == 1:
        base = (fb2[0] + (col * 7 + row * 3) % 8,
                fb2[1] + (col * 2 + row * 9) % 6,
                fb2[2] + (col * 4 + row * 6) % 6)
    else:
        base = (fc2[0] + (col * 4 + row * 7) % 8,
                fc2[1] + (col * 8 + row * 2) % 6,
                fc2[2] + (col * 6 + row * 4) % 6)
    rect = pygame.Rect(x, y, TS, TS)
    pygame.draw.rect(screen, base, rect)
    if col % 2 == 0:
        pygame.draw.line(screen, fj2, (x, y), (x, y + TS), 1)
    if row % 2 == 0:
        pygame.draw.line(screen, fj2, (x, y), (x + TS, y), 1)

    # 表面灰尘斑点
    for i in range(2):
        sx = (seed * (17 + i * 11) + col * 43 + row * 79) % (TS - 4)
        sy = (seed * (23 + i * 13) + col * 31 + row * 67) % (TS - 4)
        shade = base[0] + (seed + i) % 8 - 4
        pygame.draw.rect(screen, (shade, shade - 2, shade - 1),
                         (x + sx, y + sy, 2, 2))


# =========================================================
#  墙壁（3D）
# =========================================================

def draw_wall(screen: pygame.Surface, x: int, y: int,
              col: int, row: int, seed: int):
    """绘制立体墙壁 — 顶面+正面+砖纹+青苔。

    参数：
        screen: 渲染目标。
        x, y: 像素坐标。
        col, row: 瓦片坐标。
        seed: 随机种子。
    """
    top_h = 6          # 顶面高度
    rect = pygame.Rect(x, y, TS, TS)

    # 正面（暗）
    wt, wf, wb, wm, wh, gl = (_pal("wall_top"), _pal("wall_face"),
        _pal("wall_brick"), _pal("wall_moss"), _pal("wall_highlight"), _pal("grid_line"))
    face_rect = pygame.Rect(x, y + top_h, TS, TS - top_h)
    pygame.draw.rect(screen, wf, face_rect)
    # 砖缝横线
    for ly in range(y + top_h + 6, y + TS, 8):
        pygame.draw.line(screen, wb, (x, ly), (x + TS, ly), 1)
    # 竖砖缝
    offset = (col * 5 + row * 3) % 10
    for lx2 in range(x + offset, x + TS, 12):
        pygame.draw.line(screen, wb, (lx2, y + top_h), (lx2, y + TS), 1)
    # 青苔
    if (col * 7 + row * 13) % 5 == 0:
        pyg = (col * 3 + row * 11) % (TS - top_h)
        pgx = (col * 17 + row * 5) % (TS - 4)
        pygame.draw.rect(screen, wm, (x + pgx, y + top_h + pyg, 4, 3))

    # 顶面（亮）
    top_rect = pygame.Rect(x, y, TS, top_h)
    pygame.draw.rect(screen, wt, top_rect)
    # 顶面高光
    pygame.draw.rect(screen, wh, (x + 2, y + 1, TS - 4, 2))

    # 网格线
    pygame.draw.rect(screen, gl, rect, 1)


# =========================================================
#  楼梯
# =========================================================

def draw_stairs(screen: pygame.Surface, x: int, y: int):
    """绘制发光楼梯 — 台阶+光柱脉冲。

    参数：
        screen: 渲染目标。
        x, y: 像素坐标。
    """
    rect = pygame.Rect(x, y, TS, TS)
    # 基底
    pygame.draw.rect(screen, (100, 80, 30), rect)

    # 三级台阶
    for i in range(4):
        sy = y + TS - (i + 1) * 7
        step_w = TS - i * 5
        step_x = x + (TS - step_w) // 2
        shade = tuple(int(c * (0.6 + i * 0.12)) for c in STAIR_STEP)
        pygame.draw.rect(screen, shade, (step_x, sy, step_w, 5))

    # 光柱脉冲
    pulse = 0.6 + 0.4 * math.sin(time.time() * 5)
    glow_alpha = int(120 * pulse)
    glow = pygame.Surface((TS, TS), pygame.SRCALPHA)
    cx, cy = TS // 2, TS // 2
    for r in range(TS // 2, TS // 2 + 8):
        a = max(0, glow_alpha - (r - TS // 2) * 15)
        pygame.draw.circle(glow, (255, 220, 50, a), (cx, cy), r, 1)
    screen.blit(glow, (x, y))

    # 向下箭头
    pts = [(cx + x, cy + y + 8), (cx + x - 9, cy + y - 4), (cx + x + 9, cy + y - 4)]
    arrow_color = (255, 220, min(200, int(80 + 120 * pulse)))
    pygame.draw.polygon(screen, arrow_color, pts)

    pygame.draw.rect(screen, (120, 100, 40), rect, 1)


# =========================================================
#  阴影投射
# =========================================================

def _is_wall(game_map, col: int, row: int) -> bool:
    """检查指定坐标是否为墙。"""
    if col < 0 or col >= game_map.width or row < 0 or row >= game_map.height:
        return False
    return game_map._tiles[row][col].kind == TileType.WALL


def draw_shadow(screen: pygame.Surface, x: int, y: int,
                col: int, row: int, game_map):
    """墙投影到相邻地板 — 只渲染阴影条。

    参数：
        screen: 渲染目标。
        x, y: 像素坐标。
        col, row: 瓦片坐标。
        game_map: GameMap 实例。
    """
    # 上墙投影
    if _is_wall(game_map, col, row - 1):
        shadow = pygame.Surface((TS, 4), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 50))
        screen.blit(shadow, (x, y))
    # 左墙投影
    if _is_wall(game_map, col - 1, row):
        shadow = pygame.Surface((4, TS), pygame.SRCALPHA)
        shadow.fill((0, 0, 0, 50))
        screen.blit(shadow, (x, y))


# =========================================================
#  主入口
# =========================================================

def draw_tile(screen: pygame.Surface, tile: Tile,
              x: int, y: int, col: int, row: int,
              game_map):
    """绘制单个瓦片 — 分派到对应渲染函数。

    参数：
        screen: 渲染目标。
        tile: 瓦片对象。
        x, y: 屏幕上像素坐标。
        col, row: 瓦片坐标。
        game_map: GameMap 实例（用于阴影检测）。
    """
    seed = col * 1337 + row * 7331
    if tile.kind == TileType.WALL:
        draw_wall(screen, x, y, col, row, seed)
    elif tile.kind == TileType.STAIRS_DOWN:
        draw_floor(screen, x, y, col, row, seed)
        draw_stairs(screen, x, y)
        return
    elif tile.kind == TileType.FLOOR:
        # B8: 特殊房间地板着色
        sr = game_map.get_special_room_at(col, row)
        if sr:
            from src.world.special_room import SpecialRoomType
            # G6.2: biome landmarks — custom tile_color + icon from landmark def
            if sr.type == SpecialRoomType.LANDMARK and sr.landmark_id:
                clr, icon = _resolve_landmark_visual(sr.landmark_id)
                base = clr
            elif sr.type == SpecialRoomType.ALTAR:
                base = (50, 35, 15); icon = "+"
            elif sr.type == SpecialRoomType.TREASURE:
                base = (25, 35, 60); icon = "$"
            else:  # FOUNTAIN
                base = (20, 45, 25); icon = "~"
            # G6.2: landmarks don't dim — they're scenery, not consumables
            if sr.triggered and sr.type != SpecialRoomType.LANDMARK:
                base = tuple(int(c * 0.55) for c in base)
            rect = pygame.Rect(x, y, TS, TS)
            pygame.draw.rect(screen, base, rect)
            pygame.draw.rect(screen, (35, 35, 45), rect, 1)
            # 房间中心绘制图标
            if col == sr.cx and row == sr.cy:
                ic = (100, 100, 100) if (sr.triggered and sr.type != SpecialRoomType.LANDMARK) else (255, 255, 200)
                font = _get_icon_font()
                if font:
                    text = font.render(icon, True, ic)
                    screen.blit(text, (x + 10, y + 5))
        else:
            draw_floor(screen, x, y, col, row, seed)
            draw_shadow(screen, x, y, col, row, game_map)
    else:
        pygame.draw.rect(screen, (80, 40, 40), (x, y, TS, TS))
        pygame.draw.rect(screen, (60, 30, 30), (x, y, TS, TS), 1)
        return


_icon_font = None


def _resolve_landmark_visual(landmark_id: str) -> tuple:
    """G6.2: resolve tile_color + icon from landmarks.json."""
    default_clr = (60, 40, 40)
    default_icon = "?"
    try:
        from src.game.landmark import get_landmark_by_id
        lm = get_landmark_by_id(landmark_id)
        if lm:
            return lm.tile_color, lm.icon
    except Exception:
        pass
    return default_clr, default_icon


def _get_icon_font():
    """懒加载图标字体。"""
    global _icon_font
    if _icon_font is None:
        try:
            _icon_font = pygame.font.Font("C:/Windows/Fonts/simhei.ttf", 20)
        except Exception:
            try:
                _icon_font = pygame.font.Font(None, 20)
            except Exception:
                return None
    return _icon_font
