"""
G5.8.6: Timeline Recipe — delay + duration + include

A lightweight sequenced-event system for choreographing VFX, audio,
and camera effects over time. Designed for boss intros, level-up
ceremonies, and other multi-step presentations.

Pattern:
    tl = Timeline("boss_intro")
    tl.add(0.0, 1.0, lambda: play_sfx("hit"))
    tl.add(0.5, 0.5, lambda: trigger_shake(8))
    tl.include("boss_phase2_vfx", offset=0.3)
    tl.play()
    # ... in update loop: tl.tick(dt)
"""

from collections import OrderedDict
from typing import Callable


class TimelineEvent:
    """Single timed action within a Timeline.

    Fields:
        delay:    seconds from timeline start before this fires.
        duration: how long the effect lasts (informational, for recipes).
        callback: callable invoked when delay is reached.
        fired:    internal — True after callback has been invoked.
    """
    __slots__ = ('delay', 'duration', 'callback', 'fired')

    def __init__(self, delay: float, duration: float, callback: Callable[[], None]):
        self.delay = delay
        self.duration = duration
        self.callback = callback
        self.fired = False


class Timeline:
    """A sequence of TimelineEvents that advance with elapsed time.

    Usage:
        tl = Timeline("level_up")
        tl.add(0.0, 0.5, lambda: spawn_vfx("pulse", cx, cy))
        tl.add(0.3, 0.5, lambda: spawn_vfx("spark", cx, cy))
        tl.play()

        # in game loop:
        tl.tick(dt)
        if tl.is_finished():
            # all events fired
    """

    def __init__(self, name: str = ""):
        self.name = name
        self._events: list[TimelineEvent] = []
        self._elapsed: float = 0.0
        self._playing: bool = False
        self._total_duration: float = 0.0

    # ── Building ───────────────────────────────────────────

    def add(self, delay: float, duration: float, callback: Callable[[], None]):
        """Add a single event at `delay` seconds from start."""
        ev = TimelineEvent(delay, duration, callback)
        self._events.append(ev)
        self._events.sort(key=lambda e: e.delay)
        end = delay + duration
        if end > self._total_duration:
            self._total_duration = end

    def include(self, other: "Timeline", offset: float = 0.0):
        """Include all events from another Timeline, shifted by `offset`."""
        for ev in other._events:
            self.add(ev.delay + offset, ev.duration, ev.callback)

    # ── Playback ───────────────────────────────────────────

    def play(self):
        """Start or restart the timeline."""
        self._elapsed = 0.0
        self._playing = True
        for ev in self._events:
            ev.fired = False

    def tick(self, dt: float):
        """Advance timeline — fires any callbacks whose delay has elapsed."""
        if not self._playing:
            return
        self._elapsed += dt
        for ev in self._events:
            if not ev.fired and self._elapsed >= ev.delay:
                ev.fired = True
                try:
                    ev.callback()
                except Exception:
                    pass  # one bad callback shouldn't break the timeline

    def stop(self):
        """Stop without firing remaining events."""
        self._playing = False

    # ── Queries ────────────────────────────────────────────

    def is_finished(self) -> bool:
        """True when all events have fired."""
        return self._playing and all(ev.fired for ev in self._events)

    def is_playing(self) -> bool:
        return self._playing

    @property
    def total_duration(self) -> float:
        return self._total_duration

    @property
    def elapsed(self) -> float:
        return self._elapsed


# ══════════════════════════════════════════════════════════════
#  Timeline Recipe Registry — named presets
# ══════════════════════════════════════════════════════════════

_timeline_recipes: dict[str, Callable[[], Timeline]] = {}


def register_timeline_recipe(name: str, factory: Callable[[], Timeline]):
    """Register a named timeline factory that can be played by name."""
    _timeline_recipes[name] = factory


def get_timeline_recipe(name: str) -> Timeline | None:
    """Get a fresh instance of a named recipe timeline."""
    factory = _timeline_recipes.get(name)
    if factory:
        return factory()
    return None


def get_registered_recipes() -> list[str]:
    return list(_timeline_recipes.keys())


# ══════════════════════════════════════════════════════════════
#  Built-in recipes
# ══════════════════════════════════════════════════════════════

def _make_boss_intro_timeline(scene) -> Timeline:
    """Boss intro sequence: shake → VFX burst → sound."""
    tl = Timeline("boss_intro")
    tl.add(0.0, 0.15, lambda: scene.presentation.trigger_shake(6))
    tl.add(0.15, 0.35, lambda: scene.engine._attack_effects.extend(
        __import__("src.fx_engine", fromlist=["play_recipe"]).play_recipe(
            "boss_phase2", 480, 320, preset="fire")))
    tl.add(0.0, 0.4, lambda: __import__("src.sfx_engine", fromlist=["play_sfx"]).play_sfx("hit", 0.9))
    return tl


def _make_level_up_timeline(scene) -> Timeline:
    """Level-up sequence: sparkle VFX + sound."""
    tl = Timeline("level_up")
    pl = scene.engine.player
    cx = pl.entity.rect.centerx if pl else 480
    cy = pl.entity.rect.centery if pl else 320
    tl.add(0.0, 0.4, lambda: scene.engine._attack_effects.extend(
        __import__("src.fx_engine", fromlist=["play_recipe"]).play_recipe(
            "level_up", cx, cy, preset="heal")))
    tl.add(0.0, 0.5, lambda: __import__("src.sfx_engine", fromlist=["play_sfx"]).play_sfx("levelup", 0.8))
    return tl


register_timeline_recipe("boss_intro", lambda scene=None:
    _make_boss_intro_timeline(scene) if scene else Timeline("boss_intro"))
register_timeline_recipe("level_up", lambda scene=None:
    _make_level_up_timeline(scene) if scene else Timeline("level_up"))

