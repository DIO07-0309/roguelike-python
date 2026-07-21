"""
G5.8.2 sync: BuildTheme — visual theme per BuildType (C++ parity)

7-field struct + 12 presets + 3-tier damage color.
Each BuildType gets a distinct visual identity: HUD colors, particle
behavior, explosion scale, and VFX preset override.
"""

from src.game.build_score import BuildType

# ── RGB color shorthand ──────────────────────────────────────
GOLD = (255, 215, 0)
NEUTRAL_GRAY = (160, 160, 160)


class BuildTheme:
    """Visual theme tied to a BuildType.

    Fields (C++ parity):
        primary:       HUD border / cursor / main identity color.
        secondary:     damage number color for 25+ dmg hits.
        accent:        damage number color for 10-24 dmg hits / glow.
        name:          short preset id ("ice"|"fire"|"lightning"|…).
        particle_speed: multiplier on particle animation speed.
        explosion_scale: radius multiplier on AoE / burst effects.
        vfx_preset:    overrides recipe default color palette.
    """

    def __init__(self, primary, secondary, accent, name: str,
                 particle_speed: float = 1.0,
                 explosion_scale: float = 1.0,
                 vfx_preset: str = "default"):
        self.primary = primary
        self.secondary = secondary
        self.accent = accent
        self.name = name
        self.particle_speed = particle_speed
        self.explosion_scale = explosion_scale
        self.vfx_preset = vfx_preset

    # ── 3-tier damage coloring (C++ dmg_color_for parity) ──

    def dmg_color_for(self, dmg: int) -> tuple:
        """Return (r,g,b) for a damage number based on magnitude.

        ≥50  → gold (override, theme-independent).
        ≥25  → theme.secondary.
        ≥10  → theme.accent blended 50% with neutral gray.
        <10  → neutral gray.
        """
        if dmg >= 50:
            return GOLD
        if dmg >= 25:
            return self.secondary
        if dmg >= 10:
            a = self.accent
            return ((a[0] + 128) // 2, (a[1] + 128) // 2, (a[2] + 128) // 2)
        return NEUTRAL_GRAY

    # ── Factory ─────────────────────────────────────────────

    @staticmethod
    def from_build_type(bt: BuildType) -> "BuildTheme":
        return _THEMES.get(bt, DEFAULT_THEME)


# ══════════════════════════════════════════════════════════════
#  12 presets — one per BuildType (C++ parity)
# ══════════════════════════════════════════════════════════════

_THEMES: dict[BuildType, BuildTheme] = {
    BuildType.BERSERKER: BuildTheme(
        primary=(255, 60, 40), secondary=(255, 100, 60),
        accent=(220, 70, 40), name="berserker",
        particle_speed=1.05, explosion_scale=1.20,
        vfx_preset="fire",
    ),
    BuildType.FIRE_MAGE: BuildTheme(
        primary=(255, 140, 0), secondary=(255, 100, 30),
        accent=(240, 80, 20), name="fire",
        particle_speed=1.30, explosion_scale=1.25,
        vfx_preset="fire",
    ),
    BuildType.POISON_MASTER: BuildTheme(
        primary=(100, 200, 50), secondary=(140, 230, 80),
        accent=(80, 180, 40), name="poison",
        particle_speed=0.90, explosion_scale=1.05,
        vfx_preset="poison",
    ),
    BuildType.TIME_MASTER: BuildTheme(
        primary=(180, 160, 220), secondary=(200, 180, 240),
        accent=(160, 140, 200), name="time",
        particle_speed=0.75, explosion_scale=0.95,
        vfx_preset="time",
    ),
    BuildType.SUPPORT: BuildTheme(
        primary=(80, 220, 120), secondary=(120, 255, 160),
        accent=(60, 200, 90), name="support",
        particle_speed=0.95, explosion_scale=1.00,
        vfx_preset="heal",
    ),
    BuildType.PROJECTILE: BuildTheme(
        primary=(80, 180, 255), secondary=(120, 210, 255),
        accent=(60, 150, 240), name="projectile",
        particle_speed=1.15, explosion_scale=1.00,
        vfx_preset="lightning",
    ),
    # ── G5 sync: new builds ──
    BuildType.ICE_MAGE: BuildTheme(
        primary=(80, 200, 255), secondary=(140, 230, 255),
        accent=(60, 170, 240), name="ice",
        particle_speed=0.70, explosion_scale=1.15,
        vfx_preset="ice",
    ),
    BuildType.LIGHTNING_MAGE: BuildTheme(
        primary=(220, 200, 40), secondary=(255, 240, 80),
        accent=(200, 170, 30), name="lightning",
        particle_speed=1.40, explosion_scale=1.10,
        vfx_preset="lightning",
    ),
    BuildType.BLEED_BLADE: BuildTheme(
        primary=(200, 40, 40), secondary=(230, 70, 50),
        accent=(170, 30, 30), name="bleed",
        particle_speed=0.95, explosion_scale=1.05,
        vfx_preset="bleed",
    ),
    BuildType.SHADOW_STRIKER: BuildTheme(
        primary=(140, 80, 200), secondary=(170, 120, 230),
        accent=(110, 60, 180), name="shadow",
        particle_speed=0.85, explosion_scale=0.90,
        vfx_preset="shadow",
    ),
    BuildType.JUGGERNAUT: BuildTheme(
        primary=(200, 180, 140), secondary=(230, 210, 170),
        accent=(170, 150, 110), name="juggernaut",
        particle_speed=0.85, explosion_scale=0.90,
        vfx_preset="white",
    ),
    BuildType.SUMMON_LORD: BuildTheme(
        primary=(180, 140, 220), secondary=(210, 170, 250),
        accent=(150, 110, 200), name="summon",
        particle_speed=0.90, explosion_scale=1.10,
        vfx_preset="summon",
    ),
}

# Default / no-build fallback
DEFAULT_THEME = BuildTheme(
    primary=(200, 200, 200), secondary=(220, 220, 220),
    accent=(170, 170, 170), name="default",
    particle_speed=1.0, explosion_scale=1.0,
    vfx_preset="default",
)


def get_active_theme(player) -> BuildTheme:
    """Resolve the BuildTheme for the player's current build."""
    from src.game.build_score import calculate_build
    bs = calculate_build(player)
    return BuildTheme.from_build_type(bs.identify())


def get_theme_for_build_type(build_type) -> BuildTheme:
    """G6.4: resolve theme from a BuildType (zero Gameplay dependency)."""
    return BuildTheme.from_build_type(build_type)
