"""
──────────────────────────────────────────
《Roguelike 肉鸽游戏》— 游戏引擎（场景树版）
──────────────────────────────────────────

职责：
  - 维护游戏主循环（事件 → 更新 → 渲染）。
  - 管理场景切换，持有共享状态。
  - 不处理任何具体游戏逻辑 —— 委托给 Scene 子类。
"""

import pygame
from config import (FPS, CJK_FONT_PATH, WINDOW_WIDTH, WINDOW_HEIGHT,
                     TILE_SIZE, PLAYER_SPEED, PLAYER_MAX_HP,
                     PLAYER_ATTACK, PLAYER_PHYSICAL_DEFENSE,
                     PLAYER_MAGICAL_DEFENSE)
from src.core.scene import Scene
from src.ui_helpers import ParticleSystem

# ── 字体缓存（模块级单例，各 Scene 共用） ──────────────────────
_cjk_font_cache: dict[int, pygame.font.Font] = {}


def get_font(size: int) -> pygame.font.Font:
    """获取指定大小的中文字体（带缓存）。"""
    if size not in _cjk_font_cache:
        if CJK_FONT_PATH:
            _cjk_font_cache[size] = pygame.font.Font(CJK_FONT_PATH, size)
        else:
            _cjk_font_cache[size] = pygame.font.Font(None, size)
    return _cjk_font_cache[size]


class GameEngine:
    """游戏引擎 —— 场景管理 + 主循环 + 共享状态持有者。

    设计原则：
      - 引擎只负责"跑起来"，场景负责"做什么"。
      - 所有场景共用的可变状态集中在这里，避免散落。
    """

    def __init__(self, screen: pygame.Surface, clock: pygame.time.Clock):
        self.screen = screen
        self.clock = clock
        self.is_running = True
        self._scene: Scene | None = None

        # ===== 共享游戏状态 =====
        self.player = None
        self.game_map = None
        self.monsters: list = []
        self._game_time = 0.0
        self.ground_items: list = []
        self.inventory_open = False
        self.inventory_cursor = 0
        self._attack_effects: list[dict] = []
        self.current_floor = 1
        self.stairs_pos: tuple | None = None
        self.stairs_active = False
        self._time_stop_remaining = 0.0
        self._pending_damage: list = []
        self._boss_cinematic_timer = 0.0
        self._boss_intro_data: dict | None = None
        self._max_unlocked_floor = 1

        # ===== 跨场景使用的 UI 状态 =====
        self._bg_particles = ParticleSystem(WINDOW_WIDTH, WINDOW_HEIGHT)
        self._title_anim = 0.0
        self._bgm_stopped_for_title = False

    # ── 场景管理 ─────────────────────────────────────────────

    def change_scene(self, new_scene: Scene):
        """切换场景 —— 先退出旧场景，再进入新场景。"""
        if self._scene:
            self._scene.exit()
        self._scene = new_scene
        new_scene.enter()

    # ── 主循环 ───────────────────────────────────────────────

    def run(self):
        """游戏主循环 —— 每帧处理事件 → 更新 → 渲染。"""
        while self.is_running:
            delta_time = self.clock.tick(FPS) / 1000.0
            self._handle_global_events()
            if self._scene:
                self._scene.update(delta_time)
            self._bg_particles.update(delta_time)
            self._title_anim += delta_time
            if self._scene:
                self._scene.render()
        pygame.display.quit()

    # ── 全局事件 ─────────────────────────────────────────────

    def _handle_global_events(self):
        """F11 全屏切换在任何场景都生效，其他事件委派给当前场景。"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.is_running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F11:
                    self._toggle_fullscreen()
                    continue
                if self._scene:
                    self._scene.on_keydown(event.key)

    def _toggle_fullscreen(self):
        """切换窗口/全屏模式。"""
        is_full = bool(pygame.display.get_surface().get_flags() & pygame.FULLSCREEN)
        flags = pygame.SCALED
        if not is_full:
            flags |= pygame.FULLSCREEN
        self.screen = pygame.display.set_mode(
            (WINDOW_WIDTH, WINDOW_HEIGHT), flags)
        self._bg_particles = ParticleSystem(
            self.screen.get_width(), self.screen.get_height())

    # ── 游戏初始化辅助（TitleScene / FloorSelectScene 共用）────

    def create_empty_player(self):
        """创建一个无技能的空白玩家。"""
        from src.entities.player import Player
        self.player = Player(
            TILE_SIZE * 2, TILE_SIZE * 2, PLAYER_SPEED,
            PLAYER_MAX_HP, PLAYER_ATTACK,
            PLAYER_PHYSICAL_DEFENSE, PLAYER_MAGICAL_DEFENSE)

    def init_new_game(self):
        """初始化共享状态：清存档 → 建玩家 → 给初始技能。"""
        from saves.save_manager import delete_save
        from src.entities.skill import random_active_skill
        delete_save()
        self._max_unlocked_floor = 1
        self.create_empty_player()
        starter = random_active_skill()
        self.player.skills.learn(starter)
        self.player.skills.apply_all_passives(self.player)

    def init_from_save(self, saved: dict):
        """从存档恢复共享状态。"""
        self.player = saved["player"]
        self._max_unlocked_floor = saved["max_unlocked_floor"]
        self.current_floor = saved["current_floor"]
