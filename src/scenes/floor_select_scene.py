"""
选关场景 —— 15 关网格面板。
"""

import pygame
from config import (COLOR_BLACK, COLOR_WHITE, COLOR_RED, COLOR_GRAY,
                     MAX_FLOORS, BOSS_FLOORS)
from src.core.scene import Scene
from game import get_font
from src.entities.boss import get_boss_info
from src.bgm_engine import play_select_bgm
from saves.save_manager import load_save


class FloorSelectScene(Scene):
    """选关 — 方向键导航 + Enter 进入 + Esc 返回。"""

    def __init__(self, engine):
        super().__init__(engine)
        self._cursor = 0

    def enter(self):
        play_select_bgm()
        self.engine._bgm_stopped_for_title = True

    def render(self):
        screen = self.engine.screen
        screen.fill(COLOR_BLACK)
        sw = screen.get_width()
        self._draw_text_center("选择关卡", size=32, color=COLOR_WHITE, offset_y=-250)
        self._draw_text_center("方向键选择  Enter 进入  Esc 返回",
                               size=16, color=COLOR_GRAY, offset_y=-210)
        cols, cell_w, cell_h, gap = 5, 100, 70, 10
        sx = sw // 2 - (cols * (cell_w + gap)) // 2
        sy = 120
        for i in range(MAX_FLOORS):
            cx = sx + (i % cols) * (cell_w + gap)
            cy = sy + (i // cols) * (cell_h + gap)
            self._draw_floor_cell(i, cx, cy, cell_w, cell_h)
        pygame.display.flip()

    def _draw_floor_cell(self, idx: int, cx: int, cy: int, w: int, h: int):
        """单个选关格子 — 解锁/锁定/选中/Boss标记。"""
        screen = self.engine.screen
        unlocked = (idx + 1) <= self.engine._max_unlocked_floor
        selected = (idx == self._cursor)
        rect = pygame.Rect(cx, cy, w, h)
        clr = (60, 60, 160) if selected else (40, 40, 80) if unlocked else (30, 30, 30)
        pygame.draw.rect(screen, clr, rect)
        border = ((200, 200, 50) if selected else
                  (100, 180, 100) if unlocked else (80, 80, 80))
        pygame.draw.rect(screen, border, rect, 2)
        is_boss = (idx + 1) in BOSS_FLOORS
        fnum = get_font(28).render(
            str(idx + 1), True, COLOR_RED if is_boss else COLOR_WHITE)
        screen.blit(fnum, (cx + w // 2 - fnum.get_width() // 2, cy + 8))
        if is_boss and unlocked:
            bi = get_boss_info(idx + 1)
            bn = get_font(12).render(bi["name"] if bi else "???", True, COLOR_RED)
            screen.blit(bn, (cx + w // 2 - bn.get_width() // 2, cy + h - 20))
        elif not unlocked:
            lk = get_font(14).render("锁", True, COLOR_GRAY)
            screen.blit(lk, (cx + w // 2 - lk.get_width() // 2, cy + h - 22))

    def on_keydown(self, key: int):
        if key == pygame.K_ESCAPE:
            from src.scenes.title_scene import TitleScene
            self.engine.change_scene(TitleScene(self.engine))
            return
        if key == pygame.K_LEFT:
            self._cursor = max(0, self._cursor - 1)
        elif key == pygame.K_RIGHT:
            self._cursor = min(MAX_FLOORS - 1, self._cursor + 1)
        elif key == pygame.K_UP:
            self._cursor = max(0, self._cursor - 5)
        elif key == pygame.K_DOWN:
            self._cursor = min(MAX_FLOORS - 1, self._cursor + 5)
        elif key == pygame.K_RETURN:
            self._enter_selected_floor()

    def _enter_selected_floor(self):
        """进入选中楼层 — 加载存档或新建玩家。"""
        from src.scenes.game_scene import GameScene
        from src.entities.skill import random_active_skill
        eng = self.engine
        floor = self._cursor + 1
        if floor > eng._max_unlocked_floor:
            return
        saved = load_save()
        if saved and saved["player"]:
            eng.player = saved["player"]
            eng.player.reset_attack_timers()
        else:
            eng.create_empty_player()
            starter = random_active_skill()
            eng.player.skills.learn(starter)
            eng.player.skills.apply_all_passives(eng.player)
        # 自动升级到对应楼层等级
        target = min(floor, 4)
        if eng.player.level < target:
            eng.player.auto_level_to(target)
        eng._bgm_stopped_for_title = False
        game = GameScene(eng)
        game.enter_floor(floor)
        eng.change_scene(game)

    def _draw_text_center(self, text: str, size: int, color: tuple, offset_y: int = 0):
        """窗口中央绘制文本。"""
        screen = self.engine.screen
        font = get_font(size)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(screen.get_width() // 2,
                                      screen.get_height() // 2 + offset_y))
        screen.blit(surf, rect)
