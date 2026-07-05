"""
──────────────────────────────────────────
UI 美化工具函数 —— 面板/边框/渐变/粒子
──────────────────────────────────────────

职责：
  - 提供统一风格的面板绘制（暗色边框 + 装饰线）。
  - 支持文字阴影、标题栏、进度条美化。
  - 粒子系统（标题画面背景动画）。

设计原则：
  - 全部纯函数，不持有状态，由 engine 直接调用。
  - 不引入外部资源，全部用 pygame 绘图 API。
"""

import math
import time
import random
import pygame


# =========================================================
#  颜色主题
# =========================================================

PANEL_BG = (18, 18, 30)                # 面板暗底色
PANEL_BORDER = (70, 70, 120)           # 面板边框
PANEL_ACCENT = (120, 80, 220)          # 面板装饰线色
TITLE_BAR = (40, 30, 80)               # 标题栏底色
GOLD = (220, 180, 60)                  # 金色高亮
DARK_RED = (160, 20, 20)               # 深红色
CYBER_BLUE = (0, 180, 200)             # 科技蓝


def draw_panel(screen, rect: pygame.Rect, title: str = "",
               font_size: int = 20, alpha: int = 220):
    """绘制统一风格面板 —— 暗底色 + 装饰边框 + 标题栏。

    参数：
        screen: 渲染目标。
        rect: 面板矩形。
        title: 可选标题文本。
        font_size: 标题大小。
        alpha: 背景不透明度。
    """
    # 背景
    panel = pygame.Surface((rect.width, rect.height))
    panel.set_alpha(alpha)
    panel.fill(PANEL_BG)
    screen.blit(panel, (rect.x, rect.y))
    # 外边框（双线效果）
    pygame.draw.rect(screen, PANEL_BORDER, rect, 2)
    pygame.draw.rect(screen, (30, 30, 50), rect.inflate(-6, -6), 1)
    # 标题栏
    if title:
        _draw_title_bar(screen, rect.x, rect.y - 8, rect.width, 28, title, font_size)
    # 底部装饰线
    line_y = rect.bottom - 4
    pygame.draw.line(screen, PANEL_ACCENT,
                     (rect.x + 10, line_y),
                     (rect.right - 10, line_y), 2)


