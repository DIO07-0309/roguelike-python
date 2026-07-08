"""
死亡场景 —— 提示玩家死亡 + 存档保留提示。
"""

import pygame
from config import COLOR_BLACK, COLOR_WHITE
from src.core.scene import Scene
from game import get_font
from src.ui_helpers import draw_glow_text
from src.bgm_engine import stop_bgm


class DeathScene(Scene):
    """死亡画面 — Enter 返回标题，存档已保留。"""

    def enter(self):
        eng = self.engine
        if not eng._bgm_stopped_for_title:
            stop_bgm()
            eng._bgm_stopped_for_title = True

    def render(self):
        screen = self.engine.screen
        screen.fill(COLOR_BLACK)
        self.engine._bg_particles.draw(screen)
        sw, sh = screen.get_width(), screen.get_height()
        draw_glow_text(screen, "你 死 了", sw // 2, 130,
                       font_size=64, color=(220, 40, 40),
                       glow_color=(60, 0, 0), center=True)
        t = get_font(18).render(
            "存档已保留，可从选关界面继续挑战", True, (220, 180, 100))
        screen.blit(t, (sw // 2 - t.get_width() // 2, 210))
        draw_glow_text(screen, "按 Enter 返回标题", sw // 2, sh - 70,
                       font_size=22, color=(200, 200, 200), center=True)
        pygame.display.flip()

    def on_keydown(self, key: int):
        if key == pygame.K_RETURN:
            from src.scenes.title_scene import TitleScene
            eng = self.engine
            eng.player = None
            eng.monsters = []
            eng.game_map = None
            eng.change_scene(TitleScene(eng))
