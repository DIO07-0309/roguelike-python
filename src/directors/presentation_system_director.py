"""
PresentationSystemDirector — visual presentation dispatch hub (G5.8.7)

All gameplay→presentation communication flows through dispatch().
BuildTheme is the single source of truth for colors/style.
Camera, Audio, VFX, and Damage Numbers are consumers of PresentationEvent.

Architecture:
  GameScene → dispatch(PresentationEvent) → {BuildTheme, Recipe, Camera, Audio, Damage}
"""

from dataclasses import dataclass, field
from src.game.build_theme import BuildTheme, get_active_theme, DEFAULT_THEME


# ══════════════════════════════════════════════════════════════
#  PresentationEvent — unified event type for all visual/audio
# ══════════════════════════════════════════════════════════════

@dataclass
class PresentationEvent:
    """A single gameplay→presentation event. All fields optional.

    The Director resolves theme, recipe, SFX, camera, and damage
    from this event. Callers only set what's relevant.
    """
    kind: str = ""                # "melee_hit" | "skill_cast" | "boss_phase2" | ...
    cx: int = 0
    cy: int = 0
    target_cx: int = 0
    target_cy: int = 0
    dmg: int = 0
    dmg_is_magic: bool = False
    direction = None              # player Direction for arc effects
    skill_name: str = ""          # Chinese name, e.g. "冰爆"
    skill_level: int = 1
    theme_override: str = ""      # "" = use active BuildTheme
    recipe_override: str = ""     # "" = auto-resolve from skill_name / kind
    sfx_override: str = ""        # "" = auto-resolve from recipe JSON
    intensity: int = 0            # shake intensity override (0=auto from dmg)
    extra_effects: list = field(default_factory=list)  # additional VFX dicts


# ══════════════════════════════════════════════════════════════
#  Skill → Recipe / SFX mapping (replaces if/elif chain)
# ══════════════════════════════════════════════════════════════

_SKILL_TO_RECIPE: dict[str, str] = {
    "斩击": "skill_slash",
    "神罚": "skill_fireball",
    "自愈": "skill_heal",
    "冰爆": "skill_ice_nova",
    "连锁闪电": "skill_chain_lightning",
    "暗影突刺": "skill_slash",       # shadow preset
    "血怒": "melee_hit",             # bleed preset
    "召唤英灵": "boss_summon",       # summon preset
}

_KIND_TO_RECIPE: dict[str, str] = {
    "melee_hit": "melee_hit",
    "boss_phase2": "boss_phase2",
    "boss_landing": "boss_phase2",
    "level_up": "level_up",
    "time_stop": "time_stop",
    "monster_death": "melee_hit",
}

# SFX fallback when recipe JSON doesn't specify one
_RECIPE_SFX_FALLBACK: dict[str, str] = {
    "skill_slash": "slash",
    "skill_fireball": "bolt",
    "skill_heal": "heal",
    "skill_ice_nova": "ice_crack",
    "skill_chain_lightning": "lightning",
    "melee_hit": "melee",
    "boss_phase2": "hit",
    "level_up": "levelup",
    "time_stop": "timestop",
    "boss_summon": "summon",
}