def _draw_title_bar(screen, x: int, y: int, w: int, h: int,
                    text: str, font_size: int):
    """绘制凸起标题栏。

    参数：
        screen: 渲染目标。
        x, y: 左上角。
        w, h: 标题栏宽高。
        text: 标题文本。
        font_size: 文本大小。
    """
    bar = pygame.Rect(x, y, w, h)
    pygame.draw.rect(screen, TITLE_BAR, bar)
    pygame.draw.rect(screen, PANEL_ACCENT, bar, 1)
    # 文字阴影
    font = _get_cjk(font_size)
    _draw_text_shadow(screen, text, font, (240, 240, 255),
                      (x + w // 2, y + h // 2), center=True)


def draw_glow_text(screen, text: str, x: int, y: int,
                   font_size: int = 28, color: tuple = (255, 255, 255),
                   glow_color: tuple = None, center: bool = False):
    """绘制带光晕的文字。

    参数：
        screen: 渲染目标。
        text: 文本。
        x, y: 坐标。
        font_size: 字号。
        color: 主文字颜色。
        glow_color: 光晕颜色（默认自动生成）。
        center: 是否居中。
    """
    if glow_color is None:
        glow_color = tuple(max(0, min(255, c // 4)) for c in color)
    font = _get_cjk(font_size)
    # 光晕层（偏移绘制多次）
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2)]:
        glow = font.render(text, True, glow_color)
        if center:
            gx = x - glow.get_width() // 2 + dx
            gy = y - glow.get_height() // 2 + dy
        else:
            gx, gy = x + dx, y + dy
        screen.blit(glow, (gx, gy))
    # 主文字
    main = font.render(text, True, color)
    if center:
        mx = x - main.get_width() // 2
        my = y - main.get_height() // 2
    else:
        mx, my = x, y
    screen.blit(main, (mx, my))


def draw_progress_bar(screen, x: int, y: int, w: int, h: int,
                      ratio: float, color: tuple,
                      bg_color: tuple = (30, 30, 50)):
    """绘制带内发光的美化进度条。

    参数：
        screen: 渲染目标。
        x, y: 左上角。
        w, h: 宽高。
        ratio: 进度比例 (0.0~1.0)。
        color: 填充色。
        bg_color: 背景色。
    """
    # 背景
    pygame.draw.rect(screen, bg_color, (x, y, w, h))
    # 填充
    fill_w = max(0, int(w * ratio))
    if fill_w > 0:
        pygame.draw.rect(screen, color, (x, y, fill_w, h))
        # 高光效果
        highlight = tuple(min(255, c + 60) for c in color)
        highlight_h = max(1, h // 3)
        pygame.draw.rect(screen, highlight,
                         (x, y, fill_w, highlight_h))
    # 边框
    pygame.draw.rect(screen, (100, 100, 100), (x, y, w, h), 1)


def _draw_text_shadow(screen, text: str, font, color, pos,
                      center=False):
    """绘制带黑色阴影的文字。"""
    # 阴影
    shadow = font.render(text, True, (20, 20, 20))
    if center:
        sx = pos[0] - shadow.get_width() // 2 + 2
        sy = pos[1] - shadow.get_height() // 2 + 2
    else:
        sx, sy = pos[0] + 2, pos[1] + 2
    screen.blit(shadow, (sx, sy))
    # 主文字
    main = font.render(text, True, color)
    if center:
        mx = pos[0] - main.get_width() // 2
        my = pos[1] - main.get_height() // 2
    else:
        mx, my = pos
    screen.blit(main, (mx, my))


def draw_key_hint(screen, key: str, desc: str, x: int, y: int,
                  color: tuple = None):
    """绘制按键提示：[N] 新游戏 样式。

    参数：
        screen: 渲染目标。
        key: 按键名。
        desc: 描述文本。
        x, y: 左上角。
        color: 高亮色。
    """
    if color is None:
        color = GOLD
    font = _get_cjk(18)
    key_text = f" {key} "
    # 按键背景
    key_surf = font.render(key_text, True, (0, 0, 0))
    key_bg = pygame.Rect(x, y + 2, key_surf.get_width() + 4, key_surf.get_height() - 2)
    pygame.draw.rect(screen, color, key_bg, border_radius=4)
    screen.blit(key_surf, (x + 2, y + 1))
    # 描述文字
    desc_surf = font.render(desc, True, (220, 220, 220))
    screen.blit(desc_surf, (x + key_surf.get_width() + 10, y))


# =========================================================
#  粒子系统（标题背景）
# =========================================================

class Particle:
    """单个背景粒子。"""
    __slots__ = ('x', 'y', 'vx', 'vy', 'size', 'alpha', 'life', 'max_life')

    def __init__(self, x, y, vx, vy, size, life):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.size = size
        self.alpha = random.randint(60, 180)
        self.life = life
        self.max_life = life

    def update(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= dt
        self.alpha = int(60 + 120 * (self.life / self.max_life))

    def is_alive(self) -> bool:
        return self.life > 0

    def draw(self, screen):
        s = int(self.size * (self.life / self.max_life))
        if s < 1:
            return
        surface = pygame.Surface((s * 2, s * 2), pygame.SRCALPHA)
        a = min(255, self.alpha)
        pygame.draw.circle(surface, (160, 140, 220, a), (s, s), s)
        screen.blit(surface, (int(self.x) - s, int(self.y) - s))


class ParticleSystem:
    """背景粒子系统 —— 标题画面和 Boss 介绍用。"""

    def __init__(self, screen_w: int, screen_h: int, count: int = 35):
        self.w = screen_w
        self.h = screen_h
        self.particles: list[Particle] = []
        self._target = count

    def update(self, dt: float):
        # 补充粒子
        while len(self.particles) < self._target:
            x = random.randint(0, self.w)
            y = random.randint(0, self.h)
            vx = random.uniform(-25, 25)
            vy = random.uniform(-35, -10)
            size = random.uniform(1.5, 3.5)
            life = random.uniform(3, 8)
            self.particles.append(Particle(x, y, vx, vy, size, life))
        # 更新现有
        for p in self.particles:
            p.update(dt)
        self.particles = [p for p in self.particles if p.is_alive()]

    def draw(self, screen):
        for p in self.particles:
            p.draw(screen)


# =========================================================
#  全局字体缓存
# =========================================================

_cjk_cache = {}


def _get_cjk(size: int) -> pygame.font.Font:
    if size not in _cjk_cache:
        from config import CJK_FONT_PATH
        if CJK_FONT_PATH:
            _cjk_cache[size] = pygame.font.Font(CJK_FONT_PATH, size)
        else:
            _cjk_cache[size] = pygame.font.Font(None, size)
    return _cjk_cache[size]
