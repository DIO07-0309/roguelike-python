"""
教程场景 —— 6 阶段渐进引导。
"""

import pygame
from config import (COLOR_BLACK, COLOR_WHITE, COLOR_GRAY, TILE_SIZE,
                     PLAYER_SPEED, PLAYER_MAX_HP, PLAYER_ATTACK,
                     PLAYER_PHYSICAL_DEFENSE, PLAYER_MAGICAL_DEFENSE)
from src.core.scene import Scene
from game import get_font
from src.entities.player import Player
from src.entities.skill import get_learned_skill_names
from src.tutorial import (TutorialGuide, TutorialStage,
                           build_tutorial_map, create_tutorial_dummy,
                           create_tutorial_items, give_tutorial_skill)
from src.bgm_engine import stop_bgm


class TutorialScene(Scene):
    """6 阶段教程 — 逐步学习移动/攻击/拾取/背包/装备/技能。"""

    def __init__(self, engine):
        super().__init__(engine)
        self.tutorial: TutorialGuide | None = None
        self._gave_tutorial_skill = False

    def enter(self):
        eng = self.engine
        stop_bgm()
        eng._bgm_stopped_for_title = True
        eng._game_time = 0.0
        eng.ground_items = []
        eng.inventory_open = False
        eng.inventory_cursor = 0
        self._gave_tutorial_skill = False
        self.tutorial = TutorialGuide()
        eng.game_map = build_tutorial_map()
        spawn_px = 2 * TILE_SIZE
        spawn_py = 4 * TILE_SIZE
        eng.player = Player(spawn_px, spawn_py, PLAYER_SPEED,
                            PLAYER_MAX_HP, PLAYER_ATTACK,
                            PLAYER_PHYSICAL_DEFENSE, PLAYER_MAGICAL_DEFENSE)
        eng.monsters = [create_tutorial_dummy(8, 4)]
        eng.ground_items = create_tutorial_items(6, 5)

    def update(self, delta_time: float):
        eng = self.engine
        if not eng.player:
            return
        t = self.tutorial
        if t.stage == TutorialStage.WELCOME:
            return
        keys = pygame.key.get_pressed()
        if eng.inventory_open:
            eng.player.update(delta_time)
            self._check_advance()
            return
        move_x, move_y = eng.player.handle_input(keys)
        self._apply_movement(move_x, move_y, delta_time)
        eng.player.update(delta_time)
        if t.stage == TutorialStage.SKILL and not self._gave_tutorial_skill:
            give_tutorial_skill(eng.player)
            self._gave_tutorial_skill = True
        self._check_advance()

    def _apply_movement(self, move_x: float, move_y: float, dt: float):
        """分轴移动 + 地图碰撞。"""
        eng = self.engine
        entity = eng.player.entity
        speed = eng.player.speed
        entity.position.x += move_x * speed * dt
        entity.sync_rect()
        if not eng.game_map.is_rect_walkable(entity.rect):
            entity.position.x -= move_x * speed * dt
            entity.sync_rect()
        entity.position.y += move_y * speed * dt
        entity.sync_rect()
        if not eng.game_map.is_rect_walkable(entity.rect):
            entity.position.y -= move_y * speed * dt
            entity.sync_rect()

    def _check_advance(self):
        """委托教程引导检测阶段推进条件。"""
        self.tutorial.check_and_advance(self.engine.player, {
            "game_time": self.engine._game_time,
            "inventory_open": self.engine.inventory_open,
            "monsters": self.engine.monsters,
            "ground_items": self.engine.ground_items,
        })

    def render(self):
        """渲染教程画面 — 地图 + 实体 + HUD + 提示框。"""
        eng = self.engine
        screen = eng.screen
        screen.fill(COLOR_BLACK)
        cam_x, cam_y = self._get_camera_offset()
        if eng.game_map:
            eng.game_map.render(screen, cam_x, cam_y)
        for m in eng.monsters:
            m.render(screen, cam_x, cam_y)
        self._render_ground_items(cam_x, cam_y)
        if eng.player:
            eng.player.render(screen, cam_x, cam_y)
        self._render_hud()
        if self.tutorial and self.tutorial.stage != TutorialStage.WELCOME:
            self._draw_text_center(
                "WASD移动 | 空格攻击 | E拾取 | I背包 | T跳过教程",
                size=12, color=COLOR_GRAY,
                offset_y=screen.get_height() // 2 - 20)
        if eng.inventory_open:
            from src.scenes.game_scene import GameScene
            # borrow the GameScene's inventory renderer via a temp helper
            self._render_inventory()
        self._render_overlay()
        pygame.display.flip()

    def _render_inventory(self):
        """临时借用背包渲染。"""
        # Use the engine's inventory_open state to show a simple panel
        # Full rendering is in GameScene; here we do the equivalent
        from src.ui_helpers import draw_panel, GOLD
        eng = self.engine
        screen = eng.screen
        sw, sh = screen.get_width(), screen.get_height()
        dark = pygame.Surface((sw, sh)); dark.set_alpha(180); dark.fill((0, 0, 0))
        screen.blit(dark, (0, 0))
        inv = eng.player.inventory
        pw, ph = 440, 480
        pr = pygame.Rect(sw // 2 - pw // 2, sh // 2 - ph // 2, pw, ph)
        draw_panel(screen, pr, title="背 包  I关闭")
        x0, y0 = pr.x + 30, pr.y + 40
        f18 = get_font(18)
        eq_text = "◆ 装备: "
        for slot, eq in inv.equipped.items():
            eq_text += f"【{slot}】{eq.get_description()}  " if eq else f"【{slot}】空  "
        screen.blit(f18.render(eq_text, True, GOLD), (x0, y0))
        pygame.draw.line(screen, (60, 60, 90), (x0, y0 + 28), (pr.right - 30, y0 + 28), 1)
        for idx, item in enumerate(inv.items):
            ry = y0 + 38 + idx * 30
            mk = "▶" if idx == eng.inventory_cursor else " "
            screen.blit(f18.render(f"{mk} [{idx+1:>2}] {item.get_description()}", True, item.color), (x0, ry))
        if not inv.items:
            screen.blit(f18.render("背包空空如也", True, (120, 120, 120)), (x0, y0 + 38))
        tips = "↑↓选择  X装备  U使用  D丢弃  I关闭"
        tip = get_font(16).render(tips, True, (140, 140, 140))
        screen.blit(tip, (pr.x + (pw - tip.get_width()) // 2, pr.bottom - 30))

    def _render_overlay(self):
        """画面中央教程提示框。"""
        if not self.tutorial:
            return
        lines = self.tutorial.get_stage_instructions()
        if not lines:
            return
        screen = self.engine.screen
        font = get_font(22)
        max_w = max(font.size(ln)[0] for ln in lines) + 60
        line_h = 28
        total_h = len(lines) * line_h + 40
        box_x = (screen.get_width() - max_w) // 2
        box_y = 80
        overlay = pygame.Surface((max_w, total_h))
        overlay.set_alpha(200); overlay.fill((20, 20, 40))
        screen.blit(overlay, (box_x, box_y))
        pygame.draw.rect(screen, (100, 100, 180), (box_x, box_y, max_w, total_h), 2)
        for i, line in enumerate(lines):
            txt = font.render(line, True, COLOR_WHITE)
            tx = box_x + (max_w - txt.get_width()) // 2
            ty = box_y + 20 + i * line_h
            screen.blit(txt, (tx, ty))

    def on_keydown(self, key: int):
        if not self.tutorial:
            return
        t = self.tutorial
        if key == pygame.K_t:
            from src.scenes.title_scene import TitleScene
            self.engine.change_scene(TitleScene(self.engine))
            return
        if t.stage == TutorialStage.WELCOME:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                t.advance_stage()
            return
        if t.stage == TutorialStage.COMPLETE:
            if key == pygame.K_RETURN:
                from src.scenes.title_scene import TitleScene
                self.engine.change_scene(TitleScene(self.engine))
            return
        eng = self.engine
        if eng.inventory_open:
            self._handle_inventory_key(key)
            return
        self._handle_game_key(key)

    def _handle_inventory_key(self, key: int):
        """背包面板按键 — 简化版。"""
        eng = self.engine
        inv = eng.player.inventory
        if key in (pygame.K_i, pygame.K_ESCAPE):
            eng.inventory_open = False
        elif key == pygame.K_UP:
            eng.inventory_cursor = max(0, eng.inventory_cursor - 1)
        elif key == pygame.K_DOWN:
            eng.inventory_cursor = min(max(0, len(inv.items) - 1), eng.inventory_cursor + 1)
        elif key == pygame.K_x:
            inv.equip(eng.inventory_cursor, eng.player)
            eng.inventory_cursor = min(eng.inventory_cursor, max(0, len(inv.items) - 1))
        elif key == pygame.K_u:
            inv.use(eng.inventory_cursor, eng.player)
            eng.inventory_cursor = min(eng.inventory_cursor, max(0, len(inv.items) - 1))
        elif key == pygame.K_d:
            inv.remove(eng.inventory_cursor)
            eng.inventory_cursor = min(eng.inventory_cursor, max(0, len(inv.items) - 1))

    def _handle_game_key(self, key: int):
        """教程中游戏操作按键。"""
        from src.systems.combat_system import find_attack_target, calculate_damage
        from src.systems.buff_system import get_effective_attack
        from src.fx_engine import player_attack_fx, hit_flash_fx
        from src.sfx_engine import play_sfx
        eng = self.engine
        t = self.tutorial
        if key == pygame.K_SPACE:
            player = eng.player
            if not player or not player.combat.is_alive or not player.can_attack(eng._game_time):
                return
            cr = player.entity.rect
            eng._attack_effects += player_attack_fx(cr.centerx, cr.centery, 48)
            play_sfx("melee")
            target = find_attack_target(player.entity.rect, eng.monsters, 1.5)
            if target:
                dmg = calculate_damage(
                    get_effective_attack(player),
                    target.combat.get_effective_defense(player.attack_type),
                    player.attack_type)
                player._last_attack_time = eng._game_time
                target.combat.take_damage(dmg)
                play_sfx("hit")
                eng._attack_effects += hit_flash_fx(
                    int(target.entity.position.x), int(target.entity.position.y),
                    target.entity.size[0])
            self._check_advance()
        elif key == pygame.K_e:
            # simplified pickup
            if eng.ground_items:
                item = eng.ground_items[0]
                if eng.player.inventory.add(item.item, eng.player):
                    eng.ground_items.remove(item)
        elif key == pygame.K_i:
            eng.inventory_open = True
            eng.inventory_cursor = 0
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            idx = key - pygame.K_1
            if idx < len(eng.player.skills.active_skills):
                eng.player.skills.use_active(idx, eng.player, eng.monsters, eng.game_map, eng._game_time)
                if t.stage == TutorialStage.SKILL:
                    t.notify_skill_used()

    # ── 辅助 ──────────────────────────────────────────────

    def _get_camera_offset(self) -> tuple:
        eng = self.engine
        if not eng.player:
            return 0, 0
        sw, sh = eng.screen.get_width(), eng.screen.get_height()
        cx = eng.player.entity.rect.centerx - sw // 2
        cy = eng.player.entity.rect.centery - sh // 2
        if eng.game_map:
            cx = max(0, min(cx, eng.game_map.pixel_width - sw))
            cy = max(0, min(cy, eng.game_map.pixel_height - sh))
        return int(cx), int(cy)

    def _render_ground_items(self, cam_x: int, cam_y: int):
        """简化版掉落物渲染。"""
        import math, time
        screen = self.engine.screen
        for dropped in self.engine.ground_items:
            px = dropped.tile_x * TILE_SIZE - cam_x
            py = dropped.tile_y * TILE_SIZE - cam_y
            size = TILE_SIZE - 4
            rect = pygame.Rect(px + 2, py + 2, size, size)
            pygame.draw.rect(screen, dropped.item.color, rect, border_radius=4)
            pygame.draw.rect(screen, (0, 0, 0), rect, 1, border_radius=4)
            txt = get_font(16).render(dropped.item.tile_char, True, (255, 255, 255))
            screen.blit(txt, (px + 10, py + 6))

    def _render_hud(self):
        """简化版 HUD — 仅血条 + 等级。"""
        from src.ui_helpers import draw_progress_bar
        from src.entities.components import AttackType
        eng = self.engine
        if not eng.player:
            return
        c = eng.player.combat
        screen = eng.screen
        bar_x, bar_y, bar_w, bar_h = 10, 10, 200, 16
        ratio = c.current_hp / c.max_hp
        clr = (50, 200, 50) if ratio > 0.5 else (200, 200, 50) if ratio > 0.25 else (200, 50, 50)
        draw_progress_bar(screen, bar_x, bar_y, bar_w, bar_h, ratio, clr, (40, 20, 20))
        txt = get_font(16).render(f"HP:{c.current_hp}/{c.max_hp}  ATK:{c.get_effective_attack()}", True, (220, 220, 220))
        screen.blit(txt, (bar_x + bar_w + 10, bar_y))

    def _draw_text_center(self, text: str, size: int, color: tuple, offset_y: int = 0):
        screen = self.engine.screen
        font = get_font(size)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(screen.get_width() // 2,
                                      screen.get_height() // 2 + offset_y))
        screen.blit(surf, rect)
