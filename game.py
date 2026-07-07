"""
──────────────────────────────────────────
《Roguelike 肉鸽游戏》— 游戏引擎
──────────────────────────────────────────

职责：
  - 维护游戏主循环（事件 → 更新 → 渲染）。
  - 管理游戏状态机，调度当前状态的逻辑。
  - 不直接处理渲染细节 —— 委托给 ui/ 模块。
"""

import pygame
from config import (FPS, COLOR_BLACK, COLOR_WHITE, COLOR_RED,
                     COLOR_GREEN, COLOR_YELLOW, COLOR_GRAY, CJK_FONT_PATH,
                     WINDOW_WIDTH, WINDOW_HEIGHT,
                     PLAYER_SPEED, TILE_SIZE, PLAYER_MAX_HP,
                     PLAYER_ATTACK, PLAYER_PHYSICAL_DEFENSE,
                     PLAYER_MAGICAL_DEFENSE, PLAYER_ATTACK_RANGE,
                     MAP_WIDTH, MAP_HEIGHT, INVENTORY_MAX_SIZE,
                     LOOT_DROP_CHANCE, PICKUP_RANGE,
                     MAX_FLOORS, BOSS_FLOORS,
                     XP_PER_KILL_BASE, XP_PER_KILL_BOSS,
                     FLOOR_MONSTER_HP_MULT, FLOOR_MONSTER_ATK_MULT,
                     FLOOR_MONSTER_COUNT)

# 加载中文字体（全局单例）
_cjk_font_cache = {}


def _get_font(size: int) -> pygame.font.Font:
    """获取指定大小的中文字体（带缓存）。

    参数：
        size: 字体大小。

    返回：
        pygame.font.Font 实例。
    """
    if size not in _cjk_font_cache:
        if CJK_FONT_PATH:
            _cjk_font_cache[size] = pygame.font.Font(CJK_FONT_PATH, size)
        else:
            _cjk_font_cache[size] = pygame.font.Font(None, size)
    return _cjk_font_cache[size]
from src.entities.player import Player
from src.entities.monster import Monster, spawn_monster
from src.entities.item import (DroppedItem, Item, EquipmentItem,
                                ConsumableItem, Rarity, generate_random_item,
                                generate_charm_for_skill)
from src.entities.skill import (random_skill, random_active_skill, SkillManager,
                                 ActiveSkill, PassiveSkill,
                                 get_learned_skill_names)
from src.entities.components import AttackType
from src.entities.boss import spawn_boss, get_boss_info
from src.tutorial import (TutorialGuide, TutorialStage,
                           build_tutorial_map, create_tutorial_dummy,
                           create_tutorial_items, give_tutorial_skill)
from src.systems.combat_system import find_attack_target
from src.world.game_map import GameMap
from src.world.dungeon_generator import DungeonGenerator
from saves.save_manager import save_game, load_save, delete_save, save_exists
from src.ui_helpers import (draw_panel, draw_key_hint, draw_glow_text,
                             draw_progress_bar, ParticleSystem,
                             PANEL_BG, GOLD, DARK_RED, CYBER_BLUE)
from src.fx_engine import (player_attack_fx, slash_skill_fx, fireball_fx,
                            heal_fx, monsters_attack_fx, boss_cone_fx,
                            boss_circle_fx, boss_summon_fx, time_stop_fx,
                            hit_flash_fx, draw_fx_on_screen)
from src.sfx_engine import play_sfx
from src.bgm_engine import (play_title_bgm, play_select_bgm,
                             play_dungeon_bgm, play_boss_bgm, stop_bgm,
                             init_bgm)


class GameState:
    TITLE = "title"
    PLAYING = "playing"
    BOSS_INTRO = "boss_intro"
    BOSS_CINEMATIC = "boss_cinematic"
    FLOOR_SELECT = "floor_select"
    TUTORIAL = "tutorial"
    DEATH = "death"
    VICTORY = "victory"


