"""
──────────────────────────────────────────
战斗特效引擎 — 脉冲/弧线/爆散/震屏 + VFX Recipes
──────────────────────────────────────────

职责：
  - 提供丰富多元的攻击/技能/Boss视觉特效。
  - 支持等级驱动（Lv1/2/3 不同规模）。
  - 支持朝向感知（弧线、锥形跟随方向）。
  - G5.8.5: vfx_recipes.json 数据驱动 + play_recipe()

设计原则：
  - 纯函数，通过 attack_effects 列表驱动。
  - 复用现有 _attack_effects dict 格式。

设计原则：
  - 纯函数，通过 attack_effects 列表驱动。
  - 复用现有 _attack_effects dict 格式。
"""

import math
import random
import pygame


# =========================================================
#  特效工厂 — 返回 effects dict 列表
# =========================================================

def player_attack_fx(cx: int, cy: int, radius: int = 48) -> list[dict]:
    """玩家普攻：金色脉冲圆 + 4小火星。"""
    return [
        {"kind": "pulse", "x": cx, "y": cy, "radius": radius,
         "color": (255, 200, 50), "duration": 0.35, "elapsed": 0.0},
    ] + _sparks(cx, cy, 4, (255, 220, 100), 0.25)


def slash_skill_fx(cx: int, cy: int, direction, level: int) -> list[dict]:
    """斩击：等级越高规模越大。"""
    r = {1: 56, 2: 72, 3: 88}[level]
    dur = 0.35
    color = (255, 80, 80)
    effects = [
        {"kind": "slash_arc", "x": cx, "y": cy, "radius": r,
         "color": color, "duration": dur, "elapsed": 0.0,
         "direction": direction},
    ]
    if level >= 2:
        # 额外斜线
        effects.append({"kind": "cone", "x": cx, "y": cy, "radius": r,
                         "color": (255, 60, 60), "duration": 0.3, "elapsed": 0.0})
    if level >= 3:
        effects += _sparks(cx, cy, 8, (255, 120, 80), 0.35)
    return effects


def fireball_fx(cx: int, cy: int, target_cx: int, target_cy: int,
                level: int) -> list[dict]:
    """神罚：多圈脉冲 + 火花轨迹。"""
    dur_map = {1: 0.4, 2: 0.45, 3: 0.5}
    rings = {1: 1, 2: 2, 3: 3}
    dur = dur_map[level]
    effects = []
    # 发射轨迹线（闪电弧光）
    effects.append({"kind": "bolt", "x": cx, "y": cy,
                     "tx": target_cx, "ty": target_cy,
                     "color": (255, 160, 30), "duration": dur, "elapsed": 0.0})
    # 目标点脉冲圆（多层）
    for i in range(rings[level]):
        effects.append({"kind": "pulse", "x": target_cx, "y": target_cy,
                         "radius": 48 + i * 20,
                         "color": (255, 140, 0), "duration": dur - i * 0.08,
                         "elapsed": 0.0})
    # 击中火花
    effects += _sparks(target_cx, target_cy, 10 + level * 4, (255, 180, 40), 0.4)
    return effects


def heal_fx(cx: int, cy: int, level: int) -> list[dict]:
    """自愈：绿色光柱 + 上升气泡。"""
    dur = 0.5
    effects = [{"kind": "pulse", "x": cx, "y": cy, "radius": 48,
                 "color": (50, 255, 100), "duration": dur, "elapsed": 0.0}]
    bubbles = 6 + level * 4
    effects += _sparks(cx, cy, bubbles, (100, 255, 150), 0.6)
    if level >= 3:
        # 持续再生光环
        effects.append({"kind": "pulse", "x": cx, "y": cy, "radius": 64,
                         "color": (80, 255, 130), "duration": 0.7, "elapsed": 0.0})
    return effects


def monsters_attack_fx(cx: int, cy: int, target_cx: int, target_cy: int,
                        color: tuple = (255, 255, 255)) -> list[dict]:
    """怪物普攻：红色小脉冲 + 爪痕弧线朝向玩家。"""
    dur = 0.3
    effects = [
        {"kind": "pulse", "x": cx, "y": cy, "radius": 36,
         "color": color, "duration": dur, "elapsed": 0.0},
    ]
    # 爪击弧线朝向玩家
    dx = target_cx - cx
    dy = target_cy - cy
    angle = math.degrees(math.atan2(-dy, dx))
    effects.append({"kind": "arc", "x": cx, "y": cy, "radius": 30,
                     "color": color, "duration": 0.25, "elapsed": 0.0,
                     "angle": angle})
    effects += _sparks(cx, cy, 3, color, 0.2)
    return effects


