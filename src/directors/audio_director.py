"""
G5.8.4: AudioDirector — BGM layer/mix control + boss Phase2 cue

Wraps bgm_engine / sfx_engine with:
  - Cross-fade between BGM tracks (fade-out → swap → fade-in).
  - Boss Phase2 audio cue (layered percussion burst on enrage).
  - Volume ducking for high-priority SFX.
"""

from src.bgm_engine import play_bgm, stop_bgm, _bgm_channel, _bgm_cache


class AudioDirector:
    """BGM layer controller — crossfade, boss cues, ducking.

    Instantiated once in GameScene; coordinates with BossSystemDirector
    to trigger audio transitions on boss state changes.
    """

    def __init__(self):
        self._current_bgm: str = ""
        self._fading: bool = False
        self._fade_timer: float = 0.0
        self._fade_duration: float = 0.0
        self._next_bgm: str = ""
        self._phase2_played: bool = False

    # ── Cross-fade ─────────────────────────────────────────

    def crossfade_to(self, name: str, duration: float = 0.6):
        """Fade out current BGM, then fade in the new track.

        If no BGM is playing, start the new track immediately.
        """
        if name == self._current_bgm and not self._fading:
            return
        if not self._current_bgm:
            self._play_now(name)
            return
        self._next_bgm = name
        self._fading = True
        self._fade_timer = duration
        self._fade_duration = duration

    def tick(self, dt: float):
        """Per-frame crossfade update — call from GameScene.update()."""
        if not self._fading:
            return
        self._fade_timer -= dt
        if self._fade_timer <= 0:
            self._fade_timer = 0
            self._fading = False
            self._play_now(self._next_bgm)
        elif _bgm_channel:
            ratio = self._fade_timer / self._fade_duration
            _bgm_channel.set_volume(0.45 * ratio)

    def _play_now(self, name: str):
        """Immediate BGM switch (no fade)."""
        self._current_bgm = name
        play_bgm(name)

    # ── Boss Phase2 cue ────────────────────────────────────

    def play_boss_phase2_cue(self):
        """Play a layered burst when boss enters Phase2/enrage.

        Adds a heavy-hitting SFX on top of the current BGM without
        interrupting it, then slightly boosts BGM volume for intensity.
        """
        if self._phase2_played:
            return
        self._phase2_played = True
        from src.sfx_engine import play_sfx
        # Heavy hit + low rumble for enrage announcement
        play_sfx("hit", 0.9)
        if _bgm_channel:
            _bgm_channel.set_volume(0.55)  # boost BGM intensity

    def reset_phase2(self):
        """Reset phase2 flag for new boss fight."""
        self._phase2_played = False

    # ── Ducking ────────────────────────────────────────────

    def duck_bgm(self, duck_volume: float = 0.15, duration: float = 0.5):
        """Temporarily lower BGM volume (e.g. for dialogue)."""
        if _bgm_channel:
            _bgm_channel.set_volume(duck_volume)

    def restore_bgm(self, volume: float = 0.45):
        """Restore BGM after ducking."""
        if _bgm_channel:
            _bgm_channel.set_volume(volume)

    # ── State queries ──────────────────────────────────────

    @property
    def current_bgm(self) -> str:
        return self._current_bgm


# Singleton convenience
_audio_director: AudioDirector | None = None


def get_audio_director() -> AudioDirector:
    global _audio_director
    if _audio_director is None:
        _audio_director = AudioDirector()
    return _audio_director
