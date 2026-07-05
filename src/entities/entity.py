"""
──────────────────────────────────────────
实体基类 —— 所有游戏对象的公共基底
──────────────────────────────────────────

职责：
  - 持有位置、尺寸、碰撞矩形。
  - 提供渲染接口（子类覆写）。

设计原则：
  - 只放"所有实体都有的东西"，不放具体行为。
  - 战斗属性、AI、背包等由组件负责，不堆在基类里。
"""

import pygame


class Entity:
    """游戏实体基类 —— 位置 + 渲染抽象。

    属性：
        position: pygame.Vector2，实体在屏幕上的像素坐标。
        size: (width, height) 元组。
        rect: pygame.Rect，用于渲染定位和碰撞检测。
    """

    def __init__(self, x: float, y: float, width: int, height: int):
        """创建实体。

        参数：
            x, y: 初始像素坐标。
            width, height: 实体尺寸（像素）。
        """
        self.position = pygame.Vector2(x, y)
        self.size = (width, height)
        self.rect = pygame.Rect(x, y, width, height)

    def update(self, delta_time: float):
        """更新实体逻辑（子类覆写）。

        参数：
            delta_time: 上一帧耗时（秒）。
        """
        pass

    def render(self, screen: pygame.Surface):
        """绘制实体（子类覆写）。

        参数：
            screen: pygame 窗口 Surface。
        """
        pass

    def sync_rect(self):
        """同步碰撞矩形到当前 position —— 每次移动后调用。"""
        self.rect.x = int(self.position.x)
        self.rect.y = int(self.position.y)
