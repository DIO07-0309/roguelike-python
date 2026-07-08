"""
标题画面场景 —— 粒子背景 + 菜单选项。
"""

import math
import pygame
from config import (COLOR_BLACK, COLOR_WHITE, COLOR_GRAY,
                     BOSS_FLOORS, MAX_FLOORS)
from src.core.scene import Scene
from game import get_font
from src.ui_helpers import (draw_panel, draw_key_hint, draw_glow_text,
                             GOLD, DARK_RED)


class TitleScene(Scene):
    """标题画面 —— N新游戏 / C继续 / F选关 / T教程 / Esc退出。"""

    def enter(self):
        from src.bgm_engine import play_title_bgm
        play_title_bgm()
        self.engine._bgm_stopped_for_title = True

    def render(self):
        screen = self.engine.screen
        screen.fill(COLOR_BLACK)
        self.engine._bg_particles.draw(screen)
        sw, sh = screen.get_width(), screen.get_height()

        # 标题（脉冲效果）
        pulse = 1.0 + 0.02 * math.sin(self.engine._title_anim * 2)
        draw_glow_text(screen, "Roguelike 肉鸽游戏", sw // 2, 100,
                       font_size=int(52 * pulse), color=(255, 255, 220),
                       glow_color=(120, 80, 40), center=True)
        draw_glow_text(screen, "— 地牢深处 —", sw // 2, 150,
                       font_size=18, color=(180, 180, 180), center=True)

        # 菜单面板
        pw, ph = 340, 290
        pr = pygame.Rect(sw // 2 - pw // 2, 190, pw, ph)
        draw_panel(screen, pr, title="选 单")
        self._draw_menu(pr)

        # 底部信息
        cr = get_font(12).render(
            "重庆大学大数据与软件学院 · 程序设计实训", True, (80, 80, 80))
        screen.blit(cr, (sw // 2 - cr.get_width() // 2, sh - 50))
        dev = get_font(14).render("开发者：ruozhiDIO", True, (140, 140, 160))
        screen.blit(dev, (sw // 2 - dev.get_width() // 2, sh - 30))
        pygame.display.flip()

    def _draw_menu(self, pr: pygame.Rect):
        """绘制菜单选项列表。"""
        from saves.save_manager import save_exists, load_save
        screen = self.engine.screen
        saved = load_save() if save_exists() else None
        has_save = saved is not None
        save_txt = (f"● 存档已存在（已解锁第{saved['max_unlocked_floor']}层）"
                    if has_save else "○ 暂无存档")
        ss = get_font(14).render(save_txt, True, (160, 160, 160))
        screen.blit(ss, (pr.x + (pr.width - ss.get_width()) // 2, pr.y + 30))

        y0 = pr.y + 60
        items = [
            ("N", "新游戏", GOLD),
            ("C", "继续游戏", (100, 200, 100) if has_save else (80, 80, 80)),
            ("F", "选关", (100, 180, 255) if has_save else (80, 80, 80)),
            ("T", "新手教程", (200, 180, 120)),
            ("F11", "全屏切换", (160, 160, 200)),
            ("Esc", "退出", (200, 100, 100)),
        ]
        for i, (key, desc, color) in enumerate(items):
            draw_key_hint(screen, key, desc, pr.x + 60, y0 + i * 36, color)

    def on_keydown(self, key: int):
        if key == pygame.K_n:
            self._start_new_game()
        elif key == pygame.K_c:
            self._continue_game()
        elif key == pygame.K_f:
            self._enter_floor_select()
        elif key == pygame.K_t:
            self._enter_tutorial()
        elif key == pygame.K_ESCAPE:
            self.engine.is_running = False

    # ── 场景跳转 ──────────────────────────────────────────

    def _start_new_game(self):
        """新游戏 → 建玩家 → 切到 GameScene 第1层。"""
        from src.scenes.game_scene import GameScene
        eng = self.engine
        eng.init_new_game()
        eng._bgm_stopped_for_title = False
        game = GameScene(eng)
        game.enter_floor(1)
        eng.change_scene(game)

    def _continue_game(self):
        """继续游戏 → 从存档恢复到 GameScene。"""
        from saves.save_manager import save_exists, load_save
        from src.scenes.game_scene import GameScene
        from config import BOSS_FLOORS
        eng = self.engine
        if not save_exists():
            return
        saved = load_save()
        if not saved:
            return
        eng.init_from_save(saved)
        eng._bgm_stopped_for_title = False
        game = GameScene(eng)
        floor = saved["current_floor"]
        seed = saved.get("dungeon_seed", 0)
        spr = saved.get("special_triggered", [])
        spd = saved.get("special_discovered", [])
        # B8: 用存档 seed 重建地图
        game.enter_floor(floor, seed)
        # B8/B10: 恢复特殊房间触发/发现状态
        if eng.game_map and spr:
            rooms = eng.game_map.special_rooms
            n = min(len(rooms), len(spr))
            for i in range(n):
                rooms[i].triggered = spr[i]
        if eng.game_map and spd:
            rooms = eng.game_map.special_rooms
            n = min(len(rooms), len(spd))
            for i in range(n):
                rooms[i].discovered = spd[i]
        eng.change_scene(game)

    def _enter_floor_select(self):
        """切换到选关场景。"""
        from saves.save_manager import save_exists, load_save
        from src.scenes.floor_select_scene import FloorSelectScene
        if save_exists():
            saved = load_save()
            self.engine._max_unlocked_floor = saved.get("max_unlocked_floor", 1)
        self.engine.change_scene(FloorSelectScene(self.engine))

    def _enter_tutorial(self):
        """切换到教程场景。"""
        from src.scenes.tutorial_scene import TutorialScene
        self.engine.change_scene(TutorialScene(self.engine))
