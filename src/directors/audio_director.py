"""
G5.8.7: AudioDirector — BGM layer/mix control + unified SFX dispatch

Presentation consumers via on_presentation_event().
BGM: crossfade, ducking, boss phase2 intensity boost.
SFX: single entry point replacing direct play_sfx() calls.
"""

from src.bgm_engine import play_bgm, stop_bgm


class AudioDirector:
    """BGM layer controller — crossfade, boss cues, ducking.

    G5.8.7: on_presentation_event() is the unified audio dispatch.
    PresentationSystemDirector calls it; gameplay never touches audio directly.
    """

    def __init__(self):
        self._current_bgm: str = ""
        self._fading: bool = False
        self._fade_timer: float = 0.0
        self._fade_duration: float = 0.0
        self._next_bgm: str = ""
        self._phase2_played: bool = False

    # ── G5.8.7: Unified SFX entry ──────────────────────────

    def on_presentation_event(self, sfx: str, vol: float = 0.6):
        """Play a sound effect for a presentation event.

        G5.8.7: All SFX flows through this method.
        High-priority SFX (timestop) auto-ducks BGM.
        """
        if not sfx:
            return
        from src.sfx_engine import play_sfx
        # Timestop = full volume + duck BGM during playback
        if sfx == "timestop":
            self.duck_bgm(0.10)
            play_sfx(sfx, 1.0)
        else:
            # Heavy sounds duck BGM slightly
            if sfx in ("hit", "bolt", "ice_crack", "lightning", "slash"):
                self.duck_bgm(0.25, 0.15)
            play_sfx(sfx, vol)

    # ── Cross-fade ─────────────────────────────────────────

    def crossfade_to(self, name: str, duration: float = 0.6):
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
        if not self._fading:
            return
        self._fade_timer -= dt
        if self._fade_timer <= 0:
            self._fade_timer = 0
            self._fading = False
            self._play_now(self._next_bgm)
        else:
            self._ramp_bgm_volume(0.45 * (self._fade_timer / self._fade_duration))

    def _play_now(self, name: str):
        self._current_bgm = name
        play_bgm(name)

    def _ramp_bgm_volume(self, vol: float):
        """Set BGM channel volume (internal — avoids direct _bgm_channel access)."""
        from src.bgm_engine import _bgm_channel
        if _bgm_channel:
            _bgm_channel.set_volume(vol)

    # ── Boss Phase2 cue ────────────────────────────────────

    def play_boss_phase2_cue(self):
        if self._phase2_played:
            return
        self._phase2_played = True
        self.on_presentation_event("hit", 0.9)
        self._ramp_bgm_volume(0.55)

    def reset_phase2(self):
        self._phase2_played = False

    # ── Ducking ────────────────────────────────────────────

    def duck_bgm(self, duck_volume: float = 0.15, duration: float = 0.5):
        self._ramp_bgm_volume(duck_volume)

    def restore_bgm(self, volume: float = 0.45):
        self._ramp_bgm_volume(volume)

    # ── State queries ──────────────────────────────────────

    @property
    def current_bgm(self) -> str:
        return self._current_bgm


# Singleton
_audio_director: AudioDirector | None = None


def get_audio_director() -> AudioDirector:
    global _audio_director
    if _audio_director is None:
        _audio_director = AudioDirector()
    return _audio_director
