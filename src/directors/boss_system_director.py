"""
BossSystemDirector — Boss 子系统统一生命周期管理 (D5)

接入: BossNarrative / Encounter / Timeline
"""

import time


class BossSystemDirector:
    """Boss 子系统编排器。"""

    def __init__(self):
        self.modifier_text = ""
        self.evolution_name = None
        self.current_cmd = 0
        self.battle_report = None
        self._spawn_time = 0.0
        self._phase2 = False
        self._last_stand = False
        self._dead = False
        self.dmg_done = 0
        self.dmg_taken = 0

    def reset(self):
        self._spawn_time = time.time()
        self._phase2 = False
        self._last_stand = False
        self._dead = False
        self.dmg_done = 0
        self.dmg_taken = 0

    def init_on_spawn(self, boss, floor: int, world_state=None,
                      build_type=None, rels=None, game_map=None):
        self.reset()
        boss_name = getattr(boss, 'name', '???')
        self.evolution_name = boss_name

    def tick(self, dt: float):
        pass

    def notify_phase2(self):
        self._phase2 = True

    def notify_last_stand(self):
        self._last_stand = True

    def notify_death(self):
        self._dead = True

    def total_time(self) -> float:
        return time.time() - self._spawn_time

    def is_phase2(self) -> bool:
        return self._phase2

    def is_last_stand(self) -> bool:
        return self._last_stand
