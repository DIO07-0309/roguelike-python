"""
PresentationSystemDirector — 视觉表现层统一管理 (D1-D6)

接入: FloorIntro / ChapterIntro / RoomMessage / RelicMessage
G5.8.2: BuildTheme integration — themed damage colors, active theme tracking
"""

from src.game.build_theme import BuildTheme, get_active_theme, DEFAULT_THEME


class PresentationSystemDirector:
    """视觉演出编排器。

    G5.8.2: 持有当前 BuildTheme，根据玩家构筑自动切换主题色。
    """

    def __init__(self):
        self.damage_floats: list = []
        self._active_theme: BuildTheme = DEFAULT_THEME
        self.shake_timer: float = 0.0
        self.shake_intensity: float = 0.0
        self.freeze_timer: float = 0.0
        # G5.8.3: Camera dynamic state
        self.dash_offset_x: float = 0.0
        self.dash_offset_y: float = 0.0
        self.zoom_level: float = 1.0
        self.zoom_target: float = 1.0
        self.boss_landing_timer: float = 0.0
        self.room_msg: str = ""
        self.room_msg_timer: float = 0.0
        self.boss_intro_text: str = ""
        self.boss_modifier_text: str = ""
        self.floor_intro_active: bool = False
        self.floor_intro_timer: float = 0.0
        self.floor_intro_fade: float = 0.0
        self.floor_intro_floor: int = 0
        self.chapter_intro_active: bool = False
        self.chapter_intro_timer: float = 0.0
        self.chapter_intro_ch: int = 0
        self.show_growth_debug: bool = False
        self.show_flow_debug: bool = False
        self.show_boss_behavior: bool = False
        self.show_boss_cmd: bool = False
        self.show_boss_report: bool = False
        self.combat_juice_on: bool = True

    def tick(self, dt: float):
        """逐帧更新所有视觉元素。"""
        if self.room_msg_timer > 0:
            self.room_msg_timer -= dt
            if self.room_msg_timer <= 0:
                self.room_msg_timer = 0
                self.room_msg = ""

        if self.floor_intro_active:
            self.floor_intro_timer -= dt
            self.floor_intro_fade = min(1.0, self.floor_intro_fade + dt * 2.5)
            if self.floor_intro_timer <= 0:
                self.floor_intro_active = False

        if self.chapter_intro_active:
            self.chapter_intro_timer -= dt
            if self.chapter_intro_timer <= 0:
                self.chapter_intro_active = False

        # 伤害数字衰减
        for df in self.damage_floats:
            df["lifetime"] -= dt
        self.damage_floats = [d for d in self.damage_floats if d["lifetime"] > 0]

        # 震动衰减
        if self.shake_timer > 0:
            self.shake_timer -= dt
        # G5.8.3: camera state decay
        if self.boss_landing_timer > 0:
            self.boss_landing_timer -= dt
            self.zoom_target = 1.0 + 0.15 * min(1.0, self.boss_landing_timer / 0.8)
        else:
            self.zoom_target = 1.0
        # smooth zoom
        self.zoom_level += (self.zoom_target - self.zoom_level) * min(1.0, dt * 6.0)
        # decay dash offset
        decay = min(1.0, dt * 8.0)
        self.dash_offset_x *= (1.0 - decay)
        self.dash_offset_y *= (1.0 - decay)
        if abs(self.dash_offset_x) < 0.5:
            self.dash_offset_x = 0.0
        if abs(self.dash_offset_y) < 0.5:
            self.dash_offset_y = 0.0

    def spawn_damage(self, x: float, y: float, value: int,
                     color=(255, 255, 255), is_magic: bool = False):
        self.damage_floats.append({
            "x": x, "y": y, "value": value, "color": color,
            "lifetime": 0.6, "is_magic": is_magic
        })

    def trigger_shake(self, intensity: float):
        self.shake_intensity = intensity
        self.shake_timer = 0.12

    def trigger_freeze(self, duration: float):
        self.freeze_timer = duration

    def show_message(self, msg: str, duration: float = 2.0):
        """显示房间消息 toast，自动处理 RELIC 前缀 (金色)。"""
        self.room_msg = msg
        self.room_msg_timer = duration

    def show_relic_message(self, relic_name: str):
        """显示 relic 获得消息 (带 RELIC: 前缀)。"""
        self.show_message(f"RELIC:{relic_name}", 3.5)

    # ── G5.8.2: BuildTheme 集成 ──────────────────────────

    def update_theme(self, player) -> bool:
        """根据玩家构筑刷新主题，返回 True 表示主题变化。"""
        new_theme = get_active_theme(player)
        changed = new_theme.name != self._active_theme.name
        self._active_theme = new_theme
        return changed

    @property
    def active_theme(self) -> BuildTheme:
        return self._active_theme

    def spawn_themed_damage(self, x: float, y: float, value: int,
                            is_magic: bool = False):
        """按当前主题色生成伤害数字 (G5.8.2 3-tier)。"""
        color = self._active_theme.dmg_color_for(value)
        self.spawn_damage(x, y, value, color, is_magic)

    def get_particle_speed(self) -> float:
        return self._active_theme.particle_speed

    def get_explosion_scale(self) -> float:
        return self._active_theme.explosion_scale

    # ── G5.8.3: Camera control ────────────────────────────

    def trigger_boss_landing(self):
        """Camera zoom + heavy shake when boss appears."""
        self.trigger_shake(12)
        self.boss_landing_timer = 0.8

    def set_dash_offset(self, dx: float, dy: float):
        """Nudge camera in dash direction (called per move frame)."""
        self.dash_offset_x = dx * 16
        self.dash_offset_y = dy * 16

    def get_camera_shake_offset(self) -> tuple:
        """Return random (sx, sy) for current shake state."""
        if self.shake_timer <= 0:
            return 0, 0
        import random
        ratio = self.shake_timer / 0.12
        intensity = int(self.shake_intensity * ratio)
        return (random.randint(-intensity, intensity),
                random.randint(-intensity, intensity))

    def is_room_msg_active(self) -> bool:
        return self.room_msg_timer > 0 and bool(self.room_msg)

    def is_intro_active(self) -> bool:
        return self.floor_intro_active or self.chapter_intro_active
