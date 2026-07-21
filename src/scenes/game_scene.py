"""
游戏主场景 —— 地图探索 / 战斗 / 背包 / Boss。

这是最大的场景，承载原 game.py PLAYING + BOSS_INTRO + BOSS_CINEMATIC 三个状态。
每个方法不超过 40 行，渲染与逻辑分离。
"""

import math
import time
import random
import pygame
from config import (TILE_SIZE, MAP_WIDTH, MAP_HEIGHT, MAX_FLOORS,
                     COLOR_BLACK, COLOR_WHITE, COLOR_RED, COLOR_GREEN,
                     COLOR_YELLOW, COLOR_GRAY, COLOR_BLUE,
                     PLAYER_ATTACK_RANGE, PICKUP_RANGE,
                     LOOT_DROP_CHANCE, XP_PER_KILL_BASE, XP_PER_KILL_BOSS)
from src.game.floor_config import (get_floor_config, get_floor_narrative,
                                     get_chapter_title, get_chapter_subtitle,
                                     get_chapter_for_floor)
from src.core.scene import Scene
from game import get_font
from src.ui_helpers import (draw_panel, draw_glow_text, draw_progress_bar,
                             ParticleSystem, PANEL_BG, GOLD,
                             DARK_RED, CYBER_BLUE)
from src.world.dungeon_generator import DungeonGenerator
from src.world.tile import TileType
from src.world.special_room import (SpecialRoom, SpecialRoomType,
                                     execute_special_room, get_discovery_message)
from src.entities.monster import Monster, spawn_monster
from src.entities.item import (DroppedItem, Item, EquipmentItem,
                                ConsumableItem, Rarity, generate_random_item,
                                generate_charm_for_skill)
from src.entities.boss import spawn_boss, get_boss_info
from src.entities.player import Direction
from src.entities.components import AttackType
from src.systems.combat_system import find_attack_target, calculate_damage
from src.systems.buff_system import (get_effective_attack, get_effective_speed,
                                      get_buff_display_name, get_buff_short_name,
                                      get_buff_hud_color, format_buff_time,
                                      tick_buffs, apply_triggers)
from src.fx_engine import (player_attack_fx, time_stop_fx,
                            hit_flash_fx, draw_fx_on_screen)
from src.bgm_engine import (stop_bgm,
                             init_bgm)
from src.systems.relic_system import (get_relic_def, get_relic_short_name,
                                       get_relic_display_name, get_relic_hud_color,
                                       player_has_relic, get_all_relic_ids,
                                       try_grant_random_relic)
from src.systems.relic_archive import g_relic_archive