def boss_cone_fx(cx: int, cy: int) -> list[dict]:
    """Boss暗影冲击：多重红圈 + 震屏级大圈。"""
    effects = [
        {"kind": "pulse", "x": cx, "y": cy, "radius": 48, "color": (200, 40, 40),
         "duration": 0.5, "elapsed": 0.0},
        {"kind": "pulse", "x": cx, "y": cy, "radius": 80, "color": (180, 30, 30),
         "duration": 0.45, "elapsed": 0.0},
        {"kind": "pulse", "x": cx, "y": cy, "radius": 120, "color": (140, 20, 20),
         "duration": 0.4, "elapsed": 0.0},
    ]
    effects += _sparks(cx, cy, 12, (200, 60, 40), 0.5)
    return effects


def boss_circle_fx(cx: int, cy: int) -> list[dict]:
    """Boss地裂：暗红大圆 + 火焰碎片。"""
    effects = [
        {"kind": "pulse", "x": cx, "y": cy, "radius": 60, "color": (220, 50, 50),
         "duration": 0.5, "elapsed": 0.0},
        {"kind": "pulse", "x": cx, "y": cy, "radius": 96, "color": (200, 40, 30),
         "duration": 0.45, "elapsed": 0.0},
        {"kind": "pulse", "x": cx, "y": cy, "radius": 140, "color": (160, 30, 20),
         "duration": 0.4, "elapsed": 0.0},
    ]
    effects += _sparks(cx, cy, 16, (240, 80, 60), 0.5)
    return effects


def boss_summon_fx(cx: int, cy: int) -> list[dict]:
    """Boss召唤：紫色漩涡。"""
    effects = []
    for i in range(3):
        effects.append({"kind": "pulse", "x": cx, "y": cy,
                         "radius": 50 + i * 25,
                         "color": (150, 50, 200), "duration": 0.6, "elapsed": 0.0})
    effects += _sparks(cx, cy, 10, (180, 80, 220), 0.5)
    return effects


def time_stop_fx(cx: int, cy: int) -> list[dict]:
    """The World — 全景时停动画。"""
    effects = [
        {"kind": "pulse", "x": cx, "y": cy, "radius": 400,
         "color": (180, 180, 200), "duration": 1.0, "elapsed": 0.0},
        {"kind": "pulse", "x": cx, "y": cy, "radius": 600,
         "color": (140, 140, 180), "duration": 0.8, "elapsed": 0.0},
        {"kind": "pulse", "x": cx, "y": cy, "radius": 900,
         "color": (100, 100, 160), "duration": 0.6, "elapsed": 0.0},
    ]
    return effects


def hit_flash_fx(entity_x: int, entity_y: int, size: int = 28) -> list[dict]:
    """受击闪光：白光小圆。"""
    cx = entity_x + size // 2
    cy = entity_y + size // 2
    return [
        {"kind": "flash", "x": cx, "y": cy, "radius": size // 2 + 4,
         "color": (255, 255, 255), "duration": 0.12, "elapsed": 0.0},
    ]


# =========================================================
#  内部工具
# =========================================================

def _sparks(cx: int, cy: int, count: int, color: tuple,
            duration: float) -> list[dict]:
    """生成随机方向散射粒子。"""
    out = []
    for _ in range(count):
        dx = random.randint(-20, 20)
        dy = random.randint(-20, 20)
        out.append({"kind": "spark", "x": cx + dx * 3, "y": cy + dy * 3,
                     "radius": 1 + random.randint(1, 3), "color": color,
                     "duration": duration, "elapsed": 0.0})
    return out


# =========================================================
#  渲染函数
# =========================================================