class GameEngine:
    """游戏引擎 —— 持有主循环，调度各状态的 enter / update / render。

    设计原则：
      - 引擎不关心某个状态具体做什么，只负责调用对应方法。
      - 状态的行为通过 `_update_<state>` / `_render_<state>` 约定
        来分发，避免 if-elif 地狱。
    """

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen = screen
        self.clock = clock
        self.is_running = True
        self.state = GameState.TITLE
        self._state_dispatch = self._build_dispatch_table()
        self.player: Player | None = None
        self.game_map: GameMap | None = None
        self.monsters: list[Monster] = []
        self._game_time = 0.0
        self.ground_items: list[DroppedItem] = []
        self.inventory_open = False
        self.inventory_cursor = 0
        self.tutorial: TutorialGuide | None = None
        self._gave_tutorial_skill = False
        self._attack_effects: list[dict] = []
        self.current_floor = 1
        self.stairs_pos: tuple[int, int] | None = None
        self.stairs_active = False
        self._time_stop_remaining = 0.0
        self._pending_damage: list[tuple] = []
        self._boss_cinematic_timer = 0.0
        self._boss_intro_data: dict | None = None
        self._max_unlocked_floor = 1
        self._floor_select_cursor = 0
        self._bg_particles = ParticleSystem(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._title_anim = 0.0
        self._bgm_stopped_for_title = False

    # ---- 主循环 ----

    def run(self):
        """游戏主循环 —— 每帧处理事件 → 更新 → 渲染。"""
        while self.is_running:
            delta_time = self.clock.tick(FPS) / 1000.0    # 毫秒 → 秒
            self._handle_global_events()
            self._update(delta_time)
            self._render()
        # 循环结束后关闭窗口
        pygame.display.quit()

    # ---- 事件处理 ----

    def _handle_global_events(self):
        """处理全局事件 — F11 全屏切换在任何状态都生效。"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self._toggle_fullscreen()
                    continue
                self._dispatch_keydown(event.key)

    def _toggle_fullscreen(self):
        """切换窗口/全屏模式。"""
        is_full = bool(pygame.display.get_surface().get_flags() & pygame.FULLSCREEN)
        flags = pygame.SCALED
        if not is_full:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode(
            (WINDOW_WIDTH, WINDOW_HEIGHT), flags)
        # 重建粒子系统因为屏幕尺寸变了
        self._bg_particles = ParticleSystem(
            self.screen.get_width(), self.screen.get_height())

    def _dispatch_keydown(self, key: int):
        """将按键事件转发给当前状态对应的处理方法。

        参数：
            key: pygame 按键常量（如 pygame.K_RETURN）。
        """
        handler = self._state_dispatch.get(self.state, {}).get("on_keydown")
        if handler:
            handler(key)

    # ---- 更新 & 渲染分发 ----

    def _update(self, delta_time: float):
        """调用当前状态的更新逻辑。

        参数：
            delta_time: 上一帧耗时（秒），用于时间相关计算。
        """
        if self.state == GameState.PLAYING:
            self._game_time += delta_time
            self._update_playing(delta_time)
            # 时停倒计时
            if self._time_stop_remaining > 0:
                self._time_stop_remaining -= delta_time
                if self._time_stop_remaining <= 0:
                    self._time_stop_remaining = 0
                    self._apply_pending_damage()
            if self.player and not self.player.combat.is_alive:
                self.state = GameState.DEATH
            if not self.stairs_active and self._all_monsters_dead():
                self._activate_stairs()
        elif self.state == GameState.BOSS_CINEMATIC:
            self._update_boss_cinematic(delta_time)
        elif self.state == GameState.TUTORIAL:
            self._game_time += delta_time
            self._update_tutorial(delta_time)
        # 攻击特效 / 背景粒子衰减
        for fx in self._attack_effects:
            fx["elapsed"] += delta_time
        self._attack_effects = [f for f in self._attack_effects
                                if f["elapsed"] < f["duration"]]
        self._bg_particles.update(delta_time)
        self._title_anim += delta_time

    def _render(self):
        """调用当前状态的渲染逻辑。"""
        if self.state == GameState.TITLE:
            self._render_title()
        elif self.state == GameState.PLAYING:
            self._render_playing()
        elif self.state == GameState.FLOOR_SELECT:
            self._render_floor_select()
        elif self.state == GameState.BOSS_INTRO:
            self._render_boss_intro()
        elif self.state == GameState.BOSS_CINEMATIC:
            self._render_playing()
            self._render_boss_cinematic_overlay()
        elif self.state == GameState.TUTORIAL:
            self._render_tutorial()
        elif self.state == GameState.VICTORY:
            self._render_victory()
        elif self.state == GameState.DEATH:
            self._render_death()

    # =======================================================
    #  各状态的渲染 & 逻辑
    # =======================================================

    # ---------- 标题画面 ----------

    def _render_title(self):
        """标题画面 — 播放标题 BGM。"""
        if self.state == GameState.TITLE and not self._bgm_stopped_for_title:
            play_title_bgm()
            self._bgm_stopped_for_title = True
        self.screen.fill(COLOR_BLACK)
        self._bg_particles.draw(self.screen)
        sw, sh = self.screen.get_width(), self.screen.get_height()
        import math
        pulse = 1.0 + 0.02 * math.sin(self._title_anim * 2)
        draw_glow_text(self.screen, "Roguelike 肉鸽游戏", sw // 2, 100,
                       font_size=int(52 * pulse), color=(255, 255, 220),
                       glow_color=(120, 80, 40), center=True)
        draw_glow_text(self.screen, "— 地牢深处 —", sw // 2, 150,
                       font_size=18, color=(180, 180, 180), center=True)
        pw, ph = 340, 290
        pr = pygame.Rect(sw // 2 - pw // 2, 190, pw, ph)
        draw_panel(self.screen, pr, title="选 单")
        has_save = save_exists()
        self._draw_title_menu(pr, has_save)
        cr = _get_font(12).render(
            "重庆大学大数据与软件学院 · 程序设计实训", True, (80, 80, 80))
        self.screen.blit(cr, (sw // 2 - cr.get_width() // 2, sh - 50))
        dev = _get_font(14).render(
            "开发者：ruozhiDIO", True, (140, 140, 160))
        self.screen.blit(dev, (sw // 2 - dev.get_width() // 2, sh - 30))
        pygame.display.flip()

    def _draw_title_menu(self, pr: pygame.Rect, has_save: bool):
        """绘制标题菜单项。"""
        save_txt = (f"● 存档已存在（已解锁第{load_save()['max_unlocked_floor']}层）"
                    if has_save else "○ 暂无存档")
        ss = _get_font(14).render(save_txt, True, (160, 160, 160))
        self.screen.blit(ss, (pr.x + (pr.width - ss.get_width()) // 2,
                               pr.y + 30))
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
            draw_key_hint(self.screen, key, desc, pr.x + 60, y0 + i * 36, color)

    def _on_title_keydown(self, key: int):
        """标题画面按键。"""
        if key == pygame.K_n:
            self._new_game()
            self.state = GameState.PLAYING
        elif key == pygame.K_c:
            if not save_exists():
                return
            saved = load_save()
            if saved:
                self._load_saved_game(saved)
        elif key == pygame.K_f:
            saved = load_save()
            if saved:
                self._max_unlocked_floor = saved["max_unlocked_floor"]
            self._floor_select_cursor = 0
            self.state = GameState.FLOOR_SELECT
        elif key == pygame.K_t:
            self._enter_tutorial()
            self.state = GameState.TUTORIAL
        elif key == pygame.K_ESCAPE:
            self.is_running = False

    def _load_saved_game(self, saved: dict):
        """从存档恢复游戏 —— 若在Boss关且未击败则触发介绍画面。"""
        self.player = saved["player"]
        floor = saved["current_floor"]
        self._max_unlocked_floor = saved["max_unlocked_floor"]
        # 未击破的Boss关：需要重新生成Boss → 走介绍流程
        if floor in BOSS_FLOORS and self._max_unlocked_floor <= floor:
            self._enter_floor(floor)   # 设 state = BOSS_INTRO
        else:
            self._enter_floor(floor)
            self.state = GameState.PLAYING

    # ---------- 进行中画面 ----------

    def _render_playing(self):
        """渲染游戏画面 —— 地图 → 怪物 → 掉落物 → 玩家 → HUD → 背包面板。"""
        self.screen.fill(COLOR_BLACK)
        camera_x, camera_y = self._get_camera_offset()
        # 1. 地图
        if self.game_map:
            self.game_map.render(self.screen, camera_x, camera_y)
        # 2. 怪物
        for monster in self.monsters:
            monster.render(self.screen, camera_x, camera_y)
            self._draw_monster_buffs(monster, camera_x, camera_y)
        # 3. 地面掉落物
        self._render_ground_items(camera_x, camera_y)
        # 4. 玩家
        if self.player:
            self.player.render(self.screen, camera_x, camera_y)
        # 5. 攻击范围闪烁
        self._render_attack_effects(camera_x, camera_y)
        # 6. HUD
        self._render_hud()
        if not self.inventory_open:
            self._draw_text_center(
            "WASD移动 | 空格攻击 | 1-4技能 | E拾取 | I背包 | >下楼 | F11全屏 | Esc返回",
                size=13, color=COLOR_WHITE,
                offset_y=self.screen.get_height() // 2 - 25,
            )
        # 6. 背包面板
        if self.inventory_open:
            self._render_inventory_panel()
        # 7. 时停 B&W 叠加层
        if self._time_stop_remaining > 0:
            self._render_time_stop_overlay()
        pygame.display.flip()

    def _render_time_stop_overlay(self):
        """时停期间的 B&W 去色层 + 中央大字倒计时 + 顶部标题。"""
        sw = self.screen.get_width()
        sh = self.screen.get_height()
        # 灰色半透明层
        overlay = pygame.Surface((sw, sh))
        overlay.set_alpha(130)
        overlay.fill((90, 90, 100))
        self.screen.blit(overlay, (0, 0))
        remain = max(0, self._time_stop_remaining)
        # 顶部标题
        title = _get_font(24).render(
            "The World · 时停", True, (255, 255, 255))
        self.screen.blit(title, (sw // 2 - title.get_width() // 2, 60))
        # 中央大字倒计时
        big_font = _get_font(80)
        # 脉冲缩放效果
        import math, time
        pulse = 1.0 + 0.06 * math.sin(time.time() * 6)
        big = big_font.render(f"{remain:.0f}", True, (255, 255, 255))
        scaled_w = int(big.get_width() * pulse)
        scaled_h = int(big.get_height() * pulse)
        scaled = pygame.transform.smoothscale(big, (scaled_w, scaled_h))
        cx = sw // 2 - scaled_w // 2
        cy = sh // 2 - scaled_h // 2 - 20
        self.screen.blit(scaled, (cx, cy))

    def _new_game(self):
        """开始新游戏 —— 清空存档，进入第 1 层。"""
        delete_save()
        self._max_unlocked_floor = 1
        self._new_game_empty()
        starter = random_active_skill()
        self.player.skills.learn(starter)
        self.player.skills.apply_all_passives(self.player)
        self._enter_floor(1)

    def _enter_floor(self, floor_num: int):
        """进入指定关卡 —— Boss 关触发介绍画面。

        参数：
            floor_num: 关卡号 (1~15)。
        """
        self.current_floor = floor_num
        self._game_time = 0.0
        self.ground_items = []
        self.inventory_open = False
        self.inventory_cursor = 0
        self.stairs_active = False
        self._attack_effects = []
        self._time_stop_remaining = 0.0
        self._pending_damage = []
        generator = DungeonGenerator(MAP_WIDTH, MAP_HEIGHT, TILE_SIZE)
        self.game_map = generator.generate()
        room_centers = generator.get_room_centers()
        self._place_player_in_room(room_centers)
        other = room_centers[1:] if len(room_centers) > 1 else []
        idx = min(floor_num - 1, 14)
        n = FLOOR_MONSTER_COUNT[idx]
        is_boss = floor_num in BOSS_FLOORS
        if not is_boss:
            self.monsters = self._spawn_monsters_scaled(other, n, floor_num)
        else:
            self.monsters = []
        self.stairs_pos = (room_centers[-1] if room_centers
                           else (MAP_WIDTH // 2, MAP_HEIGHT // 2))
        self.player.combat.current_hp = self.player.combat.max_hp
        self.player.reset_attack_timers()
        self._start_floor_bgm(is_boss, floor_num)

    def _start_floor_bgm(self, is_boss: bool, floor_num: int):
        """设置关卡 BGM + 状态。"""
        if is_boss:
            self._boss_intro_data = get_boss_info(floor_num)
            self.state = GameState.BOSS_INTRO
            play_boss_bgm()
        else:
            self.state = GameState.PLAYING
            play_dungeon_bgm()
        self._bgm_stopped_for_title = False

    def _place_player_in_room(self, room_centers: list):
        """将玩家摆放在第一个房间的中心。

        参数：
            room_centers: 房间中心瓦片坐标列表。
        """
        tx, ty = room_centers[0] if room_centers else (MAP_WIDTH // 2, MAP_HEIGHT // 2)
        px, py = self.game_map.tile_to_pixel(tx, ty)
        self.player.entity.position = pygame.Vector2(px, py)
        self.player.entity.sync_rect()

    def _update_playing(self, delta_time: float):
        """游戏进行中的帧更新 —— 背包打开时暂停移动和怪物AI。

        参数：
            delta_time: 上一帧耗时（秒）。
        """
        keys = pygame.key.get_pressed()
        if self.inventory_open:
            self.player.update(delta_time)
            return
        move_x, move_y = self.player.handle_input(keys)
        entity = self.player.entity
        from src.systems.buff_system import get_effective_speed
        speed = get_effective_speed(self.player, self.player.speed)

        # ---- X 轴移动 + 碰撞 ----
        entity.position.x += move_x * speed * delta_time
        entity.sync_rect()
        if not self.game_map.is_rect_walkable(entity.rect):
            entity.position.x -= move_x * speed * delta_time
            entity.sync_rect()

        # ---- Y 轴移动 + 碰撞 ----
        entity.position.y += move_y * speed * delta_time
        entity.sync_rect()
        if not self.game_map.is_rect_walkable(entity.rect):
            entity.position.y -= move_y * speed * delta_time
            entity.sync_rect()

        # ---- 怪物行为 + 楼层检测（时停期间冻结） ----
        if self._time_stop_remaining <= 0:
            self._update_monsters(delta_time)
            self._check_floor_transition()

        self.player.update(delta_time)
        self._tick_skill_regen(delta_time)
        self._tick_buff_system(delta_time)

    def _tick_skill_regen(self, dt: float):
        """自愈 Lv3 持续回复。"""
        for sk in self.player.skills.active_skills:
            if hasattr(sk, "tick_regen"):
                sk.tick_regen(self.player, dt)

    def _tick_buff_system(self, dt: float):
        """每帧结算所有 Buff — 玩家 + 怪物。"""
        from src.systems.buff_system import tick_buffs
        tick_buffs(self.player, dt)
        for m in self.monsters:
            tick_buffs(m, dt)
        # 玩家被 DOT 毒死 → 切死亡画面
        if not self.player.combat.is_alive:
            self.state = GameState.DEATH
            return
        # 怪物被 DOT 毒死 → 走击杀流程
        dead = [m for m in self.monsters if not m.combat.is_alive]
        for m in dead:
            self._on_monster_killed(m)
        self.monsters = [m for m in self.monsters if m.combat.is_alive]

    # ---- 楼层系统 ----

    def _all_monsters_dead(self) -> bool:
        """所有怪物是否已死亡。"""
        return all(not m.combat.is_alive for m in self.monsters)

    def _activate_stairs(self):
        """激活楼梯 + 自动存档（Boss 存活时禁止）。"""
        if not self.stairs_pos or self.stairs_active:
            return
        # Boss 未死则绝不激活楼梯
        boss = self._get_boss()
        if boss and boss.combat.is_alive:
            return
        sx, sy = self.stairs_pos
        from src.world.tile import TileType
        self.game_map.set_tile(sx, sy, TileType.STAIRS_DOWN)
        self.stairs_active = True
        # 自动存档
        self._max_unlocked_floor = max(self._max_unlocked_floor,
                                       self.current_floor)
        save_game(self.player, self.current_floor,
                  self._max_unlocked_floor)

    def _check_floor_transition(self):
        """检测玩家是否站在激活的楼梯上并按下 > 键。"""
        if not self.stairs_active or not self.player or not self.stairs_pos:
            return
        keys = pygame.key.get_pressed()
        if not keys[pygame.K_PERIOD]:              # '.' 键右边的 '>'
            return
        px, py = self.game_map.pixel_to_tile(
            self.player.entity.rect.centerx,
            self.player.entity.rect.centery)
        if (px, py) != self.stairs_pos:
            return
        # 进入下一层
        next_floor = self.current_floor + 1
        if next_floor > MAX_FLOORS:
            self.state = GameState.VICTORY
        else:
            self._enter_floor(next_floor)

    def _spawn_monsters_scaled(self, room_centers: list,
                                 count: int, floor: int) -> list[Monster]:
        """生成按关卡难度缩放的怪物。

        参数：
            room_centers: 房间中心瓦片坐标列表。
            count: 怪物数量。
            floor: 当前关卡号。

        返回：
            怪物实例列表。
        """
        import random
        if not room_centers:
            return []
        hp_mult = FLOOR_MONSTER_HP_MULT[min(floor - 1, 14)]
        atk_mult = FLOOR_MONSTER_ATK_MULT[min(floor - 1, 14)]
        spawned = []
        room_index = 0
        while len(spawned) < count and room_index < 500:
            tx, ty = room_centers[room_index % len(room_centers)]
            offset_x = random.randint(-2, 2)
            offset_y = random.randint(-2, 2)
            spawn_tx = tx + offset_x
            spawn_ty = ty + offset_y
            if self.game_map.is_walkable(spawn_tx, spawn_ty):
                px, py = self.game_map.tile_to_pixel(spawn_tx, spawn_ty)
                m = spawn_monster(px, py, random.choice(["slime", "slime", "orc"]))
                # 缩放怪物属性
                m.combat.max_hp = int(m.combat.max_hp * hp_mult)
                m.combat.current_hp = m.combat.max_hp
                m.combat.attack = int(m.combat.attack * atk_mult)
                spawned.append(m)
            room_index += 1
        return spawned

    def _get_camera_offset(self) -> tuple[int, int]:
        """计算摄像机偏移 —— 让玩家保持在屏幕中央。

        返回：
            (camera_x, camera_y) 偏移像素值，用于 map 和 entity 渲染。
        """
        if not self.player:
            return 0, 0
        screen_w = self.screen.get_width()
        screen_h = self.screen.get_height()
        # 以玩家中心为目标
        cx = self.player.entity.rect.centerx - screen_w // 2
        cy = self.player.entity.rect.centery - screen_h // 2
        # 不超出地图边界
        if self.game_map:
            cx = max(0, min(cx, self.game_map.pixel_width - screen_w))
            cy = max(0, min(cy, self.game_map.pixel_height - screen_h))
        return int(cx), int(cy)

    def _on_playing_keydown(self, key: int):
        """游戏中按键处理 —— 区分普通模式和背包模式。

        参数：
            key: pygame 按键常量。
        """
        if self.inventory_open:
            self._handle_inventory_key(key)
            return
        if key == pygame.K_ESCAPE:
            # 中途退出自动存档
            if self.player and self.player.combat.is_alive:
                self._max_unlocked_floor = max(self._max_unlocked_floor,
                                               self.current_floor)
                save_game(self.player, self.current_floor,
                          self._max_unlocked_floor)
            self.state = GameState.TITLE
        elif key == pygame.K_SPACE:
            self._handle_player_attack()
        elif key == pygame.K_e:
            self._handle_pickup()
        elif key == pygame.K_i:
            self.inventory_open = True
            self.inventory_cursor = 0
        elif key == pygame.K_1:
            self._use_skill(0)
        elif key == pygame.K_2:
            self._use_skill(1)
        elif key == pygame.K_3:
            self._use_skill(2)
        elif key == pygame.K_4:
            self._use_skill(3)

    # ---- 技能 ----

    def _use_skill(self, index: int):
        """释放指定索引的主动技能。"""
        if not self.player or index >= len(self.player.skills.active_skills):
            return
        skill = self.player.skills.active_skills[index]
        if skill.name == "The World":
            self._activate_time_stop(skill, index)
            return
        if self._time_stop_remaining > 0:
            self._use_skill_in_time_stop(skill, index)
            return
        self._use_skill_normal(skill, index)

    def _activate_time_stop(self, skill, index: int):
        """激活 The World 时停。

        参数：
            skill: TheWorldSkill 实例。
            index: 技能索引。
        """
        result = self.player.skills.use_active(
            index, self.player, self.monsters,
            self.game_map, self._game_time)
        if result and "冷却中" not in result:
            duration = skill.get_stop_duration()
            self._time_stop_remaining = duration
            self._pending_damage = []
            play_sfx("timestop", 1.0)
            fx = time_stop_fx(self.player.entity.rect.centerx,
                              self.player.entity.rect.centery)
            for f in fx:
                f["duration"] = min(f["duration"], duration * 0.3)
            self._attack_effects += fx

    def _use_skill_in_time_stop(self, skill, index: int):
        """时停期间释放技能 —— 伤害暂存不立即结算。

        参数：
            skill: 技能实例。
            index: 技能索引。
        """
        pre_hp = {id(m): m.combat.current_hp for m in self.monsters}
        result = self.player.skills.use_active(
            index, self.player, self.monsters,
            self.game_map, self._game_time)
        if result and "冷却中" not in result:
            self._add_skill_effect(skill)
        if result:
            for m in self.monsters:
                if id(m) in pre_hp:
                    delta = pre_hp[id(m)] - m.combat.current_hp
                    if delta > 0:
                        self._pending_damage.append((m, delta))
                        m.combat.current_hp = pre_hp[id(m)]
                        m.combat.is_alive = True

    def _use_skill_normal(self, skill, index: int):
        """正常释放技能 + 死亡处理。

        参数：
            skill: 技能实例。
            index: 技能索引。
        """
        result = self.player.skills.use_active(
            index, self.player, self.monsters,
            self.game_map, self._game_time)
        if result and "冷却中" not in result:
            self._add_skill_effect(skill)
        if result:
            dead = [m for m in self.monsters if not m.combat.is_alive]
            for m in dead:
                self._on_monster_killed(m)
                self.monsters.remove(m)

    def _add_skill_effect(self, skill):
        """根据技能类型+等级写入视觉特效。"""
        if not self.player:
            return
        cx = self.player.entity.rect.centerx
        cy = self.player.entity.rect.centery
        lv = skill.level
        name = skill.name
        if name == "斩击":
            self._attack_effects += slash_skill_fx(
                cx, cy, self.player.direction, lv)
            play_sfx("slash")
        elif name == "神罚":
            from src.systems.combat_system import find_attack_target
            t = find_attack_target(self.player.entity.rect, self.monsters, 10.0)
            if t:
                self._attack_effects += fireball_fx(
                    cx, cy, t.entity.rect.centerx, t.entity.rect.centery, lv)
            else:
                self._attack_effects += fireball_fx(
                    cx, cy, cx + 100, cy, lv)
            play_sfx("bolt")
        elif name == "自愈":
            self._attack_effects += heal_fx(cx, cy, lv)
            play_sfx("heal")
        elif name == "The World":
            pass  # SFX 在 _activate_time_stop 中播放

    def _add_effect(self, kind: str, x: int, y: int,
                    radius: int, color: tuple, duration: float):
        """向特效列表中添加一条攻击视觉特效。

        参数：
            kind: "circle" | "cone"
            x, y: 世界坐标中心点。
            radius: 半径（像素）。
            color: RGB 颜色。
            duration: 持续时长（秒）。
        """
        self._attack_effects.append({
            "kind": kind, "x": x, "y": y,
            "radius": radius, "color": color,
            "duration": duration, "elapsed": 0.0,
        })

    def _spawn_death_particles(self, monster: Monster):
        """怪物死亡彩色粒子爆散。"""
        import random
        cx = monster.entity.rect.centerx
        cy = monster.entity.rect.centery
        c = monster.color
        n = 10 if monster.is_boss else 5
        for _ in range(n):
            dx = random.randint(-20, 20)
            dy = random.randint(-20, 20)
            self._add_effect("spark", cx + dx * 3, cy + dy * 3,
                             2 + random.randint(0, 3), c, 0.4)

    # ---- 拾取 ----

    def _handle_pickup(self):
        """拾取玩家附近最近的地面物品。"""
        if not self.player:
            return
        best = None
        best_dist = PICKUP_RANGE * TILE_SIZE
        player_rect = self.player.entity.rect
        for dropped in self.ground_items:
            px = dropped.tile_x * TILE_SIZE + TILE_SIZE // 2
            py = dropped.tile_y * TILE_SIZE + TILE_SIZE // 2
            dist = ((player_rect.centerx - px) ** 2
                    + (player_rect.centery - py) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best = dropped
        if best is None:
            return
        if self.player.inventory.add(best.item, self.player):
            self.ground_items.remove(best)
            play_sfx("pickup", 0.4)

    # =========================================================
    #  战斗
    # =========================================================

    def _handle_player_attack(self):
        """玩家普攻+击退火花FX。"""
        if not self.player or not self.player.combat.is_alive:
            return
        if not self.player.can_attack(self._game_time):
            return
        cr = self.player.entity.rect
        self._attack_effects += player_attack_fx(
            cr.centerx, cr.centery, int(PLAYER_ATTACK_RANGE * TILE_SIZE))
        play_sfx("melee")
        target = find_attack_target(
            self.player.entity.rect, self.monsters, PLAYER_ATTACK_RANGE)
        if target is None:
            return
        from src.systems.combat_system import calculate_damage
        from src.systems.buff_system import get_effective_attack
        atk_type = self.player.attack_type
        dmg = calculate_damage(
            get_effective_attack(self.player),
            target.combat.get_effective_defense(atk_type),
            atk_type)
        self.player._last_attack_time = self._game_time
        if self._time_stop_remaining > 0:
            self._pending_damage.append((target, dmg))
        else:
            target.combat.take_damage(dmg)
            play_sfx("hit")
            # 受击闪光
            self._attack_effects += hit_flash_fx(
                int(target.entity.position.x), int(target.entity.position.y),
                target.entity.size[0])
            if not target.combat.is_alive:
                self._on_monster_killed(target)
                self.monsters.remove(target)

    def _apply_pending_damage(self):
        """时停结束 —— 一次性结算所有暂存伤害。"""
        if not self._pending_damage:
            return
        for target, dmg in self._pending_damage:
            if target.combat.is_alive:
                target.combat.take_damage(dmg)
        dead = [m for m in self.monsters if not m.combat.is_alive]
        for m in dead:
            self._on_monster_killed(m)
            self.monsters.remove(m)
        self._pending_damage = []

    def _update_monsters(self, delta_time: float):
        """更新怪物行为 —— 检测玩家受伤播放音效。"""
        if not self.player or not self.player.combat.is_alive:
            return
        hp_before = self.player.combat.current_hp
        for monster in self.monsters:
            monster.update_ai(self.player, self.game_map,
                              delta_time, self._game_time,
                              self.monsters, self._attack_effects)
        if self.player.combat.current_hp < hp_before:
            play_sfx("hit")

    # =========================================================
    #  道具系统
    # =========================================================

    def _on_monster_killed(self, monster: Monster):
        """怪物死亡时处理掉落。

        Boss：高额经验 + 传说奖励。
        普通怪物：经验 + 概率掉落装备。
        技能不再随机掉落 —— 升级时自动习得。

        参数：
            monster: 被击杀的怪物实例。
        """
        import random
        # 死亡粒子
        self._spawn_death_particles(monster)
        if monster.is_boss:
            if self.player and self.player.give_xp(XP_PER_KILL_BOSS):
                play_sfx("levelup")
            self._drop_boss_reward(monster)
            return
        xp_gained = XP_PER_KILL_BASE + int(monster.combat.max_hp * 0.5)
        if self.player and self.player.give_xp(xp_gained):
            play_sfx("levelup")
        if random.random() > LOOT_DROP_CHANCE:
            return
        tile_x, tile_y = self.game_map.pixel_to_tile(
            monster.entity.position.x, monster.entity.position.y)
        item = generate_random_item()
        self.ground_items.append(DroppedItem(item, tile_x, tile_y))

    def _drop_boss_reward(self, monster: Monster):
        """Boss 死亡掉落奖励 —— 传说装备 + 技能卷轴 + 传说药水。

        参数：
            monster: 被击杀的 Boss。
        """
        tx, ty = self.game_map.pixel_to_tile(
            monster.entity.position.x, monster.entity.position.y)
        # 1. 传说武器
        weapon = EquipmentItem("魔渊之刃", Rarity.LEGENDARY,
                               "weapon", atk_bonus=18, pdef_bonus=3,
                               mdef_bonus=0)
        self.ground_items.append(DroppedItem(weapon, tx, ty))
        # 2. 传说护符（选一个已掌握技能对应的护符）
        import random
        skill_names = [type(s).__name__ for s in self.player.skills.active_skills]
        if skill_names:
            chosen = random.choice(skill_names)
            charm = generate_charm_for_skill(chosen, Rarity.LEGENDARY)
            if charm:
                self.ground_items.append(DroppedItem(charm, tx + 1, ty))
        # 3. 传说药水
        potion = ConsumableItem("神谕药剂", Rarity.LEGENDARY, "heal", 80)
        self.ground_items.append(DroppedItem(potion, tx + 2, ty))
        # 4. 技能卷轴（自动学习，去重）
        if self.player.skills.can_learn():
            names = get_learned_skill_names(self.player.skills)
            skill = random_skill(names)
            self.player.skills.learn(skill)
            self.player.skills.apply_all_passives(self.player)

    def _render_ground_items(self, camera_x: int, camera_y: int):
        """绘制掉落物（光晕+脉冲）。"""
        import math, time
        for dropped in self.ground_items:
            px = dropped.tile_x * TILE_SIZE - camera_x
            py = dropped.tile_y * TILE_SIZE - camera_y
            size = TILE_SIZE - 4
            cx, cy = px + TILE_SIZE // 2, py + TILE_SIZE // 2
            # 光晕脉冲
            pulse = 6 + int(3 * math.sin(time.time() * 5 + px * 0.1))
            glow = pygame.Rect(cx - pulse, cy - pulse, pulse * 2, pulse * 2)
            c = dropped.item.color
            pygame.draw.rect(self.screen, (c[0]//3, c[1]//3, c[2]//3), glow, 1, border_radius=3)
            # 主体
            rect = pygame.Rect(px + 2, py + 2, size, size)
            pygame.draw.rect(self.screen, c, rect, border_radius=4)
            # 高光
            hl = tuple(min(255, v + 80) for v in c[:3])
            pygame.draw.rect(self.screen, hl,
                             (px + 4, py + 3, size - 8, 5), border_radius=2)
            pygame.draw.rect(self.screen, (0, 0, 0), rect, 1, border_radius=4)
            # 字符
            font = _get_font(16)
            txt = font.render(dropped.item.tile_char, True, (255, 255, 255))
            self.screen.blit(txt, (px + 10, py + 6))

    # ---- Boss 介绍画面 ----

    def _render_boss_intro(self):
        """Boss 介绍（粒子背景）。"""
        self.screen.fill(COLOR_BLACK)
        self._bg_particles.draw(self.screen)
        if not self._boss_intro_data:
            return
        d = self._boss_intro_data
        sw, sh = self.screen.get_width(), self.screen.get_height()
        pw, ph = 500, 380
        pr = pygame.Rect(sw // 2 - pw // 2, sh // 2 - ph // 2, pw, ph)
        draw_panel(self.screen, pr, title="⚠ Boss 遭遇 ⚠")
        draw_glow_text(self.screen, d["title"], sw // 2, pr.y + 45,
                       font_size=30, color=d["color"],
                       glow_color=(60, 0, 0), center=True)
        f16 = _get_font(16)
        stats = [f"HP: {d['max_hp']}    ATK: {d['attack']}",
                 (f"物防: {d.get('physical_defense',0)}    "
                  f"魔防: {d.get('magical_defense',0)}"),
                 f"技能: {d['skills']}"]
        for i, line in enumerate(stats):
            t = f16.render(line, True, (200, 200, 200))
            self.screen.blit(t, (sw // 2 - t.get_width() // 2, pr.y + 110 + i * 28))
        f18 = _get_font(18)
        for i, line in enumerate(d["lore"].split('\n')):
            t = f18.render(line, True, (160, 160, 180))
            self.screen.blit(t, (sw // 2 - t.get_width() // 2, pr.y + 210 + i * 26))
        self._render_boss_intro_hint(sw, sh)
        pygame.display.flip()

    def _render_boss_intro_hint(self, sw: int, sh: int):
        """Boss 介绍底部闪烁提示。"""
        import math
        pulse = 0.8 + 0.2 * math.sin(self._title_anim * 4)
        hint = _get_font(20).render("按 Enter 进入战斗...", True, DARK_RED)
        self.screen.blit(hint, (sw // 2 - hint.get_width() // 2, sh - 60))

    def _on_boss_intro_keydown(self, key: int):
        """Boss 介绍画面按键 —— Enter 后生成Boss + 1秒特写。"""
        if key == pygame.K_RETURN and self._boss_intro_data:
            self._spawn_boss_from_intro()
            self._boss_cinematic_timer = 1.0
            self.state = GameState.BOSS_CINEMATIC

    def _spawn_boss_from_intro(self):
        """根据当前楼层和介绍数据生成 Boss。"""
        room_tx = self.stairs_pos[0] if self.stairs_pos else MAP_WIDTH // 2
        room_ty = (self.stairs_pos[1] if self.stairs_pos
                   else MAP_HEIGHT // 2)
        boss = spawn_boss(room_tx, room_ty, self.current_floor)
        self.monsters.append(boss)

    def _update_boss_cinematic(self, delta_time: float):
        """Boss 1秒特写倒计时。"""
        self._boss_cinematic_timer -= delta_time
        if self._boss_cinematic_timer <= 0:
            self._boss_cinematic_timer = 0
            self._boss_intro_data = None
            self.state = GameState.PLAYING

    def _render_boss_cinematic_overlay(self):
        """Boss 特写叠加层 —— 全屏暗色 + 中央提醒文字。"""
        sw, sh = self.screen.get_width(), self.screen.get_height()
        # 暗色遮罩
        dark = pygame.Surface((sw, sh))
        dark.set_alpha(160)
        dark.fill((0, 0, 0))
        self.screen.blit(dark, (0, 0))
        # 中央警告
        import math, time
        pulse = 1.0 + 0.08 * math.sin(time.time() * 8)
        big = _get_font(48)
        txt = big.render("BOSS 来了！", True, COLOR_RED)
        sw2 = int(txt.get_width() * pulse)
        sh2 = int(txt.get_height() * pulse)
        scaled = pygame.transform.smoothscale(txt, (sw2, sh2))
        self.screen.blit(scaled,
                         (sw // 2 - sw2 // 2, sh // 2 - sh2 // 2))

    # ---- 背包面板 ----

    def _render_inventory_panel(self):
        """美化背包面板。"""
        sw, sh = self.screen.get_width(), self.screen.get_height()
        dark = pygame.Surface((sw, sh)); dark.set_alpha(180); dark.fill((0, 0, 0))
        self.screen.blit(dark, (0, 0))
        inv = self.player.inventory
        pw, ph = 440, 480
        pr = pygame.Rect(sw // 2 - pw // 2, sh // 2 - ph // 2, pw, ph)
        draw_panel(self.screen, pr, title="背 包  I关闭")
        x0, y0 = pr.x + 30, pr.y + 40
        self._inv_draw_equipped(inv, x0, y0, pr)
        self._inv_draw_items(inv, x0, y0)
        tips = "↑↓选择  X装备  U使用  D丢弃  I关闭"
        tip = _get_font(16).render(tips, True, (140, 140, 140))
        self.screen.blit(tip, (pr.x + (pw - tip.get_width()) // 2, pr.bottom - 30))

    def _inv_draw_equipped(self, inv, x0: int, y0: int, pr: pygame.Rect):
        """绘制装备槽。"""
        f18 = _get_font(18)
        eq_text = "◆ 装备: "
        for slot, eq in inv.equipped.items():
            eq_text += f"【{slot}】{eq.get_description()}  " if eq else f"【{slot}】空  "
        eq = f18.render(eq_text, True, GOLD)
        self.screen.blit(eq, (x0, y0))
        pygame.draw.line(self.screen, (60, 60, 90), (x0, y0 + 28),
                         (pr.right - 30, y0 + 28), 1)

    def _inv_draw_items(self, inv, x0: int, y0: int):
        """绘制物品列表。"""
        f18 = _get_font(18)
        for idx, item in enumerate(inv.items):
            ry = y0 + 38 + idx * 30
            mk = "▶" if idx == self.inventory_cursor else " "
            t = f18.render(f"{mk} [{idx+1:>2}] {item.get_description()}", True, item.color)
            self.screen.blit(t, (x0, ry))
        if not inv.items:
            em = f18.render("背包空空如也", True, (120, 120, 120))
            self.screen.blit(em, (x0, y0 + 38))

    def _handle_inventory_key(self, key: int):
        """背包面板按键处理 —— 导航 / 装备 / 使用 / 丢弃。

        参数：
            key: pygame 按键常量。
        """
        inv = self.player.inventory
        if key == pygame.K_i or key == pygame.K_ESCAPE:
            self.inventory_open = False
        elif key == pygame.K_UP:
            self.inventory_cursor = max(0, self.inventory_cursor - 1)
        elif key == pygame.K_DOWN:
            self.inventory_cursor = min(
                max(0, len(inv.items) - 1), self.inventory_cursor + 1)
        elif key == pygame.K_x:
            inv.equip(self.inventory_cursor, self.player)
            self._clamp_cursor()
        elif key == pygame.K_u:
            inv.use(self.inventory_cursor, self.player)
            self._clamp_cursor()
        elif key == pygame.K_d:
            inv.remove(self.inventory_cursor)
            self._clamp_cursor()

    def _clamp_cursor(self):
        """修正背包光标，防止越界。"""
        count = len(self.player.inventory.items)
        if count == 0:
            self.inventory_cursor = 0
        else:
            self.inventory_cursor = min(self.inventory_cursor, count - 1)

    # =========================================================
    #  HUD
    # =========================================================

    def _render_hud(self):
        """左上角：血条 + 属性 + 等级/XP + 楼层信息。"""
        if not self.player:
            return
        combat = self.player.combat
        bar_x, bar_y = 10, 10
        bar_w, bar_h = 200, 16
        self._draw_player_hp_bar(combat, bar_x, bar_y, bar_w, bar_h)
        # 等级 & XP 条
        lvl, xp, xp_next = self.player.get_level_info()
        self._draw_xp_bar(bar_x, bar_y + bar_h + 4, bar_w, 10, xp, xp_next, lvl)
        boss = self._get_boss()
        if boss:
            self._render_boss_hp_bar(boss)
        # 楼层信息
        font = _get_font(16)
        floor_text = f"第 {self.current_floor}/{MAX_FLOORS} 层"
        floor_surf = font.render(floor_text, True, COLOR_YELLOW)
        self.screen.blit(floor_surf, (bar_x + bar_w + 10, bar_y + bar_h + 4))
        # 楼梯状态提示
        if self.stairs_active:
            stair_text = "楼梯已开启！按 > 下楼"
            stair_surf = font.render(stair_text, True, (100, 255, 100))
            self.screen.blit(stair_surf, (bar_x, bar_y + bar_h + 28))
        self._render_skill_bar(bar_x, bar_y + bar_h + 50)
        # Buff HUD
        self._draw_player_buffs()

    def _draw_player_buffs(self):
        """玩家 Buff HUD — 技能栏下方。"""
        if not self.player or not self.player.active_buffs:
            return
        from src.systems.buff_system import get_buff_display_name, format_buff_time, get_buff_hud_color
        x, y = 10, 56.0 + len(self.player.skills.active_skills) * 28.0 + 4.0
        for b in self.player.active_buffs:
            line = f"{get_buff_display_name(b.id)} x{b.stacks}  {format_buff_time(b.remaining)}"
            c = get_buff_hud_color(b.id)
            surf = _get_font(14).render(line, True, c)
            self.screen.blit(surf, (x, y))
            y += 18

    def _draw_monster_buffs(self, monster, cam_x, cam_y):
        """怪物头顶 Buff 标签。"""
        if not monster.active_buffs:
            return
        from src.systems.buff_system import get_buff_short_name, get_buff_hud_color
        label = " ".join(f"{get_buff_short_name(b.id)}x{b.stacks}" for b in monster.active_buffs)
        surf = _get_font(12).render(label, True, get_buff_hud_color(monster.active_buffs[0].id))
        px = monster.entity.rect.x - cam_x + (monster.entity.rect.w - surf.get_width()) / 2
        py = monster.entity.rect.y - cam_y - 16
        self.screen.blit(surf, (px, py))

    def _draw_xp_bar(self, x: int, y: int, w: int, h: int,
                     xp: int, xp_next: int, level: int):
        """美化经验条。"""
        ratio = min(1.0, xp / max(1, xp_next))
        draw_progress_bar(self.screen, x, y, w, h, ratio,
                          (80, 120, 255), (30, 30, 60))
        font = _get_font(13)
        txt = font.render(f"Lv{level}  XP:{xp}/{xp_next}", True, (180, 200, 255))
        self.screen.blit(txt, (x + 2, y + h + 2))

    def _draw_player_hp_bar(self, combat, x: int, y: int,
                            w: int, h: int):
        """美化玩家血条。"""
        hp_ratio = combat.current_hp / combat.max_hp
        if hp_ratio > 0.5:
            clr = (50, 200, 50)
        elif hp_ratio > 0.25:
            clr = (200, 200, 50)
        else:
            clr = (200, 50, 50)
        draw_progress_bar(self.screen, x, y, w, h, hp_ratio, clr, (40, 20, 20))
        pd = combat.get_effective_defense(AttackType.PHYSICAL)
        md = combat.get_effective_defense(AttackType.MAGICAL)
        font = _get_font(16)
        txt = font.render(
            f"HP:{combat.current_hp}/{combat.max_hp}  ATK:{combat.get_effective_attack()}"
            f"  PD:{pd} MD:{md}",
            True, (220, 220, 220))
        self.screen.blit(txt, (x + w + 10, y))

    def _get_boss(self):
        """获取当前存活且标记为 Boss 的怪物。"""
        for m in self.monsters:
            if m.is_boss and m.combat.is_alive:
                return m
        return None

    def _render_boss_hp_bar(self, boss: Monster):
        """顶部中央 Boss 血条（史诗级双线框+脉冲）。"""
        import math, time
        c = boss.combat
        bw, bh = 400, 20
        bx = (self.screen.get_width() - bw) // 2
        by = 4
        ratio = c.current_hp / c.max_hp
        # 外框
        pulse = int(220 + 25 * math.sin(time.time() * 5))
        pygame.draw.rect(self.screen, (pulse, 40, 40),
                         (bx - 2, by - 2, bw + 4, bh + 4), 2)
        # 背景
        pygame.draw.rect(self.screen, (30, 5, 5), (bx, by, bw, bh))
        # 渐变填充（红→金）
        fill_w = int(bw * ratio)
        segments = 10
        seg_w = fill_w // segments
        for i in range(segments):
            t = i / segments
            cr = int(200 - t * 60)
            cg = int(40 + t * 120)
            cb = int(30 + t * 20)
            sx = bx + i * seg_w
            sw = seg_w + (fill_w - (i + 1) * seg_w if i == segments - 1 else 0)
            pygame.draw.rect(self.screen, (cr, cg, cb), (sx, by, sw or 1, bh))
        # 高光
        pygame.draw.rect(self.screen, (255, 150, 80, 100),
                         (bx, by, fill_w, bh // 3))
        # 文字
        f = _get_font(18)
        txt = f.render(f"⚔ {boss.name}  HP:{c.current_hp}/{c.max_hp}", True, (255, 220, 100))
        self.screen.blit(txt, (bx + (bw - txt.get_width()) // 2, by + bh + 3))

    def _render_skill_bar(self, start_x: int, start_y: int):
        """美化技能栏。"""
        active = self.player.skills.active_skills
        if not active:
            return
        f = _get_font(14)
        bw, bh = 90, 10
        x, y = start_x, start_y
        for i, sk in enumerate(active):
            ry = y + i * (bh + 20)
            ready = sk.can_use(self._game_time)
            # 编号方框
            num_bg = (50, 160, 50) if ready else (60, 60, 60)
            num_rect = pygame.Rect(x, ry, 22, 18)
            pygame.draw.rect(self.screen, num_bg, num_rect, border_radius=3)
            ns = f.render(str(i + 1), True, (255, 255, 255))
            self.screen.blit(ns, (x + 7, ry + 1))
            # 技能名 + 等级效果
            bonus = (sk.get_level_bonus_text() if hasattr(sk, "get_level_bonus_text")
                     else f"Lv{sk.level}")
            label = f.render(f"{sk.name} {bonus}", True,
                             (180, 220, 255) if ready else (100, 100, 100))
            self.screen.blit(label, (x + 26, ry + 2))
            # 冷却条
            ratio = 1.0 - sk.remaining_cooldown(self._game_time) / sk.cooldown
            draw_progress_bar(self.screen, x + 26, ry + 16, bw, bh, ratio,
                              (60, 180, 255) if ready else (70, 70, 70),
                              (30, 30, 45))

    def _render_attack_effects(self, camera_x: int, camera_y: int):
        """绘制所有活跃攻击特效 —— 委托给 fx_engine。"""
        for fx in self._attack_effects:
            draw_fx_on_screen(self.screen, fx, camera_x, camera_y)

    def _draw_fx_circle(self, cx: int, cy: int, radius: int,
                        color: tuple):
        """在屏幕上绘制透明的攻击范围圆环。

        参数：
            cx, cy: 屏幕坐标。
            radius: 半径。
            color: (r, g, b, a) 含透明度。
        """
        diameter = radius * 2 + 6
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(surface, color,
                           (radius + 3, radius + 3), radius, 3)
        self.screen.blit(surface, (cx - radius - 3, cy - radius - 3))

    def _draw_fx_cone(self, cx: int, cy: int, radius: int,
                      color: tuple):
        """绘制锥形攻击矩形 —— 根据玩家朝向在身前画半透明区域。

        参数：
            cx, cy: 屏幕坐标（玩家中心）。
            radius: 半边尺寸。
            color: (r, g, b, a) 含透明度。
        """
        if not self.player:
            return
        from src.entities.player import Direction
        d = self.player.direction
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        rect = pygame.Rect(0, 0, radius * 2, radius * 2)
        pygame.draw.rect(surface, color, rect)
        pygame.draw.rect(surface, (color[0], color[1], color[2], 200), rect, 2)
        # 根据朝向偏移——放在玩家前方
        if d == Direction.UP:
            offset = (cx - radius, cy - radius * 2)
        elif d == Direction.DOWN:
            offset = (cx - radius, cy)
        elif d == Direction.LEFT:
            offset = (cx - radius * 2, cy - radius)
        else:  # RIGHT
            offset = (cx, cy - radius)
        self.screen.blit(surface, offset)

    # =========================================================
    #  教程模式
    # =========================================================

    def _enter_tutorial(self):
        """进入教程模式。"""
        stop_bgm()
        self._bgm_stopped_for_title = True
        self._game_time = 0.0
        self.ground_items = []
        self.inventory_open = False
        self.inventory_cursor = 0
        self._gave_tutorial_skill = False
        self.tutorial = TutorialGuide()
        # 教程小地图
        self.game_map = build_tutorial_map()
        # 玩家出生在地图左侧中央
        spawn_px = 2 * TILE_SIZE
        spawn_py = 4 * TILE_SIZE
        self.player = Player(spawn_px, spawn_py, PLAYER_SPEED,
                             PLAYER_MAX_HP, PLAYER_ATTACK, PLAYER_PHYSICAL_DEFENSE, PLAYER_MAGICAL_DEFENSE)
        # 木桩放在地图右侧
        self.monsters = [create_tutorial_dummy(8, 4)]
        # 道具放在木桩旁边
        self.ground_items = create_tutorial_items(6, 5)

    def _update_tutorial(self, delta_time: float):
        """教程帧更新 —— 背包/移动/技能授予/阶段检测。"""
        if not self.player:
            return
        t = self.tutorial
        if t.stage == TutorialStage.WELCOME:
            return
        keys = pygame.key.get_pressed()
        if self.inventory_open:
            self.player.update(delta_time)
            self._tutorial_check_advance()
            return
        # 移动 + 碰撞
        move_x, move_y = self.player.handle_input(keys)
        self._apply_movement_collision(move_x, move_y, delta_time)
        self.player.update(delta_time)
        if t.stage == TutorialStage.SKILL and not self._gave_tutorial_skill:
            give_tutorial_skill(self.player)
            self._gave_tutorial_skill = True
        self._tutorial_check_advance()

    def _apply_movement_collision(self, move_x: float,
                                  move_y: float, dt: float):
        """分轴移动 + 地图碰撞（教程与游戏共用）。

        参数：
            move_x, move_y: 归一化移动方向。
            dt: 帧耗时。
        """
        entity = self.player.entity
        speed = self.player.speed
        entity.position.x += move_x * speed * dt
        entity.sync_rect()
        if not self.game_map.is_rect_walkable(entity.rect):
            entity.position.x -= move_x * speed * dt
            entity.sync_rect()
        entity.position.y += move_y * speed * dt
        entity.sync_rect()
        if not self.game_map.is_rect_walkable(entity.rect):
            entity.position.y -= move_y * speed * dt
            entity.sync_rect()

    def _tutorial_check_advance(self):
        """封装教程阶段检测调用，避免重复代码。"""
        self.tutorial.check_and_advance(self.player, {
            "game_time": self._game_time,
            "inventory_open": self.inventory_open,
            "monsters": self.monsters,
            "ground_items": self.ground_items,
        })

    # =========================================================
    #  选关界面
    # =========================================================

    def _render_floor_select(self):
        """选关界面。"""
        if self.state == GameState.FLOOR_SELECT and not self._bgm_stopped_for_title:
            play_select_bgm()
            self._bgm_stopped_for_title = True
        self.screen.fill(COLOR_BLACK)
        sw = self.screen.get_width()
        self._draw_text_center("选择关卡", size=32, color=COLOR_WHITE, offset_y=-250)
        self._draw_text_center(
            "方向键选择  Enter 进入  Esc 返回",
            size=16, color=COLOR_GRAY, offset_y=-210)
        cols, cell_w, cell_h, gap = 5, 100, 70, 10
        sx = sw // 2 - (cols * (cell_w + gap)) // 2
        sy = 120
        for i in range(MAX_FLOORS):
            cx = sx + (i % cols) * (cell_w + gap)
            cy = sy + (i // cols) * (cell_h + gap)
            self._draw_floor_cell(i, cx, cy, cell_w, cell_h)
        pygame.display.flip()

    def _draw_floor_cell(self, idx: int, cx: int, cy: int,
                         w: int, h: int):
        """绘制单个选关格子。

        参数：
            idx: 楼层索引 (0~14)。
            cx, cy: 左上角像素坐标。
            w, h: 格子宽高。
        """
        unlocked = (idx + 1) <= self._max_unlocked_floor
        selected = (idx == self._floor_select_cursor)
        rect = pygame.Rect(cx, cy, w, h)
        if selected:
            clr = (60, 60, 160)
        elif unlocked:
            clr = (40, 40, 80)
        else:
            clr = (30, 30, 30)
        pygame.draw.rect(self.screen, clr, rect)
        border = (200, 200, 50) if selected else (
            (100, 180, 100) if unlocked else (80, 80, 80))
        pygame.draw.rect(self.screen, border, rect, 2)
        is_boss = (idx + 1) in BOSS_FLOORS
        fnum = _get_font(28).render(
            str(idx + 1), True, COLOR_RED if is_boss else COLOR_WHITE)
        self.screen.blit(fnum, (cx + w // 2 - fnum.get_width() // 2, cy + 8))
        if is_boss and unlocked:
            bi = get_boss_info(idx + 1)
            bn = _get_font(12).render(
                bi["name"] if bi else "???", True, COLOR_RED)
            self.screen.blit(bn, (cx + w // 2 - bn.get_width() // 2, cy + h - 20))
        elif not unlocked:
            lk = _get_font(14).render("锁", True, COLOR_GRAY)
            self.screen.blit(lk, (cx + w // 2 - lk.get_width() // 2, cy + h - 22))

    def _on_floor_select_keydown(self, key: int):
        """选关界面按键。"""
        if key == pygame.K_ESCAPE:
            self.state = GameState.TITLE
            return
        if key == pygame.K_LEFT:
            self._floor_select_cursor = max(0, self._floor_select_cursor - 1)
        elif key == pygame.K_RIGHT:
            self._floor_select_cursor = min(MAX_FLOORS - 1, self._floor_select_cursor + 1)
        elif key == pygame.K_UP:
            self._floor_select_cursor = max(0, self._floor_select_cursor - 5)
        elif key == pygame.K_DOWN:
            self._floor_select_cursor = min(MAX_FLOORS - 1, self._floor_select_cursor + 5)
        elif key == pygame.K_RETURN:
            floor = self._floor_select_cursor + 1
            if floor <= self._max_unlocked_floor:
                saved = load_save()
                if saved and saved["player"]:
                    self.player = saved["player"]
                    self.player.reset_attack_timers()
                else:
                    self._new_game_empty()
                    starter = random_active_skill()
                    self.player.skills.learn(starter)
                    self.player.skills.apply_all_passives(self.player)
                # 自动升级到对应楼层等级（最少 Lv1，最多到满技能 Lv4+）
                target = min(floor, 4)
                if self.player.level < target:
                    self.player.auto_level_to(target)
                self._enter_floor(floor)

    def _new_game_empty(self):
        """创建空白玩家（不附带技能，用于选关/新游戏）。"""
        self.player = Player(
            TILE_SIZE * 2, TILE_SIZE * 2, PLAYER_SPEED,
            PLAYER_MAX_HP, PLAYER_ATTACK,
            PLAYER_PHYSICAL_DEFENSE, PLAYER_MAGICAL_DEFENSE)

    def _render_tutorial(self):
        """渲染教程画面 —— 地图 + 木桩 + 道具 + 玩家 + 提示框。"""
        self.screen.fill(COLOR_BLACK)
        camera_x, camera_y = self._get_camera_offset()
        if self.game_map:
            self.game_map.render(self.screen, camera_x, camera_y)
        for m in self.monsters:
            m.render(self.screen, camera_x, camera_y)
        self._render_ground_items(camera_x, camera_y)
        if self.player:
            self.player.render(self.screen, camera_x, camera_y)
        self._render_attack_effects(camera_x, camera_y)
        self._render_hud()
        # 底部提示
        if self.tutorial and self.tutorial.stage != TutorialStage.WELCOME:
            self._draw_text_center(
                "WASD移动 | 空格攻击 | E拾取 | I背包 | T跳过教程",
                size=12, color=COLOR_GRAY,
                offset_y=self.screen.get_height() // 2 - 20,
            )
        if self.inventory_open:
            self._render_inventory_panel()
        # 阶段提示框
        self._render_tutorial_overlay()
        pygame.display.flip()

    def _render_tutorial_overlay(self):
        """在画面中央绘制教程提示框。"""
        if not self.tutorial:
            return
        lines = self.tutorial.get_stage_instructions()
        if not lines:
            return
        font = _get_font( 22)
        # 计算框体尺寸
        max_w = max(font.size(ln)[0] for ln in lines) + 60
        line_h = 28
        total_h = len(lines) * line_h + 40
        box_x = (self.screen.get_width() - max_w) // 2
        box_y = 80
        # 半透明背景
        overlay = pygame.Surface((max_w, total_h))
        overlay.set_alpha(200)
        overlay.fill((20, 20, 40))
        self.screen.blit(overlay, (box_x, box_y))
        # 边框
        pygame.draw.rect(self.screen, (100, 100, 180),
                         (box_x, box_y, max_w, total_h), 2)
        # 文字
        for i, line in enumerate(lines):
            txt = font.render(line, True, COLOR_WHITE)
            tx = box_x + (max_w - txt.get_width()) // 2
            ty = box_y + 20 + i * line_h
            self.screen.blit(txt, (tx, ty))

    def _on_tutorial_keydown(self, key: int):
        """教程模式按键 —— 分发到对应处理方法。"""
        if not self.tutorial:
            return
        t = self.tutorial
        if key == pygame.K_t:
            self.state = GameState.TITLE
            return
        if t.stage == TutorialStage.WELCOME:
            if key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                t.advance_stage()
            return
        if t.stage == TutorialStage.COMPLETE:
            if key == pygame.K_RETURN:
                self.state = GameState.TITLE
            return
        if self.inventory_open:
            self._handle_inventory_key(key)
            return
        self._handle_tutorial_game_key(key)

    def _handle_tutorial_game_key(self, key: int):
        """教程中游戏操作按键（非背包模式）。

        参数：
            key: pygame 按键常量。
        """
        t = self.tutorial
        if key == pygame.K_SPACE:
            self._handle_player_attack()
            self._tutorial_check_advance()
        elif key == pygame.K_e:
            self._handle_pickup()
        elif key == pygame.K_i:
            self.inventory_open = True
            self.inventory_cursor = 0
        elif key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
            self._use_skill(key - pygame.K_1)
            if t.stage == TutorialStage.SKILL:
                t.notify_skill_used()

    # =========================================================
    #  通关画面
    # =========================================================

    def _render_victory(self):
        """通关画面。"""
        if not self._bgm_stopped_for_title:
            stop_bgm()
            play_sfx("victory", 1.0)
            self._bgm_stopped_for_title = True
        self.screen.fill(COLOR_BLACK)
        self._bg_particles.draw(self.screen)
        sw, sh = self.screen.get_width(), self.screen.get_height()
        draw_glow_text(self.screen, "恭喜通关！", sw // 2, 120,
                       font_size=60, color=(50, 255, 100),
                       glow_color=(0, 80, 0), center=True)
        lvl = self.player.level if self.player else 1
        txt = f"你击败了地牢最深处的黑暗，光明重归大地  最终等级 Lv{lvl}"
        t = _get_font(18).render(txt, True, (200, 240, 200))
        self.screen.blit(t, (sw // 2 - t.get_width() // 2, 200))
        # 面板
        pw, ph = 400, 150
        pr = pygame.Rect(sw // 2 - pw // 2, 250, pw, ph)
        draw_panel(self.screen, pr, title="英雄凯旋")
        stats_text = [
            f"最终等级: Lv{lvl}",
            f"技能数: {len(self.player.skills.active_skills)}主动 "
            f"+ {len(self.player.skills.passives)}被动",
            f"装备武器: {self.player.inventory.equipped.get('weapon','无')}",
        ]
        for i, line in enumerate(stats_text):
            s = _get_font(16).render(str(line), True, (200, 200, 200))
            self.screen.blit(s, (sw // 2 - s.get_width() // 2, pr.y + 35 + i * 28))
        draw_glow_text(self.screen, "按 Enter 返回标题", sw // 2, sh - 60,
                       font_size=22, color=GOLD, center=True)
        pygame.display.flip()

    def _on_victory_keydown(self, key: int):
        if key == pygame.K_RETURN:
            self.player = None; self.monsters = []
            self.game_map = None; self.state = GameState.TITLE

    # =========================================================
    #  死亡画面
    # =========================================================

    def _render_death(self):
        if not self._bgm_stopped_for_title:
            stop_bgm()
            self._bgm_stopped_for_title = True
        self.screen.fill(COLOR_BLACK)
        self._bg_particles.draw(self.screen)
        sw, sh = self.screen.get_width(), self.screen.get_height()
        draw_glow_text(self.screen, "你 死 了", sw // 2, 130,
                       font_size=64, color=(220, 40, 40),
                       glow_color=(60, 0, 0), center=True)
        t = _get_font(18).render(
            "存档已保留，可从选关界面继续挑战", True, (220, 180, 100))
        self.screen.blit(t, (sw // 2 - t.get_width() // 2, 210))
        draw_glow_text(self.screen, "按 Enter 返回标题", sw // 2, sh - 70,
                       font_size=22, color=(200, 200, 200), center=True)
        pygame.display.flip()

    def _on_death_keydown(self, key: int):
        """死亡画面按键处理。

        参数：
            key: pygame 按键常量。
        """
        if key == pygame.K_RETURN:
            self.player = None
            self.monsters = []
            self.game_map = None
            self.state = GameState.TITLE

    # ---- 辅助工具 ----

    def _draw_text_center(self, text: str, size: int,
                          color: tuple, offset_y: int = 0):
        """在窗口中央绘制单行文本。

        参数：
            text: 要绘制的文本。
            size: 字体大小。
            color: RGB 颜色元组。
            offset_y: 垂直偏移量（负值向上）。
        """
        font = _get_font( size)
        surface = font.render(text, True, color)
        rect = surface.get_rect(center=(self.screen.get_width() // 2,
                                        self.screen.get_height() // 2 + offset_y))
        self.screen.blit(surface, rect)

    def _build_dispatch_table(self):
        return {
            GameState.TITLE: {"on_keydown": self._on_title_keydown},
            GameState.PLAYING: {"on_keydown": self._on_playing_keydown},
            GameState.FLOOR_SELECT: {"on_keydown": self._on_floor_select_keydown},
            GameState.BOSS_INTRO: {"on_keydown": self._on_boss_intro_keydown},
            GameState.TUTORIAL: {"on_keydown": self._on_tutorial_keydown},
            GameState.VICTORY: {"on_keydown": self._on_victory_keydown},
            GameState.DEATH: {"on_keydown": self._on_death_keydown},
        }