class GameScene(Scene):
    """核心游戏场景 —— 包含地图探索/战斗/背包/Boss战。"""

    def __init__(self, engine):
        super().__init__(engine)
        self._state = "playing"   # playing | boss_intro | boss_cinematic | encounter
        self._last_biome_id = ""               # G6.1: biome boundary detection
        self._hazard_timers: dict = {}         # G6.3: hazard cooldowns per landmark
        self._hazard_confused: float = 0.0     # G6.3: confuse timer
        self._pending_event = None             # G6.4: active biome event
        self._encounter_def = None             # G6.5: current EncounterDef (npc/event/...)
        self._encounter_node = ""              # G6.5: current dialogue node id
        self._encounter_result: list = []      # G6.5: result messages to display
        self._show_relic_panel = False         # B12: R 面板开关
        self._shown_relic_hint = False         # B12.5: 首次 relic 提示
        # D0: 四个 Director (纯骨架，不影响现有行为)
        from src.directors.boss_system_director import BossSystemDirector
        from src.directors.gameplay_system_director import GameplaySystemDirector
        from src.directors.presentation_system_director import (PresentationSystemDirector,
                                                                     PresentationEvent)
        from src.directors.game_flow_director import GameFlowDirector
        from src.directors.audio_director import AudioDirector
        self.boss_sys = BossSystemDirector()
        self.gameplay = GameplaySystemDirector()
        self.presentation = PresentationSystemDirector()
        self.flow = GameFlowDirector()
        self.audio = AudioDirector()
        # G5.8.8: bind effects target for Timeline scheduling
        self.presentation.bind_effects_target(eng._attack_effects)
        self.flow.bind(self)

    # ═══════════════════════════════════════════════════════════
    #  生命周期
    # ═══════════════════════════════════════════════════════════

    def update(self, delta_time: float):
        eng = self.engine
        eng._game_time += delta_time

        if self._state == "boss_cinematic":
            self._update_boss_cinematic(delta_time)
        elif self._state == "encounter":
            pass  # G6.5: freeze gameplay during encounter
        elif self._state == "playing":
            self._update_playing(delta_time)

        self._decay_effects(delta_time)

        # D0: Director 逐帧生命周期
        self.presentation.tick(delta_time)
        self.gameplay.tick(delta_time)
        self.boss_sys.tick(delta_time)
        self.audio.tick(delta_time)                          # G5.8.4: crossfade
        self._check_boss_phase2()                            # G5.8.4: boss enrage audio

        # D1: 随机旁白 (非Boss层, 非事件, 非背包, playing状态)
        fcfg = get_floor_config(self.engine.current_floor)
        if not fcfg.is_boss:
            nar = self.gameplay.tick_narration(
                self.engine.current_floor, fcfg.is_boss,
                False, self.engine.inventory_open, self._state)
            if nar:
                self.presentation.show_message(nar, 3.0)

        # D3: 构筑变化检测
        bmsg = self.gameplay.check_build_change(self.engine.player)
        if bmsg:
            self.presentation.show_message(bmsg, 2.0)
            # G5.8.2: refresh visual theme on BUILD COMPLETE/CHANGED
            # G6.4: compute build in Gameplay layer, pass BuildType to Presentation
            from src.game.build_score import calculate_build
            bt = calculate_build(self.engine.player).identify()
            if self.presentation.update_theme(bt):
                self.presentation.show_message(
                    f"Theme: {self.presentation.active_theme.vfx_preset}", 1.5)

    def _decay_effects(self, delta_time: float):
        """衰减所有活跃攻击特效 + 时停倒计时。"""
        eng = self.engine
        for fx in eng._attack_effects:
            fx["elapsed"] += delta_time
        eng._attack_effects = [f for f in eng._attack_effects
                               if f["elapsed"] < f["duration"]]
        if eng._time_stop_remaining > 0:
            eng._time_stop_remaining -= delta_time
            if eng._time_stop_remaining <= 0:
                eng._time_stop_remaining = 0
                self._apply_pending_damage()

    def render(self):
        if self._state == "boss_intro":
            self._render_boss_intro()
            return
        if self._state == "encounter":
            self._render_playing()
            self._render_encounter_panel()
            return
        self._render_playing()
        if self._state == "boss_cinematic":
            self._render_boss_cinematic_overlay()

    # ═══════════════════════════════════════════════════════════
    #  楼层管理
    # ═══════════════════════════════════════════════════════════

    def enter_floor(self, floor_num: int, seed: int = 0):
        """进入指定关卡 — 生成地图 + 放置实体 + 设置BGM。

        seed=0: 随机生成; seed!=0: 读档恢复 (B8)。
        """
        eng = self.engine
        fcfg = get_floor_config(floor_num)  # D1: 统一配置

        eng.current_floor = floor_num
        eng._game_time = 0.0
        eng.ground_items = []
        eng.inventory_open = False
        eng.inventory_cursor = 0
        eng.stairs_active = False
        eng._attack_effects = []
        eng._time_stop_remaining = 0.0
        eng._pending_damage = []
        # G5.8.4: reset audio / boss state for new floor
        self.audio.reset_phase2()
        self.boss_sys._phase2 = False
        self.presentation.room_msg = ""
        self.presentation.room_msg_timer = 0.0

        # B8: seed=0 → 随机, seed!=0 → 读档恢复
        if seed != 0:
            eng._dungeon_seed = seed
        else:
            eng._dungeon_seed = random.randint(0, 2**32 - 1)

        generator = DungeonGenerator(MAP_WIDTH, MAP_HEIGHT, TILE_SIZE)
        # G6.2: query biome for landmark injection
        from src.game.biome import get_biome_for_floor as _biome_for_gen
        _bio_gen = _biome_for_gen(floor_num)
        eng.game_map = generator.generate(eng._dungeon_seed, biome_id=_bio_gen.id if _bio_gen else "")
        room_centers = generator.get_room_centers()
        self._place_player_in_room(room_centers)

        if fcfg.is_boss:
            eng.monsters = []
        else:
            other = room_centers[1:] if len(room_centers) > 1 else []
            # G6.1: enemy pool from Biome
            from src.game.biome import get_biome_for_floor
            biome = get_biome_for_floor(floor_num)
            pool = biome.enemy_pool if biome else None
            wts = biome.enemy_weights if biome else None
            eng.monsters = self._spawn_monsters_scaled(
                other, fcfg.monster_count, fcfg.hp_mult, fcfg.atk_mult,
                enemy_pool=pool, enemy_weights=wts)

        # G6.1: inject biome tile palette + boundary detection
        from src.game.biome import get_biome_for_floor as _bio
        _b = _bio(floor_num) or get_biome_for_floor(floor_num)  # reuse if already imported
        if _b:
            from src.world.tile_renderer import set_tile_palette
            set_tile_palette(_b.tile_palette)
            # G6.1: ambient biome particles
            if _b.ambient:
                self.presentation.set_ambient_biome(_b.ambient)
            # G6.1: biome boundary → chapter-style intro
            if _b.id != self._last_biome_id and self._last_biome_id:
                self.presentation.chapter_intro_active = True
                self.presentation.chapter_intro_timer = 3.0
                self.presentation.chapter_intro_ch = _b.id
                self.presentation.floor_intro_active = False
                self.presentation.show_message(f"进入 {_b.name}", 2.5)
            self._last_biome_id = _b.id

        eng.stairs_pos = (room_centers[-1] if room_centers
                           else (MAP_WIDTH // 2, MAP_HEIGHT // 2))
        eng.player.combat.current_hp = eng.player.combat.max_hp
        eng.player.reset_attack_timers()

        if fcfg.is_boss:
            eng._boss_intro_data = get_boss_info(floor_num)
            self._state = "boss_intro"
            self.audio.crossfade_to("boss")
        else:
            self._state = "playing"
            # G6.1: biome BGM (prison/volcano/abyss), falls back to dungeon
            from src.game.biome import get_biome_for_floor
            bg = get_biome_for_floor(floor_num)
            self.audio.crossfade_to(bg.bgm if bg and bg.bgm else "dungeon")
        eng._bgm_stopped_for_title = False

        # D1: 楼层入场演出
        if not fcfg.is_boss and not self.gameplay.narr_state.floor_intro_played[floor_num - 1]:
            self.presentation.floor_intro_active = True
            self.presentation.floor_intro_timer = 2.0
            self.presentation.floor_intro_fade = 0.0
            self.presentation.floor_intro_floor = floor_num

        # D1: 章节入场
        ch = get_chapter_for_floor(floor_num)
        if not fcfg.is_boss and ch != self.presentation.chapter_intro_ch:
            self.presentation.chapter_intro_active = True
            self.presentation.chapter_intro_timer = 3.0
            self.presentation.chapter_intro_ch = ch
            self.presentation.floor_intro_active = False

        # D1: 剧情消息 (Boss层由Boss介绍覆盖)
        if fcfg.story_msg and not self.presentation.floor_intro_active and not self.presentation.chapter_intro_active:
            self.presentation.room_msg = fcfg.story_msg
            self.presentation.room_msg_timer = 3.0

        self.gameplay.on_enter_floor(floor_num)  # D0: 生命周期

        # G6.4: 25% chance biome event on non-boss floors
        if not fcfg.is_boss and random.random() < 0.25:
            self._try_trigger_encounter()

    def _place_player_in_room(self, room_centers: list):
        """玩家置于第一个房间中心。"""
        eng = self.engine
        tx, ty = room_centers[0] if room_centers else (MAP_WIDTH // 2, MAP_HEIGHT // 2)
        px, py = eng.game_map.tile_to_pixel(tx, ty)
        eng.player.entity.position = pygame.Vector2(px, py)
        eng.player.entity.sync_rect()

    def _spawn_monsters_scaled(self, room_centers: list,
                                 count: int, hp_mult: float, atk_mult: float,
                                 enemy_pool: list = None,
                                 enemy_weights: list = None) -> list:
        """按楼层难度缩放生成怪物 (D1: 参数来自 FloorConfig, G6.1: pool from Biome)。"""
        eng = self.engine
        if not room_centers:
            return []
        if enemy_pool is None:
            enemy_pool = ["slime", "slime", "orc"]
        if enemy_weights is None:
            enemy_weights = [2, 2, 1]
        spawned = []
        room_index = 0
        while len(spawned) < count and room_index < 500:
            tx, ty = room_centers[room_index % len(room_centers)]
            off_x, off_y = random.randint(-2, 2), random.randint(-2, 2)
            stx, sty = tx + off_x, ty + off_y
            if eng.game_map.is_walkable(stx, sty):
                px, py = eng.game_map.tile_to_pixel(stx, sty)
                m = spawn_monster(px, py, random.choices(enemy_pool, weights=enemy_weights)[0])
                m.combat.max_hp = int(m.combat.max_hp * hp_mult)
                m.combat.current_hp = m.combat.max_hp
                m.combat.attack = int(m.combat.attack * atk_mult)
                spawned.append(m)
            room_index += 1
        return spawned

    def _get_camera_offset(self) -> tuple:
        """计算摄像机偏移——玩家居中 + G5.8.3 震动/冲刺/缩放。"""
        eng = self.engine
        if not eng.player:
            return 0, 0
        p = self.presentation
        sw, sh = eng.screen.get_width(), eng.screen.get_height()
        # G5.8.3: zoom shrinks effective viewport (logical zoom)
        zoom = max(0.85, min(1.3, p.zoom_level))
        sw_eff = int(sw / zoom)
        sh_eff = int(sh / zoom)
        cx = eng.player.entity.rect.centerx - sw_eff // 2
        cy = eng.player.entity.rect.centery - sh_eff // 2
        # G5.8.3: dash offset
        cx -= p.dash_offset_x
        cy -= p.dash_offset_y
        if eng.game_map:
            cx = max(0, min(cx, eng.game_map.pixel_width - sw_eff))
            cy = max(0, min(cy, eng.game_map.pixel_height - sh_eff))
        # G5.8.3: screen shake
        sx, sy = p.get_camera_shake_offset()
        cx += sx; cy += sy
        return int(cx), int(cy)

    # ═══════════════════════════════════════════════════════════
    #  每帧更新（playing 状态）
    # ═══════════════════════════════════════════════════════════

    def _update_playing(self, delta_time: float):
        """playing 状态帧更新 — 背包打开时暂停怪物AI。"""
        eng = self.engine
        keys = pygame.key.get_pressed()
        if eng.inventory_open:
            eng.player.update(delta_time)
            return
        # 移动 + 碰撞
        move_x, move_y = eng.player.handle_input(keys)
        speed = get_effective_speed(eng.player, eng.player.speed)
        self._apply_movement(move_x, move_y, speed, delta_time)
        # B10: 检测是否步入特殊房间
        self._check_special_room_discovery()
        # 怪物 + 楼层检测（时停期间冻结）
        if eng._time_stop_remaining <= 0:
            self._update_monsters(delta_time)
            self._check_floor_transition()
        eng.player.update(delta_time)
        self._tick_skill_regen(delta_time)
        self._tick_buff_system(delta_time)
        self._tick_hazards(delta_time)          # G6.3: biome environmental hazards
        # B10: 消息计时器由 PresentationDirector 管理
        if not eng.stairs_active and self._all_monsters_dead():
            self._activate_stairs()

    def _apply_movement(self, move_x: float, move_y: float,
                        speed: float, dt: float):
        """分轴移动 + 地图碰撞检测 + G6.3 confuse reversal。"""
        eng = self.engine
        entity = eng.player.entity
        # G6.3: confuse reverses input direction
        if self._hazard_confused > 0:
            move_x = -move_x
            move_y = -move_y
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

    def _tick_skill_regen(self, dt: float):
        """自愈 Lv3 持续回复。"""
        for sk in self.engine.player.skills.active_skills:
            if hasattr(sk, "tick_regen"):
                sk.tick_regen(self.engine.player, dt)

    def _tick_buff_system(self, dt: float):
        """每帧结算所有 Buff — 玩家 + 怪物。"""
        eng = self.engine
        tick_buffs(eng.player, dt)
        for m in eng.monsters:
            tick_buffs(m, dt)
        if not eng.player.combat.is_alive:
            self._on_player_death()
            return
        dead = [m for m in eng.monsters if not m.combat.is_alive]
        for m in dead:
            self._on_monster_killed(m)
        eng.monsters = [m for m in eng.monsters if m.combat.is_alive]

    def _tick_hazards(self, dt: float):
        """G6.3: tick biome hazards for the landmark room the player is in."""
        eng = self.engine
        if not eng.player or not eng.game_map:
            return
        # Decay confuse timer
        if self._hazard_confused > 0:
            self._hazard_confused -= dt
        # Get player's current special room
        tx, ty = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx, eng.player.entity.rect.centery)
        room = eng.game_map.get_special_room_at(tx, ty)
        if not room or not room.landmark_id:
            return
        lid = room.landmark_id
        from src.game.hazard import get_hazards_for_landmark
        hazards = get_hazards_for_landmark(lid)
        if not hazards:
            return
        gt = eng._game_time
        for hz in hazards:
            timer_key = f"{lid}:{hz.id}"
            next_tick = self._hazard_timers.get(timer_key, 0.0)
            if gt < next_tick:
                continue
            self._hazard_timers[timer_key] = gt + hz.interval
            self._apply_hazard(hz, room)

    def _apply_hazard(self, hz, room):
        """G6.3: execute a single hazard effect on the player."""
        player = self.engine.player
        if hz.effect == "burn_tick" and hz.damage > 0:
            player.combat.take_damage(hz.damage)
            self.presentation.spawn_themed_damage(
                player.entity.rect.centerx, player.entity.rect.centery - 8,
                hz.damage, is_magic=True)
            if hz.message:
                self.presentation.show_message(hz.message, 1.8)
        elif hz.effect == "slow_zone":
            from src.systems.buff_system import apply_buff
            apply_buff(player, "slow", 1)
            if hz.message:
                self.presentation.show_message(hz.message, 1.8)
        elif hz.effect == "confuse":
            self._hazard_confused = 2.0
            if hz.message:
                self.presentation.show_message(hz.message, 1.8)
        elif hz.effect == "deflect":
            if hz.message:
                self.presentation.show_message(hz.message, 1.8)

    def _on_player_death(self):
        """玩家死亡 → 切到死亡场景。"""
        self.gameplay.on_player_dead(   # D0: 生命周期
            self.engine.current_floor,
            self.engine.player.level if self.engine.player else 1,
            self.engine.player)
        self.flow.on_player_dead()      # D0: 生命周期
        from src.scenes.death_scene import DeathScene
        stop_bgm()
        self.engine._bgm_stopped_for_title = True
        self.engine.change_scene(DeathScene(self.engine))

    # ═══════════════════════════════════════════════════════════
    #  渲染（playing 状态）
    # ═══════════════════════════════════════════════════════════

    def _render_playing(self):
        """渲染游戏画面 — 地图→怪物→掉落物→玩家→HUD→背包。"""
        eng = self.engine
        screen = eng.screen
        screen.fill(COLOR_BLACK)
        cam_x, cam_y = self._get_camera_offset()

        if eng.game_map:
            eng.game_map.render(screen, cam_x, cam_y)
        for monster in eng.monsters:
            monster.render(screen, cam_x, cam_y)
            self._draw_monster_buffs(monster, cam_x, cam_y)
        self._render_ground_items(cam_x, cam_y)
        if eng.player:
            eng.player.render(screen, cam_x, cam_y)
        self._render_attack_effects(cam_x, cam_y)
        self.presentation.render_ambient(screen)             # G6.1: biome ambient particles
        self._render_damage_numbers(cam_x, cam_y)          # G5.8.2: themed damage floats
        self._render_hud()

        if not eng.inventory_open:
            self._draw_text_center(
                "WASD移动 | 空格攻击 | 1-4技能 | E拾取 | I背包 | >下楼 | F11全屏 | Esc返回",
                size=13, color=COLOR_WHITE,
                offset_y=screen.get_height() // 2 - 25)
        if eng.inventory_open:
            self._render_inventory_panel()
        if eng._time_stop_remaining > 0:
            self._render_time_stop_overlay()
        self._render_intro_overlay()          # D1: 章节/楼层入场演出 (最顶层)
        pygame.display.flip()

    def _render_intro_overlay(self):
        """D1: 章节入场 / 楼层入场全屏演出。"""
        p = self.presentation
        screen = self.engine.screen
        sw, sh = screen.get_width(), screen.get_height()

        # 章节入场
        if p.chapter_intro_active:
            ch = p.chapter_intro_ch
            a = min(1.0, p.chapter_intro_timer)
            gold = (255, 200, 50)
            white = (230, 230, 240)
            dark = pygame.Surface((sw, sh))
            dark.set_alpha(int(150 * a)); dark.fill((0, 0, 0))
            screen.blit(dark, (0, 0))
            draw_glow_text(screen, get_chapter_subtitle(ch),
                           sw // 2, sh // 2 - 45, 36, gold, center=True)
            draw_glow_text(screen, get_chapter_title(ch),
                           sw // 2, sh // 2 + 5, 28, white, center=True)
            fn = get_floor_narrative(p.floor_intro_floor if p.floor_intro_floor > 0
                                     else self.engine.current_floor)
            if fn:
                draw_glow_text(screen, fn.subtitle,
                               sw // 2, sh // 2 + 45, 18, (180, 180, 200), center=True)
            return

        # 楼层入场
        if p.floor_intro_active:
            fn = get_floor_narrative(p.floor_intro_floor)
            if fn:
                a = p.floor_intro_fade
                gold = (255, 200, 50)
                white = (230, 230, 240)
                dark = pygame.Surface((sw, sh))
                dark.set_alpha(int(120 * a)); dark.fill((0, 0, 0))
                screen.blit(dark, (0, 0))
                draw_glow_text(screen, f"Floor {p.floor_intro_floor}",
                               sw // 2, sh // 2 - 50, 20, gold, center=True)
                draw_glow_text(screen, "══════════════",
                               sw // 2, sh // 2 - 28, 18, gold, center=True)
                draw_glow_text(screen, fn.title,
                               sw // 2, sh // 2, 28, white, center=True)
                draw_glow_text(screen, fn.subtitle,
                               sw // 2, sh // 2 + 35, 16, (180, 180, 200), center=True)
                draw_glow_text(screen, "══════════════",
                               sw // 2, sh // 2 + 55, 18, gold, center=True)

    # ═══════════════════════════════════════════════════════════
    #  输入处理
    # ═══════════════════════════════════════════════════════════

    def on_keydown(self, key: int):
        """游戏中按键 — 区分普通模式和背包模式。"""
        eng = self.engine
        if self._state == "boss_intro":
            self._on_boss_intro_keydown(key)
            return
        if self._state == "encounter":
            self._on_encounter_keydown(key)
            return
        if eng.inventory_open:
            self._handle_inventory_key(key)
            return
        if key == pygame.K_ESCAPE:
            self._save_and_quit_to_title()
        elif key == pygame.K_SPACE:
            self._handle_player_attack()
        elif key == pygame.K_e:
            # B8: 优先特殊房间交互, 否则走拾取
            if eng.player and eng.game_map:
                tx, ty = eng.game_map.pixel_to_tile(
                    eng.player.entity.rect.centerx,
                    eng.player.entity.rect.centery)
                room = eng.game_map.get_special_room_at(tx, ty)
                if room and not room.triggered:
                    self._interact_special()
                else:
                    self._handle_pickup()
            else:
                self._handle_pickup()
        elif key == pygame.K_r:
            self._show_relic_panel = not self._show_relic_panel
        elif key == pygame.K_i:
            eng.inventory_open = True
            eng.inventory_cursor = 0
        elif pygame.K_1 <= key <= pygame.K_4:
            self._use_skill(key - pygame.K_1)

    def _save_and_quit_to_title(self):
        """Esc → 自动存档 → 返回标题。"""
        from saves.save_manager import save_game
        from src.scenes.title_scene import TitleScene
        eng = self.engine
        if eng.player and eng.player.combat.is_alive:
            eng._max_unlocked_floor = max(eng._max_unlocked_floor, eng.current_floor)
            spr, spd = self._collect_special_state()
            rlc = [r.id for r in getattr(eng.player, 'relics', [])]
            save_game(eng.player, eng.current_floor, eng._max_unlocked_floor,
                      getattr(eng, '_dungeon_seed', 0), spr, spd, rlc)
        eng.change_scene(TitleScene(eng))

    # ═══════════════════════════════════════════════════════════
    #  战斗
    # ═══════════════════════════════════════════════════════════

    def _handle_player_attack(self):
        """普攻 — 找最近目标 → 伤害计算 → G5.8.7 dispatch。"""
        eng = self.engine
        player = eng.player
        if not player or not player.combat.is_alive or not player.can_attack(eng._game_time):
            return
        cr = player.entity.rect
        # Swing VFX + SFX (always plays, even on miss)
        eng._attack_effects += player_attack_fx(
            cr.centerx, cr.centery, int(PLAYER_ATTACK_RANGE * TILE_SIZE))
        self.audio.on_presentation_event("melee")
        target = find_attack_target(player.entity.rect, eng.monsters, PLAYER_ATTACK_RANGE)
        if target is None:
            return
        dmg = calculate_damage(
            get_effective_attack(player),
            target.combat.get_effective_defense(player.attack_type),
            player.attack_type)
        player._last_attack_time = eng._game_time
        if eng._time_stop_remaining > 0:
            eng._pending_damage.append((target, dmg))
        else:
            target.combat.take_damage(dmg)
            # G5.8.7: unified hit reaction via dispatch
            ev = PresentationEvent(
                kind="melee_hit",
                cx=target.entity.rect.centerx,
                cy=target.entity.rect.centery,
                dmg=dmg,
                dmg_is_magic=(player.attack_type == AttackType.MAGICAL),
                sfx_override="hit")
            eng._attack_effects += self.presentation.dispatch(ev)
            eng._attack_effects += hit_flash_fx(
                int(target.entity.position.x), int(target.entity.position.y),
                target.entity.size[0])
            if not target.combat.is_alive:
                self._on_monster_killed(target)
                eng.monsters.remove(target)

    # ── 技能 ─────────────────────────────────────────────

    def _use_skill(self, index: int):
        """释放技能 — 路由到时停/普通分支。"""
        eng = self.engine
        player = eng.player
        if not player or index >= len(player.skills.active_skills):
            return
        skill = player.skills.active_skills[index]
        if skill.name == "The World":
            self._activate_time_stop(skill, index)
        elif eng._time_stop_remaining > 0:
            self._use_skill_in_time_stop(skill, index)
        else:
            self._use_skill_normal(skill, index)

    def _activate_time_stop(self, skill, index: int):
        """激活 The World — 冻结全屏 + 暂存伤害。"""
        eng = self.engine
        result = eng.player.skills.use_active(
            index, eng.player, eng.monsters, eng.game_map, eng._game_time)
        if result and "冷却中" not in result:
            eng._time_stop_remaining = skill.get_stop_duration()
            eng._pending_damage = []
            ev = PresentationEvent(kind="time_stop",
                                   cx=eng.player.entity.rect.centerx,
                                   cy=eng.player.entity.rect.centery)
            fx = self.presentation.dispatch(ev) + time_stop_fx(
                eng.player.entity.rect.centerx,
                eng.player.entity.rect.centery)
            for f in fx:
                f["duration"] = min(f["duration"], eng._time_stop_remaining * 0.3)
            eng._attack_effects += fx

    def _use_skill_in_time_stop(self, skill, index: int):
        """时停期间技能 — 伤害暂存，VFX via dispatch。"""
        eng = self.engine
        pre_hp = {id(m): m.combat.current_hp for m in eng.monsters}
        result = eng.player.skills.use_active(
            index, eng.player, eng.monsters, eng.game_map, eng._game_time)
        if result and "冷却中" not in result:
            cx = eng.player.entity.rect.centerx
            cy = eng.player.entity.rect.centery
            ev = PresentationEvent(kind="skill_cast", skill_name=skill.name,
                                   cx=cx, cy=cy, direction=eng.player.direction)
            eng._attack_effects += self.presentation.dispatch(ev)
        if result:
            for m in eng.monsters:
                if id(m) in pre_hp:
                    delta = pre_hp[id(m)] - m.combat.current_hp
                    if delta > 0:
                        eng._pending_damage.append((m, delta))
                        m.combat.current_hp = pre_hp[id(m)]
                        m.combat.is_alive = True

    def _use_skill_normal(self, skill, index: int):
        """正常释放技能 — G5.8.7: dispatch 统一处理 VFX/SFX/震屏/伤害数字。"""
        eng = self.engine
        cx = eng.player.entity.rect.centerx
        cy = eng.player.entity.rect.centery
        # Track pre-HP for damage floats
        pre_hp = {id(m): m.combat.current_hp for m in eng.monsters if m.combat.is_alive}
        result = eng.player.skills.use_active(
            index, eng.player, eng.monsters, eng.game_map, eng._game_time)
        if result and "冷却中" not in result:
            # G5.8.7: unified cast dispatch — VFX + SFX from skill name
            from src.entities.components import AttackType
            t = find_attack_target(eng.player.entity.rect, eng.monsters, 10.0)
            ev = PresentationEvent(
                kind="skill_cast",
                skill_name=skill.name, skill_level=skill.level,
                cx=cx, cy=cy,
                target_cx=(t.entity.rect.centerx if t else cx + 100),
                target_cy=(t.entity.rect.centery if t else cy),
                direction=eng.player.direction)
            eng._attack_effects += self.presentation.dispatch(ev)
            # Per-target themed damage numbers
            total_dmg = 0
            is_magic = getattr(skill, 'attack_type', None) == AttackType.MAGICAL
            for m in eng.monsters:
                hp_before = pre_hp.get(id(m), 0)
                dmg_taken = hp_before - m.combat.current_hp
                if dmg_taken > 0:
                    total_dmg += dmg_taken
                    self.presentation.spawn_themed_damage(
                        m.entity.rect.centerx, m.entity.rect.centery - 8,
                        dmg_taken, is_magic)
            if total_dmg >= 20:
                self.presentation.trigger_shake(max(3, min(10, total_dmg // 5)))
        if result:
            dead = [m for m in eng.monsters if not m.combat.is_alive]
            for m in dead:
                self._on_monster_killed(m)
                eng.monsters.remove(m)

    def _apply_pending_damage(self):
        """时停结束 — 一次性结算所有暂存伤害。"""
        eng = self.engine
        if not eng._pending_damage:
            return
        for target, dmg in eng._pending_damage:
            if target.combat.is_alive:
                target.combat.take_damage(dmg)
        dead = [m for m in eng.monsters if not m.combat.is_alive]
        for m in dead:
            self._on_monster_killed(m)
            eng.monsters.remove(m)
        eng._pending_damage = []

    # ═══════════════════════════════════════════════════════════
    #  怪物管理
    # ═══════════════════════════════════════════════════════════

    def _update_monsters(self, delta_time: float):
        """更新所有怪物AI — 检测玩家受伤播放音效。"""
        eng = self.engine
        if not eng.player or not eng.player.combat.is_alive:
            return
        hp_before = eng.player.combat.current_hp
        for m in eng.monsters:
            m.update_ai(eng.player, eng.game_map, delta_time,
                       eng._game_time, eng.monsters, eng._attack_effects)
        if eng.player.combat.current_hp < hp_before:
            self.audio.on_presentation_event("hit")

    def _on_monster_killed(self, monster: Monster):
        """怪物死亡 — 经验 + 掉落 + 粒子 + Boss奖励。"""
        eng = self.engine
        self._spawn_death_particles(monster)
        if monster.is_boss:
            if eng.player and eng.player.give_xp(XP_PER_KILL_BOSS):
                self.audio.on_presentation_event("levelup", 0.8)
            # D4: WorldState Boss击杀标记
            floor = eng.current_floor
            from src.game.world_state import WorldFlag
            if floor == 5:  self.gameplay.world_state.set(WorldFlag.Boss1_Defeated)
            if floor == 10: self.gameplay.world_state.set(WorldFlag.Boss2_Defeated)
            if floor == 15:
                self.gameplay.world_state.set(WorldFlag.Boss3_Defeated)
                if (self.gameplay.world_state.has(WorldFlag.Boss1_Defeated)
                        and self.gameplay.world_state.has(WorldFlag.Boss2_Defeated)):
                    self.gameplay.world_state.set(WorldFlag.All_Boss_Defeated)
            self.boss_sys.notify_death()  # D5
            self._drop_boss_reward(monster)
            return
        xp_gained = XP_PER_KILL_BASE + int(monster.combat.max_hp * 0.5)
        if eng.player and eng.player.give_xp(xp_gained):
            self.audio.on_presentation_event("levelup", 0.8)
        if random.random() > LOOT_DROP_CHANCE:
            pass  # always fall through to relic checks
        else:
            tx, ty = eng.game_map.pixel_to_tile(
                monster.entity.position.x, monster.entity.position.y)
            eng.ground_items.append(DroppedItem(generate_random_item(), tx, ty))
        # B11: leech_blade — 20% 回 5 HP
        if eng.player and player_has_relic(eng.player, "leech_blade"):
            d = get_relic_def("leech_blade")
            chance = d.param if d else 0.2
            heal = d.param2 if d else 5
            if random.random() < chance:
                eng.player.combat.heal(heal)
        # B12: battle_totem — 15% 获得 attack_up
        if eng.player and player_has_relic(eng.player, "battle_totem"):
            d = get_relic_def("battle_totem")
            chance = d.param if d else 0.15
            if random.random() < chance:
                from src.systems.buff_system import apply_buff
                apply_buff(eng.player, "attack_up", 1)

    def _drop_boss_reward(self, monster: Monster):
        """Boss击杀奖励 — 传说武器 + 护符 + 药水 + 技能。"""
        eng = self.engine
        tx, ty = eng.game_map.pixel_to_tile(
            monster.entity.position.x, monster.entity.position.y)
        weapon = EquipmentItem("魔渊之刃", Rarity.LEGENDARY,
                               "weapon", atk_bonus=18, pdef_bonus=3, mdef_bonus=0)
        eng.ground_items.append(DroppedItem(weapon, tx, ty))
        skill_names = [type(s).__name__ for s in eng.player.skills.active_skills]
        if skill_names:
            charm = generate_charm_for_skill(random.choice(skill_names), Rarity.LEGENDARY)
            if charm:
                eng.ground_items.append(DroppedItem(charm, tx + 1, ty))
        potion = ConsumableItem("神谕药剂", Rarity.LEGENDARY, "heal", 80)
        eng.ground_items.append(DroppedItem(potion, tx + 2, ty))
        from src.entities.skill import get_learned_skill_names, random_skill
        if eng.player.skills.can_learn():
            names = get_learned_skill_names(eng.player.skills)
            eng.player.skills.learn(random_skill(names))
            eng.player.skills.apply_all_passives(eng.player)

    def _spawn_death_particles(self, monster: Monster):
        """怪物死亡彩色粒子爆散。"""
        eng = self.engine
        cx = monster.entity.rect.centerx
        cy = monster.entity.rect.centery
        n = 10 if monster.is_boss else 5
        for _ in range(n):
            dx, dy = random.randint(-20, 20), random.randint(-20, 20)
            eng._attack_effects.append({
                "kind": "spark", "x": cx + dx * 3, "y": cy + dy * 3,
                "radius": 2 + random.randint(0, 3), "color": monster.color,
                "duration": 0.4, "elapsed": 0.0,
            })

    def _get_boss(self):
        """获取当前存活的Boss怪物。"""
        for m in self.engine.monsters:
            if m.is_boss and m.combat.is_alive:
                return m
        return None

    def _check_boss_phase2(self):
        """G5.8.4: 检测Boss进入Phase2/enrage，触发音频。"""
        boss = self._get_boss()
        if not boss or not boss.is_boss:
            return
        ai = getattr(boss, 'ai', None)
        if ai and getattr(ai, 'is_enraged', False):
            if not self.boss_sys._phase2:
                self.boss_sys._phase2 = True
                self.audio.play_boss_phase2_cue()
                # G5.8.7: unified boss phase2 dispatch
                ev = PresentationEvent(kind="boss_phase2",
                                       cx=boss.entity.rect.centerx,
                                       cy=boss.entity.rect.centery,
                                       intensity=10)
                self.engine._attack_effects += self.presentation.dispatch(ev)

    # ═══════════════════════════════════════════════════════════
    #  楼梯 & 楼层切换
    # ═══════════════════════════════════════════════════════════

    def _all_monsters_dead(self) -> bool:
        return all(not m.combat.is_alive for m in self.engine.monsters)

    def _activate_stairs(self):
        """激活楼梯 + 自动存档（Boss存活时禁止）。"""
        eng = self.engine
        if not eng.stairs_pos or eng.stairs_active:
            return
        boss = self._get_boss()
        if boss and boss.combat.is_alive:
            return
        eng.game_map.set_tile(eng.stairs_pos[0], eng.stairs_pos[1], TileType.STAIRS_DOWN)
        eng.stairs_active = True
        eng._max_unlocked_floor = max(eng._max_unlocked_floor, eng.current_floor)
        from saves.save_manager import save_game
        spr, spd = self._collect_special_state()
        rlc = [r.id for r in getattr(eng.player, 'relics', [])]
        save_game(eng.player, eng.current_floor, eng._max_unlocked_floor,
                  getattr(eng, '_dungeon_seed', 0), spr, spd, rlc)

    def _check_floor_transition(self):
        """检测玩家是否站在激活楼梯上按 > 键。"""
        eng = self.engine
        if not eng.stairs_active or not eng.player or not eng.stairs_pos:
            return
        keys = pygame.key.get_pressed()
        if not keys[pygame.K_PERIOD]:
            return
        px, py = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx, eng.player.entity.rect.centery)
        if (px, py) != eng.stairs_pos:
            return
        next_floor = eng.current_floor + 1
        if next_floor > MAX_FLOORS:
            self.gameplay.on_game_clear(  # D0: 生命周期
                eng.current_floor,
                eng.player.level if eng.player else 1,
                eng.player)
            self.flow.on_game_clear()     # D0: 生命周期
            from src.scenes.victory_scene import VictoryScene
            self.engine.change_scene(VictoryScene(self.engine))
        else:
            self.enter_floor(next_floor)

    # ═══════════════════════════════════════════════════════════
    #  拾取
    # ═══════════════════════════════════════════════════════════

    def _handle_pickup(self):
        """拾取玩家附近最近的地面物品。"""
        eng = self.engine
        if not eng.player:
            return
        best, best_dist = None, PICKUP_RANGE * TILE_SIZE
        pr = eng.player.entity.rect
        for dropped in eng.ground_items:
            px = dropped.tile_x * TILE_SIZE + TILE_SIZE // 2
            py = dropped.tile_y * TILE_SIZE + TILE_SIZE // 2
            dist = ((pr.centerx - px) ** 2 + (pr.centery - py) ** 2) ** 0.5
            if dist < best_dist:
                best_dist, best = dist, dropped
        if best and eng.player.inventory.add(best.item, eng.player):
            eng.ground_items.remove(best)
            self.audio.on_presentation_event("pickup", 0.4)

    # ═══════════════════════════════════════════════════════════
    #  特殊房间交互 (B8/B9/B10)
    # ═══════════════════════════════════════════════════════════

    def _interact_special(self):
        """E 键触发特殊房间 —— 每个房间仅一次。"""
        eng = self.engine
        if not eng.player or not eng.game_map:
            return
        tx, ty = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx,
            eng.player.entity.rect.centery)
        room = eng.game_map.get_special_room_at(tx, ty)
        if not room or room.triggered:
            return
        # G6.2: landmarks are passive narrative, not loot rooms
        if room.landmark_id:
            from src.game.landmark import get_landmark_by_id
            lm = get_landmark_by_id(room.landmark_id)
            if lm and lm.message:
                self._show_room_message(lm.message)
            room.triggered = True
            return
        msg = execute_special_room(room.type, eng.player)
        room.triggered = True
        self._show_room_message(msg)
        # B12.5: 首次获得 relic 时提示按 R
        if (not self._shown_relic_hint and eng.player
                and getattr(eng.player, 'relics', [])):
            self._shown_relic_hint = True
            self._show_room_message("按 R 可查看圣物面板")

    def _check_special_room_discovery(self):
        """每帧检测玩家是否首次步入特殊房间 (B10)。"""
        eng = self.engine
        if not eng.game_map or not eng.player:
            return
        tx, ty = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx,
            eng.player.entity.rect.centery)
        room = eng.game_map.get_special_room_at(tx, ty)
        if not room or room.discovered:
            return
        room.discovered = True
        # G6.2: landmarks have custom discovery messages
        if room.landmark_id:
            from src.game.landmark import get_landmark_by_id
            lm = get_landmark_by_id(room.landmark_id)
            msg = lm.discovery_msg if lm else f"你发现了一处特殊的地点——{room.landmark_id}。"
            self._show_room_message(msg)
            if lm and lm.message:
                self._show_room_message(lm.message)  # narrative follow-up
        else:
            self._show_room_message(get_discovery_message(room.type))

    def _show_room_message(self, msg: str):
        """显示临时消息 (2.5秒后自动消失)。"""
        self.presentation.room_msg = msg
        self.presentation.room_msg_timer = 2.5

    def _collect_special_state(self):
        """收集当前楼层特殊房间 triggered / discovered 状态。"""
        eng = self.engine
        spr, spd = [], []
        if eng.game_map:
            for sr in eng.game_map.special_rooms:
                spr.append(sr.triggered)
                spd.append(sr.discovered)
        return spr, spd

    def _draw_room_message(self, screen):
        """渲染房间消息条 —— 屏幕底部中央。"""
        if self.presentation.room_msg_timer <= 0 or not self.presentation.room_msg:
            return
        sw, sh = screen.get_width(), screen.get_height()
        font = get_font(18)
        if not font:
            return
        alpha = min(1.0, self.presentation.room_msg_timer / 0.6)
        text = font.render(self.presentation.room_msg, True,
                           (int(255 * alpha), int(255 * alpha),
                            int(200 * alpha)))
        tw = text.get_width()
        px = sw // 2 - tw // 2
        py = sh - 70
        bg = pygame.Surface((tw + 32, 28), pygame.SRCALPHA)
        bg.fill((10, 10, 20, int(180 * alpha)))
        screen.blit(bg, (px - 16, py - 4))
        screen.blit(text, (px, py))

    # ═══════════════════════════════════════════════════════════
    #  HUD 渲染
    # ═══════════════════════════════════════════════════════════

    def _render_hud(self):
        """左上角：血条 + 属性 + 等级/XP + 楼层 + Boss血条 + 技能栏 + Buff。"""
        eng = self.engine
        if not eng.player:
            return
        combat = eng.player.combat
        bar_x, bar_y, bar_w, bar_h = 10, 10, 200, 16
        self._draw_player_hp_bar(combat, bar_x, bar_y, bar_w, bar_h)
        lvl, xp, xp_next = eng.player.get_level_info()
        self._draw_xp_bar(bar_x, bar_y + bar_h + 4, bar_w, 10, xp, xp_next, lvl)
        boss = self._get_boss()
        if boss:
            self._render_boss_hp_bar(boss)
        font = get_font(16)
        floor_text = f"第 {eng.current_floor}/{MAX_FLOORS} 层"
        eng.screen.blit(font.render(floor_text, True, COLOR_YELLOW),
                        (bar_x + bar_w + 10, bar_y + bar_h + 4))
        if eng.stairs_active:
            s = font.render("楼梯已开启！按 > 下楼", True, (100, 255, 100))
            eng.screen.blit(s, (bar_x, bar_y + bar_h + 28))
        self._render_skill_bar(bar_x, bar_y + bar_h + 50)
        self._draw_player_buffs()
        # B11: 玩家 Relic HUD
        self._draw_player_relics()
        # B12: R 面板
        if self._show_relic_panel:
            self._draw_relic_panel()
        # B12.5: 快捷键提示 (右下角)
        hint = get_font(12).render("[R]圣物  [I]背包  [ESC]保存", True, (140, 140, 160))
        eng.screen.blit(hint, (eng.screen.get_width() - hint.get_width() - 14,
                                eng.screen.get_height() - 26))
        # B10: 房间消息条
        self._draw_room_message(eng.screen)

    def _draw_player_hp_bar(self, combat, x: int, y: int, w: int, h: int):
        """美化玩家血条。"""
        screen = self.engine.screen
        ratio = combat.current_hp / combat.max_hp
        clr = (50, 200, 50) if ratio > 0.5 else (200, 200, 50) if ratio > 0.25 else (200, 50, 50)
        draw_progress_bar(screen, x, y, w, h, ratio, clr, (40, 20, 20))
        pd = combat.get_effective_defense(AttackType.PHYSICAL)
        md = combat.get_effective_defense(AttackType.MAGICAL)
        txt = get_font(16).render(
            f"HP:{combat.current_hp}/{combat.max_hp}  ATK:{combat.get_effective_attack()}"
            f"  PD:{pd} MD:{md}", True, (220, 220, 220))
        screen.blit(txt, (x + w + 10, y))

    def _draw_xp_bar(self, x: int, y: int, w: int, h: int,
                     xp: int, xp_next: int, level: int):
        """美化经验条。"""
        screen = self.engine.screen
        ratio = min(1.0, xp / max(1, xp_next))
        draw_progress_bar(screen, x, y, w, h, ratio, (80, 120, 255), (30, 30, 60))
        txt = get_font(13).render(f"Lv{level}  XP:{xp}/{xp_next}", True, (180, 200, 255))
        screen.blit(txt, (x + 2, y + h + 2))

    def _render_skill_bar(self, start_x: int, start_y: int):
        """美化技能栏 — 编号框 + 名称 + 冷却条。"""
        eng = self.engine
        screen = eng.screen
        active = eng.player.skills.active_skills
        if not active:
            return
        f, bw, bh = get_font(14), 90, 10
        for i, sk in enumerate(active):
            ry = start_y + i * (bh + 20)
            ready = sk.can_use(eng._game_time)
            num_bg = (50, 160, 50) if ready else (60, 60, 60)
            nr = pygame.Rect(start_x, ry, 22, 18)
            pygame.draw.rect(screen, num_bg, nr, border_radius=3)
            screen.blit(f.render(str(i + 1), True, (255, 255, 255)), (start_x + 7, ry + 1))
            bonus = (sk.get_level_bonus_text() if hasattr(sk, "get_level_bonus_text")
                     else f"Lv{sk.level}")
            label = f.render(f"{sk.name} {bonus}", True,
                             (180, 220, 255) if ready else (100, 100, 100))
            screen.blit(label, (start_x + 26, ry + 2))
            ratio = 1.0 - sk.remaining_cooldown(eng._game_time) / sk.cooldown
            draw_progress_bar(screen, start_x + 26, ry + 16, bw, bh, ratio,
                              (60, 180, 255) if ready else (70, 70, 70), (30, 30, 45))

    def _render_boss_hp_bar(self, boss: Monster):
        """顶部中央 Boss 血条 — 双线框+渐变填充+脉冲。"""
        screen = self.engine.screen
        c = boss.combat
        bw, bh = 400, 20
        bx = (screen.get_width() - bw) // 2
        by = 4
        ratio = c.current_hp / c.max_hp
        pulse = int(220 + 25 * math.sin(time.time() * 5))
        pygame.draw.rect(screen, (pulse, 40, 40), (bx - 2, by - 2, bw + 4, bh + 4), 2)
        pygame.draw.rect(screen, (30, 5, 5), (bx, by, bw, bh))
        fill_w = int(bw * ratio)
        segments = 10
        seg_w = fill_w // segments if segments else 0
        for i in range(segments):
            t = i / segments
            cr = int(200 - t * 60); cg = int(40 + t * 120); cb = int(30 + t * 20)
            sx = bx + i * seg_w
            sw = seg_w + (fill_w - (i + 1) * seg_w if i == segments - 1 else 0)
            if sw > 0:
                pygame.draw.rect(screen, (cr, cg, cb), (sx, by, sw, bh))
        pygame.draw.rect(screen, (255, 150, 80, 100), (bx, by, fill_w, bh // 3))
        f = get_font(18)
        txt = f.render(f"⚔ {boss.name}  HP:{c.current_hp}/{c.max_hp}", True, (255, 220, 100))
        screen.blit(txt, (bx + (bw - txt.get_width()) // 2, by + bh + 3))

    def _draw_player_buffs(self):
        """玩家 Buff HUD — 技能栏下方。"""
        eng = self.engine
        if not eng.player or not eng.player.active_buffs:
            return
        x, y = 10, 56 + len(eng.player.skills.active_skills) * 28 + 4
        for b in eng.player.active_buffs:
            line = f"{get_buff_display_name(b.id)} x{b.stacks}  {format_buff_time(b.remaining)}"
            surf = get_font(14).render(line, True, get_buff_hud_color(b.id))
            eng.screen.blit(surf, (x, y))
            y += 18

    # B11/B12: Relic HUD + R 面板
    def _draw_player_relics(self):
        eng = self.engine
        if not eng.player or not getattr(eng.player, 'relics', []):
            return
        x, y = 10, 56 + len(eng.player.skills.active_skills) * 28 + 4
        if eng.player.active_buffs:
            y += len(eng.player.active_buffs) * 18 + 4
        font = get_font(13)
        label = font.render("圣物:", True, (255, 220, 100))
        eng.screen.blit(label, (x, y))
        cx = x + label.get_width() + 4
        for r in eng.player.relics:
            d = get_relic_def(r.id)
            if not d: continue
            rc = (100, 170, 255) if d.rarity == "rare" else (190, 100, 255) if d.rarity == "epic" else (255, 220, 100)
            token = font.render(d.short_name + " ", True, rc)
            eng.screen.blit(token, (cx, y))
            cx += token.get_width()

    def _draw_relic_panel(self):
        eng = self.engine
        if not eng.player: return
        sw, sh = eng.screen.get_width(), eng.screen.get_height()
        panel_w, panel_x = 370, sw - 390
        panel_y = 70
        relics = getattr(eng.player, 'relics', [])
        line_h = 24
        panel_h = 66 + (len(relics) if relics else 1) * line_h
        panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)
        pygame.draw.rect(eng.screen, (15, 15, 35), panel_rect, border_radius=8)
        pygame.draw.rect(eng.screen, (100, 100, 160), panel_rect, width=2, border_radius=8)
        eng.screen.set_clip(None)
        # M18: 标题含收集率
        coll = g_relic_archive.collected_count()
        total = g_relic_archive.total_relic_count()
        pct = g_relic_archive.collection_pct() * 100.0
        title = get_font(18).render(f"圣物图鉴  {coll}/{total} ({pct:.0f}%)", True, (255, 255, 200))
        eng.screen.blit(title, (panel_x + 14, panel_y + 10))
        if not relics:
            txt = get_font(14).render("本层尚未获得圣物。", True, (160, 160, 180))
            eng.screen.blit(txt, (panel_x + 14, panel_y + 44))
            return
        ly = panel_y + 44
        for r in relics:
            d = get_relic_def(r.id)
            if not d: continue
            rarity_cn = "稀有" if d.rarity == "rare" else "史诗" if d.rarity == "epic" else "普通"
            rc = (100, 170, 255) if d.rarity == "rare" else (190, 100, 255) if d.rarity == "epic" else (255, 220, 100)
            # M18: mastery 星标
            mlv = g_relic_archive.mastery_level(r.id)
            stars = "★" * mlv
            line = f"{stars} [{rarity_cn}] {d.name} - {d.desc}"
            txt = get_font(14).render(line, True, rc)
            eng.screen.blit(txt, (panel_x + 14, ly))
            ly += line_h

    def _draw_monster_buffs(self, monster, cam_x, cam_y):
        """怪物头顶 Buff 简写标签。"""
        if not monster.active_buffs:
            return
        label = " ".join(f"{get_buff_short_name(b.id)}x{b.stacks}"
                         for b in monster.active_buffs)
        surf = get_font(12).render(label, True, get_buff_hud_color(monster.active_buffs[0].id))
        px = monster.entity.rect.x - cam_x + (monster.entity.rect.w - surf.get_width()) / 2
        py = monster.entity.rect.y - cam_y - 16
        self.engine.screen.blit(surf, (px, py))

    # ═══════════════════════════════════════════════════════════
    #  背包面板
    # ═══════════════════════════════════════════════════════════

    def _render_inventory_panel(self):
        """美化背包面板 — 装备槽 + 物品列表。"""
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
        self._inv_draw_equipped(inv, x0, y0, pr)
        self._inv_draw_items(inv, x0, y0)
        tips = "↑↓选择  X装备  U使用  D丢弃  I关闭"
        tip = get_font(16).render(tips, True, (140, 140, 140))
        screen.blit(tip, (pr.x + (pw - tip.get_width()) // 2, pr.bottom - 30))

    def _inv_draw_equipped(self, inv, x0: int, y0: int, pr: pygame.Rect):
        """绘制装备槽。"""
        screen = self.engine.screen
        f18 = get_font(18)
        eq_text = "◆ 装备: "
        for slot, eq in inv.equipped.items():
            eq_text += f"【{slot}】{eq.get_description()}  " if eq else f"【{slot}】空  "
        eq = f18.render(eq_text, True, GOLD)
        screen.blit(eq, (x0, y0))
        pygame.draw.line(screen, (60, 60, 90), (x0, y0 + 28),
                         (pr.right - 30, y0 + 28), 1)

    def _inv_draw_items(self, inv, x0: int, y0: int):
        """绘制物品列表。"""
        screen = self.engine.screen
        f18 = get_font(18)
        for idx, item in enumerate(inv.items):
            ry = y0 + 38 + idx * 30
            mk = "▶" if idx == self.engine.inventory_cursor else " "
            t = f18.render(f"{mk} [{idx+1:>2}] {item.get_description()}", True, item.color)
            screen.blit(t, (x0, ry))
        if not inv.items:
            em = f18.render("背包空空如也", True, (120, 120, 120))
            screen.blit(em, (x0, y0 + 38))

    def _handle_inventory_key(self, key: int):
        """背包面板按键 — 导航 / 装备 / 使用 / 丢弃。"""
        eng = self.engine
        inv = eng.player.inventory
        if key in (pygame.K_i, pygame.K_ESCAPE):
            eng.inventory_open = False
        elif key == pygame.K_UP:
            eng.inventory_cursor = max(0, eng.inventory_cursor - 1)
        elif key == pygame.K_DOWN:
            eng.inventory_cursor = min(
                max(0, len(inv.items) - 1), eng.inventory_cursor + 1)
        elif key == pygame.K_x:
            inv.equip(eng.inventory_cursor, eng.player)
            eng.inventory_cursor = self._clamp_cursor(
                eng.inventory_cursor, len(inv.items))
        elif key == pygame.K_u:
            inv.use(eng.inventory_cursor, eng.player)
            eng.inventory_cursor = self._clamp_cursor(
                eng.inventory_cursor, len(inv.items))
        elif key == pygame.K_d:
            inv.remove(eng.inventory_cursor)
            eng.inventory_cursor = self._clamp_cursor(
                eng.inventory_cursor, len(inv.items))

    # ═══════════════════════════════════════════════════════════
    #  掉落物 & 攻击特效渲染
    # ═══════════════════════════════════════════════════════════

    def _render_ground_items(self, camera_x: int, camera_y: int):
        """绘制掉落物 — 光晕+脉冲+高光。"""
        eng = self.engine
        screen = eng.screen
        for dropped in eng.ground_items:
            px = dropped.tile_x * TILE_SIZE - camera_x
            py = dropped.tile_y * TILE_SIZE - camera_y
            size = TILE_SIZE - 4
            cx, cy = px + TILE_SIZE // 2, py + TILE_SIZE // 2
            pulse = 6 + int(3 * math.sin(time.time() * 5 + px * 0.1))
            glow = pygame.Rect(cx - pulse, cy - pulse, pulse * 2, pulse * 2)
            c = dropped.item.color
            pygame.draw.rect(screen, (c[0]//3, c[1]//3, c[2]//3), glow, 1, border_radius=3)
            rect = pygame.Rect(px + 2, py + 2, size, size)
            pygame.draw.rect(screen, c, rect, border_radius=4)
            hl = tuple(min(255, v + 80) for v in c[:3])
            pygame.draw.rect(screen, hl, (px + 4, py + 3, size - 8, 5), border_radius=2)
            pygame.draw.rect(screen, (0, 0, 0), rect, 1, border_radius=4)
            txt = get_font(16).render(dropped.item.tile_char, True, (255, 255, 255))
            screen.blit(txt, (px + 10, py + 6))

    def _render_attack_effects(self, camera_x: int, camera_y: int):
        """委托 fx_engine 绘制所有活跃攻击特效。"""
        for fx in self.engine._attack_effects:
            draw_fx_on_screen(self.engine.screen, fx, camera_x, camera_y)

    def _render_damage_numbers(self, camera_x: int, camera_y: int):
        """G5.8.2: 绘制浮动伤害数字 (主题色 3-tier)。"""
        screen = self.engine.screen
        font = get_font(16)
        for df in self.presentation.damage_floats:
            ratio = df["lifetime"] / 0.6
            alpha = int(min(255, 255 * ratio))
            sx = df["x"] - camera_x
            sy = df["y"] - camera_y - int((1 - ratio) * 24)
            c = df["color"]
            color = (c[0], c[1], c[2], alpha) if len(c) == 3 else c
            txt = font.render(str(df["value"]), True, color[:3])
            txt.set_alpha(alpha)
            screen.blit(txt, (sx - txt.get_width() // 2, sy))


    def _render_time_stop_overlay(self):
        """时停 B&W 去色层 + 中央大字倒计时。"""
        eng = self.engine
        screen = eng.screen
        sw, sh = screen.get_width(), screen.get_height()
        overlay = pygame.Surface((sw, sh))
        overlay.set_alpha(130); overlay.fill((90, 90, 100))
        screen.blit(overlay, (0, 0))
        remain = max(0, eng._time_stop_remaining)
        title = get_font(24).render("The World · 时停", True, (255, 255, 255))
        screen.blit(title, (sw // 2 - title.get_width() // 2, 60))
        big_font = get_font(80)
        pulse = 1.0 + 0.06 * math.sin(time.time() * 6)
        big = big_font.render(f"{remain:.0f}", True, (255, 255, 255))
        scaled = pygame.transform.smoothscale(
            big, (int(big.get_width() * pulse), int(big.get_height() * pulse)))
        screen.blit(scaled, (sw // 2 - scaled.get_width() // 2,
                             sh // 2 - scaled.get_height() // 2 - 20))

    # ═══════════════════════════════════════════════════════════
    #  Boss 介绍 & 特写
    # ═══════════════════════════════════════════════════════════

    def _render_boss_intro(self):
        """Boss 介绍画面 — 粒子背景 + 属性面板。"""
        eng = self.engine
        screen = eng.screen
        screen.fill(COLOR_BLACK)
        eng._bg_particles.draw(screen)
        if not eng._boss_intro_data:
            return
        d = eng._boss_intro_data
        sw, sh = screen.get_width(), screen.get_height()
        pw, ph = 500, 380
        pr = pygame.Rect(sw // 2 - pw // 2, sh // 2 - ph // 2, pw, ph)
        draw_panel(screen, pr, title="⚠ Boss 遭遇 ⚠")
        draw_glow_text(screen, d["title"], sw // 2, pr.y + 45,
                       font_size=30, color=d["color"], glow_color=(60, 0, 0), center=True)
        f16 = get_font(16)
        stats = [f"HP: {d['max_hp']}    ATK: {d['attack']}",
                 (f"物防: {d.get('physical_defense',0)}    "
                  f"魔防: {d.get('magical_defense',0)}"),
                 f"技能: {d['skills']}"]
        for i, line in enumerate(stats):
            t = f16.render(line, True, (200, 200, 200))
            screen.blit(t, (sw // 2 - t.get_width() // 2, pr.y + 110 + i * 28))
        f18 = get_font(18)
        for i, line in enumerate(d["lore"].split('\n')):
            t = f18.render(line, True, (160, 160, 180))
            screen.blit(t, (sw // 2 - t.get_width() // 2, pr.y + 210 + i * 26))
        pulse = 0.8 + 0.2 * math.sin(eng._title_anim * 4)
        hint = get_font(20).render("按 Enter 进入战斗...", True, DARK_RED)
        screen.blit(hint, (sw // 2 - hint.get_width() // 2, sh - 60))
        pygame.display.flip()

    def _on_boss_intro_keydown(self, key: int):
        """Boss 介绍画面 Enter → 生成 Boss + 切换到特写。"""
        eng = self.engine
        if key == pygame.K_RETURN and eng._boss_intro_data:
            self._spawn_boss_from_intro()
            eng._boss_cinematic_timer = 1.0
            self._state = "boss_cinematic"

    # ═══════════════════════════════════════════════════════════
    #  G6.4: Biome Event Panel
    # ═══════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════
    #  G6.5: Encounter Framework (unified NPC/event/trade)
    # ═══════════════════════════════════════════════════════════

    def _try_trigger_encounter(self):
        """G6.5: pick encounter (prioritizes encounters.json, falls back to biome_events.json)."""
        from src.game.biome import get_biome_for_floor
        biome = get_biome_for_floor(self.engine.current_floor)
        if not biome: return
        # Prioritize new encounter framework
        from src.game.encounter import pick_encounter_for_biome
        enc = pick_encounter_for_biome(biome.id)
        if enc:
            self._encounter_def = enc
            self._encounter_node = enc.dialogue[0].id if enc.dialogue else "end"
            self._encounter_result = []
            self._state = "encounter"
            return
        # Fallback to legacy biome_events
        from src.game.biome_event import pick_event_for_biome
        ev = pick_event_for_biome(biome.id)
        if not ev: return
        self._pending_event = ev
        self._state = "encounter"

    def _on_encounter_keydown(self, key: int):
        """G6.5: 1-5 to pick choice, advances dialogue tree."""
        # Legacy biome_event path
        ev = self._pending_event
        if ev:
            if key in (pygame.K_1, pygame.K_2):
                idx = 0 if key == pygame.K_1 else 1
                from src.game.biome_event import execute_effect, execute_risk
                eng = self.engine
                choice = ev.choices[idx]
                eff_msg = execute_effect(choice.effect, eng.player, eng.monsters, eng.game_map)
                risk_msg = execute_risk(choice.risk, eng.player, eng.monsters, eng.game_map)
                self.presentation.show_message(choice.message, 2.5)
                self._state = "playing"
                self._pending_event = None
            return
        # G6.5 encounter path
        enc = self._encounter_def
        if not enc: return
        node = self._get_encounter_node()
        if not node or not node.choices: return
        idx = -1
        if key == pygame.K_1: idx = 0
        elif key == pygame.K_2: idx = 1
        elif key == pygame.K_3: idx = 2
        elif key == pygame.K_4: idx = 3
        elif key == pygame.K_5: idx = 4
        if idx < 0 or idx >= len(node.choices):
            return
        choice = node.choices[idx]
        self._advance_encounter(choice)

    def _advance_encounter(self, choice):
        """G6.5: apply choice effects, move to next dialogue node."""
        enc = self._encounter_def
        if not enc: return
        node = self._get_encounter_node()
        eng = self.engine
        from src.game.encounter import execute_effect, execute_risk, execute_trade
        results = []
        # Execute effect
        if choice.effect == "trade" and node and node.type == "trade":
            results.append(execute_trade(node.trade_items, node.trade_cost, eng.player))
        elif choice.effect not in ("", "none"):
            results.append(execute_effect(choice.effect, eng.player, eng.monsters, eng.game_map))
        # Execute risk
        if choice.risk not in ("", "none"):
            results.append(execute_risk(choice.risk, eng.player, eng.monsters, eng.game_map))
        self._encounter_result = [r for r in results if r]
        if results:
            self.presentation.show_message(" ".join(results), 2.0)
        # Advance or end
        if choice.next == "end":
            self._state = "playing"
            self._encounter_def = None
            self._encounter_node = ""
        else:
            self._encounter_node = choice.next

    def _get_encounter_node(self):
        """G6.5: resolve current dialogue node from encounter def."""
        enc = self._encounter_def
        if not enc: return None
        for n in enc.dialogue:
            if n.id == self._encounter_node:
                return n
        return None

    def _render_encounter_panel(self):
        """G6.5: draw encounter/dialogue panel (supports npc + legacy event)."""
        # Legacy biome_event path
        ev = self._pending_event
        if ev:
            self._render_event_choice_panel(ev.narrative, ev.choices)
            return
        # G6.5 encounter path
        enc = self._encounter_def
        if not enc: return
        node = self._get_encounter_node()
        if not node: return
        is_trade = node.type == "trade"
        title = enc.name if enc.name else ""
        self._render_encounter_dialogue(enc.narrative, node.text, node.choices,
                                        title, is_trade, node.trade_cost if is_trade else "")

    def _render_event_choice_panel(self, narrative, choices):
        """Legacy: single-round 2-choice panel (from biome_event)."""
        screen = self.engine.screen; sw, sh = screen.get_width(), screen.get_height()
        dark = pygame.Surface((sw, sh)); dark.set_alpha(170); dark.fill((5, 5, 15))
        screen.blit(dark, (0, 0))
        pw, ph = 500, 280; px, py = sw // 2 - pw // 2, sh // 2 - ph // 2
        draw_panel(screen, px, py, pw, ph)
        font = get_font(18)
        lines = self._wrap_text(narrative, font, pw - 40)
        for i, line in enumerate(lines[:3]):
            t = font.render(line, True, COLOR_WHITE)
            screen.blit(t, (px + 20, py + 20 + i * 24))
        for j, c in enumerate(choices):
            y = py + 120 + j * 65
            key = get_font(22).render(f"[{j+1}]", True, GOLD)
            screen.blit(key, (px + 20, y))
            lbl = get_font(18).render(c.text, True, COLOR_WHITE)
            screen.blit(lbl, (px + 55, y))
        hint = get_font(14).render("按 1-2 选择", True, (140, 140, 160))
        screen.blit(hint, (sw // 2 - hint.get_width() // 2, py + ph - 28))
        pygame.display.flip()

    def _render_encounter_dialogue(self, narrative, text, choices, title, is_trade, cost):
        """G6.5: render multi-round dialogue / trade panel."""
        screen = self.engine.screen; sw, sh = screen.get_width(), screen.get_height()
        dark = pygame.Surface((sw, sh)); dark.set_alpha(170); dark.fill((5, 5, 15))
        screen.blit(dark, (0, 0))
        pw, ph = 540, 320; px, py = sw // 2 - pw // 2, sh // 2 - ph // 2
        draw_panel(screen, px, py, pw, ph)
        font = get_font(18)
        y = py + 20
        # Title
        if title:
            t = get_font(22).render(title, True, GOLD)
            screen.blit(t, (px + 20, y)); y += 28
        # Narrative (first visit only)
        if narrative:
            for line in self._wrap_text(narrative, font, pw - 40)[:2]:
                t = font.render(line, True, (200, 200, 210))
                screen.blit(t, (px + 20, y)); y += 22
            y += 6
        # Dialogue text
        if text:
            for line in self._wrap_text(text, font, pw - 40)[:4]:
                t = font.render(line, True, COLOR_WHITE)
                screen.blit(t, (px + 20, y)); y += 24
            y += 10
        # Trade cost hint
        if is_trade and cost:
            t = get_font(16).render(f"代价: {cost}", True, COLOR_RED)
            screen.blit(t, (px + 20, y)); y += 24
        # Choices
        for j, c in enumerate(choices):
            if j >= 5: break
            key = get_font(22).render(f"[{j+1}]", True, GOLD)
            screen.blit(key, (px + 20, y + j * 26))
            lbl = get_font(18).render(c.text, True, COLOR_WHITE)
            screen.blit(lbl, (px + 55, y + j * 26))
        hint = get_font(14).render("按 1-2 继续对话", True, (140, 140, 160))
        screen.blit(hint, (sw // 2 - hint.get_width() // 2, py + ph - 28))
        pygame.display.flip()

    @staticmethod
    def _wrap_text(text: str, font, max_width: int) -> list[str]:
        lines, cur = [], ""
        for ch in text:
            test = cur + ch
            if font.size(test)[0] > max_width and cur:
                lines.append(cur); cur = ch
            else: cur = test
        if cur: lines.append(cur)
        return lines if lines else [text]

    def _spawn_boss_from_intro(self):
        """根据当前楼层生成 Boss 实体。"""
        eng = self.engine
        room_tx = eng.stairs_pos[0] if eng.stairs_pos else MAP_WIDTH // 2
        room_ty = eng.stairs_pos[1] if eng.stairs_pos else MAP_HEIGHT // 2
        from src.game.biome import get_biome_for_floor
        biome = get_biome_for_floor(eng.current_floor)
        boss_id = biome.boss_id if biome else None
        boss = spawn_boss(room_tx, room_ty, eng.current_floor, boss_id=boss_id)
        eng.monsters.append(boss)
        self.boss_sys.init_on_spawn(boss, eng.current_floor)
        # G5.8.7: boss landing dispatch
        px, py = eng.game_map.tile_to_pixel(room_tx, room_ty)
        self.presentation.trigger_boss_landing()
        ev = PresentationEvent(kind="boss_landing", cx=px, cy=py)
        eng._attack_effects += self.presentation.dispatch(ev)

    def _update_boss_cinematic(self, delta_time: float):
        """Boss 1秒特写倒计时 → 切换到 playing。"""
        eng = self.engine
        eng._boss_cinematic_timer -= delta_time
        if eng._boss_cinematic_timer <= 0:
            eng._boss_cinematic_timer = 0
            eng._boss_intro_data = None
            self._state = "playing"

    def _render_boss_cinematic_overlay(self):
        """Boss 特写 — 全屏暗色遮罩 + 脉冲警告文字。"""
        eng = self.engine
        screen = eng.screen
        sw, sh = screen.get_width(), screen.get_height()
        dark = pygame.Surface((sw, sh))
        dark.set_alpha(160); dark.fill((0, 0, 0))
        screen.blit(dark, (0, 0))
        pulse = 1.0 + 0.08 * math.sin(time.time() * 8)
        big = get_font(48)
        txt = big.render("BOSS 来了！", True, COLOR_RED)
        s2 = (int(txt.get_width() * pulse), int(txt.get_height() * pulse))
        scaled = pygame.transform.smoothscale(txt, s2)
        screen.blit(scaled, (sw // 2 - s2[0] // 2, sh // 2 - s2[1] // 2))

    # ═══════════════════════════════════════════════════════════
    #  辅助工具
    # ═══════════════════════════════════════════════════════════

    def _draw_text_center(self, text: str, size: int, color: tuple,
                          offset_y: int = 0):
        """在窗口中央绘制单行文本。"""
        screen = self.engine.screen
        font = get_font(size)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(screen.get_width() // 2,
                                      screen.get_height() // 2 + offset_y))
        screen.blit(surf, rect)