def draw_fx_on_screen(self_screen, fx: dict, camera_x: int, camera_y: int):
    """分发渲染单个特效到屏幕上。

    参数：
        self_screen: pygame screen。
        fx: 特效 dict。
        camera_x, camera_y: 摄像机偏移。
    """
    sx = fx["x"] - camera_x
    sy = fx["y"] - camera_y
    ratio = 1.0 - fx["elapsed"] / fx["duration"]
    alpha = int(min(255, 120 * ratio + 30))
    r, g, b = fx["color"][:3]
    ca = (r, g, b, alpha)
    kind = fx["kind"]

    if kind == "circle":
        _draw_circle(self_screen, sx, sy, fx["radius"], ca)
    elif kind == "pulse":
        # 脉冲：从小到大扩展
        pulse_r = int(fx["radius"] * (0.4 + 0.6 * (1.0 - ratio)))
        _draw_circle(self_screen, sx, sy, pulse_r, ca)
    elif kind == "cone":
        _draw_filled_rect_centered(self_screen, sx, sy, fx["radius"], ca)
    elif kind == "spark":
        r2 = max(1, fx["radius"])
        pygame.draw.circle(self_screen, ca, (int(sx), int(sy)), r2)
    elif kind == "flash":
        # 白色闪光（快速大→小）
        flash_r = int(fx["radius"] * (0.3 + 0.7 * ratio))
        flash_a = int(200 * ratio)
        fl_c = (255, 255, 255, flash_a)
        _draw_circle(self_screen, sx, sy, flash_r, fl_c)
    elif kind == "slash_arc":
        # 根据方向画弧线
        _draw_slash_arc(self_screen, sx, sy, fx["radius"], ca, fx.get("direction"))
    elif kind == "bolt":
        # 闪光连线
        tx = fx.get("tx", sx) - camera_x
        ty = fx.get("ty", sy) - camera_y
        _draw_bolt(self_screen, sx, sy, tx, ty, ca, ratio)
    elif kind == "arc":
        # 爪痕弧线
        _draw_arc(self_screen, sx, sy, fx["radius"], ca, fx.get("angle", 0))