class PresentationSystemDirector:
    """Visual presentation orchestration — the single dispatch hub.

    G5.8.7: dispatch() is the sole entry for all gameplay→presentation.
    G5.8.2: holds active BuildTheme.
    G5.8.3: camera shake/dash/zoom state.
    """

    def __init__(self):
        self.damage_floats: list = []
        self._active_theme: BuildTheme = DEFAULT_THEME
        self.shake_timer: float = 0.0
        self.shake_intensity: float = 0.0
        self.freeze_timer: float = 0.0
        # G5.8.8: Timeline management
        self._active_timelines: list = []
        self._effects_target: list | None = None
        # Camera state
        self.dash_offset_x: float = 0.0
        self.dash_offset_y: float = 0.0
        self.zoom_level: float = 1.0
        self.zoom_target: float = 1.0
        self.boss_landing_timer: float = 0.0
        # Messages
        self.room_msg: str = ""
        self.room_msg_timer: float = 0.0
        self.boss_intro_text: str = ""
        self.boss_modifier_text: str = ""
        # Intro overlays
        self.floor_intro_active: bool = False
        self.floor_intro_timer: float = 0.0
        self.floor_intro_fade: float = 0.0
        self.floor_intro_floor: int = 0
        self.chapter_intro_active: bool = False
        self.chapter_intro_timer: float = 0.0
        self.chapter_intro_ch: int = 0
        # Debug toggles
        self.show_growth_debug: bool = False
        self.show_flow_debug: bool = False
        self.show_boss_behavior: bool = False
        self.show_boss_cmd: bool = False
        self.show_boss_report: bool = False
        self.combat_juice_on: bool = True

    # ═══════════════════════════════════════════════════════
    #  tick() — per-frame state decay
    # ═══════════════════════════════════════════════════════

    def tick(self, dt: float):
        """Per-frame: decay all timers and animate camera state."""
        # Room message
        if self.room_msg_timer > 0:
            self.room_msg_timer -= dt
            if self.room_msg_timer <= 0:
                self.room_msg_timer = 0
                self.room_msg = ""
        # Floor intro
        if self.floor_intro_active:
            self.floor_intro_timer -= dt
            self.floor_intro_fade = min(1.0, self.floor_intro_fade + dt * 2.5)
            if self.floor_intro_timer <= 0:
                self.floor_intro_active = False
        # Chapter intro
        if self.chapter_intro_active:
            self.chapter_intro_timer -= dt
            if self.chapter_intro_timer <= 0:
                self.chapter_intro_active = False
        # Damage floats
        for df in self.damage_floats:
            df["lifetime"] -= dt
        self.damage_floats = [d for d in self.damage_floats if d["lifetime"] > 0]
        # Screen shake
        if self.shake_timer > 0:
            self.shake_timer -= dt
        # Boss landing zoom
        if self.boss_landing_timer > 0:
            self.boss_landing_timer -= dt
            self.zoom_target = 1.0 + 0.15 * min(1.0, self.boss_landing_timer / 0.8)
        else:
            self.zoom_target = 1.0
        self.zoom_level += (self.zoom_target - self.zoom_level) * min(1.0, dt * 6.0)
        # Dash offset decay
        decay = min(1.0, dt * 8.0)
        self.dash_offset_x *= (1.0 - decay)
        self.dash_offset_y *= (1.0 - decay)
        if abs(self.dash_offset_x) < 0.5:
            self.dash_offset_x = 0.0
        if abs(self.dash_offset_y) < 0.5:
            self.dash_offset_y = 0.0
        # G5.8.8: advance active timelines, drop finished ones
        for tl in self._active_timelines:
            tl.tick(dt)
        self._active_timelines = [tl for tl in self._active_timelines
                                  if tl.is_playing() and not tl.is_finished()]

    # ═══════════════════════════════════════════════════════
    #  G5.8.8: Timeline binding
    # ═══════════════════════════════════════════════════════

    def bind_effects_target(self, effects_list: list):
        """Set the mutable list that Timelines append effects to."""
        self._effects_target = effects_list

    # ═══════════════════════════════════════════════════════
    #  dispatch() — unified presentation entry point
    # ═══════════════════════════════════════════════════════

    def dispatch(self, ev: PresentationEvent) -> list:
        """Route a gameplay event to all presentation subsystems.

        Order: Theme → Recipe(resolve) → VFX(play_recipe) → Camera(shake)
               → Audio(play_sfx) → Damage(spawn_themed_damage)

        Returns the list of VFX effect dicts added to _attack_effects
        (caller may append to eng._attack_effects, or we can do it here
        if an engine reference is provided).

        Args:
            ev: PresentationEvent describing what happened.

        Returns:
            list[dict] of VFX effects.
        """
        if not self.combat_juice_on:
            return []

        # 1. Resolve theme
        preset = ev.theme_override or self._active_theme.vfx_preset

        # 2. Resolve recipe name
        recipe = ev.recipe_override
        if not recipe:
            recipe = _SKILL_TO_RECIPE.get(ev.skill_name, "")
        if not recipe:
            recipe = _KIND_TO_RECIPE.get(ev.kind, "")
        if not recipe:
            recipe = ev.kind  # raw fallback

        # 3. Resolve SFX name
        sfx = ev.sfx_override
        if not sfx:
            sfx = self._sfx_for_recipe(recipe)
        if not sfx:
            sfx = _RECIPE_SFX_FALLBACK.get(recipe, "")

        # 4. Play VFX recipe + schedule delayed steps (G5.8.8)
        effects = []
        if recipe:
            from src.fx_engine import play_recipe, recipe_to_timeline
            # Immediate effects (delay=0)
            effects = play_recipe(recipe, ev.cx, ev.cy,
                                  preset=preset,
                                  direction=ev.direction,
                                  target_cx=ev.target_cx,
                                  target_cy=ev.target_cy)
            # Delayed effects → Timeline
            if self._effects_target is not None:
                tl = recipe_to_timeline(recipe, ev.cx, ev.cy,
                                        self._effects_target,
                                        preset=preset,
                                        direction=ev.direction,
                                        target_cx=ev.target_cx,
                                        target_cy=ev.target_cy)
                if tl:
                    tl.play()
                    self._active_timelines.append(tl)

        # 5. Camera shake
        intensity = ev.intensity
        if intensity == 0 and ev.dmg >= 25:
            intensity = max(2, min(10, ev.dmg // 5))
        if ev.kind == "skill_cast" and ev.dmg >= 20:
            intensity = max(3, min(10, ev.dmg // 5))
        if intensity > 0:
            self.trigger_shake(intensity)

        # 6. Audio — SFX
        if sfx:
            from src.sfx_engine import play_sfx
            vol = 1.0 if sfx == "timestop" else 0.6
            play_sfx(sfx, vol)

        # 7. Damage numbers
        if ev.dmg > 0:
            self.spawn_themed_damage(ev.cx, ev.cy - 8, ev.dmg, ev.dmg_is_magic)

        return effects

    def _sfx_for_recipe(self, recipe: str) -> str:
        """Look up SFX from recipe JSON if available, else fallback table."""
        try:
            from src.fx_engine import _recipe_cache
            if _recipe_cache:
                rec = _recipe_cache.get("recipes", {}).get(recipe, {})
                return rec.get("sfx", "")
        except Exception:
            pass
        return _RECIPE_SFX_FALLBACK.get(recipe, "")

    # ═══════════════════════════════════════════════════════
    #  Legacy API — preserved for gradual migration
    # ═══════════════════════════════════════════════════════

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
        self.room_msg = msg
        self.room_msg_timer = duration

    def show_relic_message(self, relic_name: str):
        self.show_message(f"RELIC:{relic_name}", 3.5)

    def spawn_themed_damage(self, x: float, y: float, value: int,
                            is_magic: bool = False):
        color = self._active_theme.dmg_color_for(value)
        self.spawn_damage(x, y, value, color, is_magic)

    # ── BuildTheme ────────────────────────────────────────

    def update_theme(self, player) -> bool:
        new_theme = get_active_theme(player)
        changed = new_theme.name != self._active_theme.name
        self._active_theme = new_theme
        return changed

    @property
    def active_theme(self) -> BuildTheme:
        return self._active_theme

    def get_particle_speed(self) -> float:
        return self._active_theme.particle_speed

    def get_explosion_scale(self) -> float:
        return self._active_theme.explosion_scale

    # ── Camera ────────────────────────────────────────────

    def trigger_boss_landing(self):
        self.trigger_shake(12)
        self.boss_landing_timer = 0.8

    def set_dash_offset(self, dx: float, dy: float):
        self.dash_offset_x = dx * 16
        self.dash_offset_y = dy * 16

    def get_camera_shake_offset(self) -> tuple:
        if self.shake_timer <= 0:
            return 0, 0
        import random
        ratio = self.shake_timer / 0.12
        intensity = int(self.shake_intensity * ratio)
        return (random.randint(-intensity, intensity),
                random.randint(-intensity, intensity))

    # ── Queries ───────────────────────────────────────────

    def is_room_msg_active(self) -> bool:
        return self.room_msg_timer > 0 and bool(self.room_msg)

    def is_intro_active(self) -> bool:
        return self.floor_intro_active or self.chapter_intro_active
