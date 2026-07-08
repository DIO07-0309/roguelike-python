"""
通关场景 —— 恭喜通关 + 统计数据展示。
"""

import pygame
from config import COLOR_BLACK
from src.core.scene import Scene
from game import get_font
from src.ui_helpers import draw_panel, draw_glow_text, GOLD
from src.bgm_engine import stop_bgm
from src.sfx_engine import play_sfx


class VictoryScene(Scene):
    """通关画面 — Enter 返回标题。"""

    def enter(self):
        eng = self.engine
        if not eng._bgm_stopped_for_title:
            stop_bgm()
            play_sfx("victory", 1.0)
            eng._bgm_stopped_for_title = True

    def render(self):
        screen = self.engine.screen
        screen.fill(COLOR_BLACK)
        self.engine._bg_particles.draw(screen)
        sw, sh = screen.get_width(), screen.get_height()
        draw_glow_text(screen, "恭喜通关！", sw // 2, 120,
                       font_size=60, color=(50, 255, 100),
                       glow_color=(0, 80, 0), center=True)
        player = self.engine.player
        lvl = player.level if player else 1
        txt = f"你击败了地牢最深处的黑暗，光明重归大地  最终等级 Lv{lvl}"
        t = get_font(18).render(txt, True, (200, 240, 200))
        screen.blit(t, (sw // 2 - t.get_width() // 2, 200))
        pw, ph = 400, 150
        pr = pygame.Rect(sw // 2 - pw // 2, 250, pw, ph)
        draw_panel(screen, pr, title="英雄凯旋")
        stats_text = [
            f"最终等级: Lv{lvl}",
            f"技能数: {len(player.skills.active_skills)}主动 "
            f"+ {len(player.skills.passives)}被动",
            f"装备武器: {player.inventory.equipped.get('weapon','无')}",
        ]
        for i, line in enumerate(stats_text):
            s = get_font(16).render(str(line), True, (200, 200, 200))
            screen.blit(s, (sw // 2 - s.get_width() // 2, pr.y + 35 + i * 28))
        draw_glow_text(screen, "按 Enter 返回标题", sw // 2, sh - 60,
                       font_size=22, color=GOLD, center=True)
        pygame.display.flip()

    def on_keydown(self, key: int):
        if key == pygame.K_RETURN:
            from src.scenes.title_scene import TitleScene
            eng = self.engine
            eng.player = None
            eng.monsters = []
            eng.game_map = None
            eng.change_scene(TitleScene(eng))