def _draw_circle(screen, cx, cy, r, color):
    """画透明圆环。"""
    d = max(6, r * 2 + 6)
    srf = pygame.Surface((d, d), pygame.SRCALPHA)
    pygame.draw.circle(srf, color, (d // 2, d // 2), max(1, r), 3)
    screen.blit(srf, (cx - d // 2, cy - d // 2))


def _draw_filled_rect_centered(screen, cx, cy, r, color):
    """中心对齐的填充矩形。"""
    d = r * 2
    srf = pygame.Surface((d, d), pygame.SRCALPHA)
    srf.fill(color)
    pygame.draw.rect(srf, (color[0], color[1], color[2], min(255, color[3] + 60)),
                     (0, 0, d, d), 2)
    screen.blit(srf, (cx - r, cy - r))


def _draw_slash_arc(screen, cx, cy, r, color, direction):
    """根据玩家朝向绘制斩击弧线。"""
    d = r * 2 + 10
    srf = pygame.Surface((d, d), pygame.SRCALPHA)
    center = (d // 2, d // 2)
    # 根据方向画三条高亮线
    if direction:
        from src.entities.player import Direction
        offsets = {
            Direction.UP: [(0, -10), (-8, -6), (8, -6)],
            Direction.DOWN: [(0, 10), (-8, 6), (8, 6)],
            Direction.LEFT: [(-10, 0), (-6, -8), (-6, 8)],
            Direction.RIGHT: [(10, 0), (6, -8), (6, 8)],
        }
        pts = offsets.get(direction, [(0, 0)])
        for ox, oy in pts:
            end = (center[0] + ox * r // 10, center[1] + oy * r // 10)
            pygame.draw.line(srf, color, center, end, 4)
    # 边框弧
    pygame.draw.circle(srf, color, center, r, 2)
    screen.blit(srf, (cx - d // 2, cy - d // 2))


def _draw_bolt(screen, x1, y1, x2, y2, color, ratio):
    """闪电连线（多段锯齿）。"""
    import math
    segs = 8
    dx = (x2 - x1) / segs
    dy = (y2 - y1) / segs
    px, py = x1, y1
    alpha = max(40, int(color[3] * ratio))
    c = (color[0], color[1], color[2], alpha)
    for s in range(segs):
        jitter_x = px + dx + random.randint(-12, 12)
        jitter_y = py + dy + random.randint(-12, 12)
        t = (s + 1) / segs
        nx = x1 + dx * (s + 1) + int(math.sin(t * 12) * 8) * (1 - ratio)
        ny = y1 + dy * (s + 1) + int(math.cos(t * 12) * 8) * (1 - ratio)
        if random.random() < 0.7:
            pygame.draw.line(screen, c, (int(px), int(py)),
                             (int(nx), int(ny)), 3)
        px, py = nx, ny


def _draw_arc(screen, cx, cy, r, color, angle):
    """爪痕弧线。"""
    import math
    d = r * 2 + 6
    srf = pygame.Surface((d, d), pygame.SRCALPHA)
    center = (d // 2, d // 2)
    rad = math.radians(angle)
    end_x = center[0] + int(r * math.cos(rad))
    end_y = center[1] - int(r * math.sin(rad))
    # 三条发散线
    for off in (-15, 0, 15):
        rad2 = math.radians(angle + off)
        ex = center[0] + int(r * 0.7 * math.cos(rad2))
        ey = center[1] - int(r * 0.7 * math.sin(rad2))
        pygame.draw.line(srf, color, center, (ex, ey), 2)
    screen.blit(srf, (cx - d // 2, cy - d // 2))


# =========================================================
#  G5.8.5: VFX Recipes — JSON-driven composable effects
# =========================================================

import json
import os
import sys

_recipe_cache: dict | None = None


def _resolve_vfx_path() -> str:
    """Resolve vfx_recipes.json path (supports PyInstaller)."""
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, "resources", "vfx_recipes.json")
    src_dir = os.path.dirname(os.path.abspath(__file__))
    rel = os.path.join(src_dir, "..", "..", "resources", "vfx_recipes.json")
    for p in (alt, rel):
        if os.path.exists(p):
            return p
    return alt


def _ensure_recipes_loaded():
    """Lazy-load vfx_recipes.json into module cache."""
    global _recipe_cache
    if _recipe_cache is not None:
        return
    try:
        path = _resolve_vfx_path()
        with open(path, "r", encoding="utf-8") as f:
            _recipe_cache = json.load(f)
    except Exception as e:
        print(f"[VFX] Failed to load recipes: {e}")
        _recipe_cache = {"presets": {}, "recipes": {}}


def _blend_colors(color_a: tuple, color_b: tuple, factor: float = 0.5) -> tuple:
    """Blend two RGB colors by factor (0.0 = pure A, 1.0 = pure B)."""
    return tuple(int(a + (b - a) * factor) for a, b in zip(color_a, color_b))


def play_recipe(recipe_name: str, cx: int, cy: int,
                preset: str = "default", direction=None,
                target_cx: int = 0, target_cy: int = 0) -> list[dict]:
    """Compose a list of effect dicts from a named recipe.

    Parameters:
        recipe_name: key in vfx_recipes.json.recipes (e.g. "melee_hit").
        cx, cy: origin pixel coordinates.
        preset: color preset key (e.g. "fire", "ice").
        direction: player Direction for slash_arc.
        target_cx, target_cy: target for bolt effects.

    Returns:
        list of effect dicts ready for _attack_effects.
    """
    _ensure_recipes_loaded()
    presets = _recipe_cache.get("presets", {})
    recipes = _recipe_cache.get("recipes", {})
    recipe = recipes.get(recipe_name)
    if not recipe:
        return []
    colors = presets.get(preset, presets.get("default", {}))

    effects = []
    for step in recipe.get("steps", []):
        kind = step.get("kind", "pulse")
        radius = step.get("radius", 48)
        duration = step.get("duration", 0.35)
        layers = step.get("layers", 1)
        layer_delay = step.get("layer_delay", 0.08)
        count = step.get("count", 4)

        # Resolve color from preset
def _resolve_recipe_step_color(kind: str, colors: dict) -> tuple:
    """Resolve color from a preset dict for a given effect kind."""
    if kind == "flash":
        return (255, 255, 255)
    if kind == "bolt":
        return tuple(colors.get("bolt", (255, 160, 30)))
    if kind == "spark":
        return tuple(colors.get("spark", (255, 220, 100)))
    if kind == "slash_arc":
        return tuple(colors.get("arc", (255, 180, 60)))
    return tuple(colors.get("pulse", (255, 200, 50)))


def _make_step_effects(step: dict, cx: int, cy: int, clr: tuple,
                       direction=None, target_cx: int = 0, target_cy: int = 0) -> list[dict]:
    """Build effect dicts from a single recipe step."""
    kind = step.get("kind", "pulse")
    radius = step.get("radius", 48)
    duration = step.get("duration", 0.35)
    layers = step.get("layers", 1)
    layer_delay = step.get("layer_delay", 0.08)
    count = step.get("count", 4)
    effects = []
    for layer in range(layers):
        layer_dur = max(0.05, duration - layer * layer_delay)
        if kind == "spark":
            effects += _sparks(cx, cy, count, clr, layer_dur)
        elif kind == "slash_arc":
            effects.append({
                "kind": kind, "x": cx, "y": cy,
                "radius": radius + layer * 10, "color": clr,
                "duration": layer_dur, "elapsed": 0.0,
                "direction": direction,
            })
        elif kind == "bolt":
            effects.append({
                "kind": kind, "x": cx, "y": cy,
                "tx": target_cx or cx, "ty": target_cy or cy,
                "color": clr, "duration": layer_dur, "elapsed": 0.0,
            })
        else:
            effects.append({
                "kind": kind, "x": cx, "y": cy,
                "radius": radius + layer * 16, "color": clr,
                "duration": layer_dur, "elapsed": 0.0,
            })
    return effects


def play_recipe(recipe_name: str, cx: int, cy: int,
                preset: str = "default", direction=None,
                target_cx: int = 0, target_cy: int = 0) -> list[dict]:
    """Compose immediate (delay=0) effect dicts from a named recipe.

    G5.8.8: Only returns steps without a delay field. Delayed steps
    are handled by recipe_to_timeline().
    """
    _ensure_recipes_loaded()
    presets = _recipe_cache.get("presets", {})
    recipes = _recipe_cache.get("recipes", {})
    recipe = recipes.get(recipe_name)
    if not recipe:
        return []
    colors = presets.get(preset, presets.get("default", {}))
    effects = []
    for step in recipe.get("steps", []):
        if step.get("delay", 0.0) > 0.0:
            continue
        clr = _resolve_recipe_step_color(step.get("kind", "pulse"), colors)
        effects += _make_step_effects(step, cx, cy, clr, direction, target_cx, target_cy)
    return effects


def recipe_to_timeline(recipe_name: str, cx: int, cy: int,
                       effects_target: list, preset: str = "default",
                       direction=None, target_cx: int = 0, target_cy: int = 0):
    """Build a Timeline from delayed recipe steps (G5.8.8).

    Each delayed step becomes a TimelineEvent that appends
    the generated effect dicts to effects_target when its delay elapses.
    Steps with delay=0 are skipped (handled by play_recipe).

    Returns:
        Timeline instance ready for play() + tick(dt),
        or None if there are no delayed steps.
    """
    from src.core.timeline import Timeline
    _ensure_recipes_loaded()
    presets = _recipe_cache.get("presets", {})
    recipes = _recipe_cache.get("recipes", {})
    recipe = recipes.get(recipe_name)
    if not recipe:
        return None
    colors = presets.get(preset, presets.get("default", {}))
    tl = Timeline(f"recipe:{recipe_name}")
    has_delayed = False
    for step in recipe.get("steps", []):
        delay = step.get("delay", 0.0)
        if delay <= 0.0:
            continue
        has_delayed = True
        kind = step.get("kind", "pulse")
        clr = _resolve_recipe_step_color(kind, colors)
        dur = step.get("duration", 0.35)
        # Capture by-value to avoid late-binding closure bugs
        tl.add(delay, dur, _make_step_callback(
            step, cx, cy, clr, effects_target, direction, target_cx, target_cy))
    return tl if has_delayed else None


def _make_step_callback(step: dict, cx: int, cy: int, clr: tuple,
                        target: list, direction, target_cx: int, target_cy: int):
    """Return a callable that appends step effects to target, on invocation."""
    # Use shallow copies of mutable defaults for correct capture
    def _cb():
        effects = _make_step_effects(step, cx, cy, clr, direction, target_cx, target_cy)
        target.extend(effects)
    return _cb


def get_recipe_names() -> list[str]:
    """Return all available recipe names."""
    _ensure_recipes_loaded()
    return list(_recipe_cache.get("recipes", {}).keys())


def get_preset_names() -> list[str]:
    """Return all available preset names."""
    _ensure_recipes_loaded()
    return list(_recipe_cache.get("presets", {}).keys())
