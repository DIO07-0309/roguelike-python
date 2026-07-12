"""
GameplaySystemDirector — 世界/叙事/任务/结局 生命周期管理 (D1-D6)

接入: WorldState / BuildScore / Narrative / Ending / Meta / GrowthCurve
"""

import random
from src.game.floor_config import NarrativeState, pick_random_narration
from src.game.world_state import WorldState
from src.game.build_score import BuildType, calculate_build
from src.game.meta_progression import RunSummary, g_meta
from src.game.growth_curve import g_growth


class GameplaySystemDirector:
    """世界状态与长期叙事编排器。"""

    def __init__(self):
        self.world_state = WorldState()
        self.run_stats = RunSummary()
        self.narr_state = NarrativeState()
        self.last_notified_build = None
        self.flow = None  # 外部注入

    # ── 生命周期 ──

    def on_new_game(self):
        self.world_state.reset()
        self.run_stats = RunSummary()
        self.narr_state = NarrativeState()
        self.last_notified_build = None

    def on_enter_floor(self, floor: int):
        self.narr_state.floor_intro_played[floor - 1] = True
        self.narr_state.narration_timer = 25.0 + random.uniform(0, 15)
        self.run_stats.floors_reached = max(self.run_stats.floors_reached, floor)

    def tick(self, dt: float):
        if self.narr_state.narration_timer > 0:
            self.narr_state.narration_timer -= dt

    def tick_narration(self, current_floor: int, is_boss: bool,
                       is_event_running: bool, inventory_open: bool,
                       state: str) -> str | None:
        if (self.narr_state.narration_timer > 0 or is_boss
                or is_event_running or inventory_open or state != "playing"):
            return None
        nar = pick_random_narration(current_floor, self.narr_state)
        self.narr_state.narration_timer = 25.0 + random.uniform(0, 15)
        return nar

    def check_build_change(self, player) -> str | None:
        """检测构筑变化，返回提示文字。"""
        bs = calculate_build(player)
        bt = bs.identify()
        if bt != BuildType.NONE and bt != self.last_notified_build:
            prev = self.last_notified_build
            self.last_notified_build = bt
            if prev is None or prev == BuildType.NONE:
                return f"BUILD COMPLETE! {bs.build_name()}"
            return f"BUILD CHANGED: {bs.build_name()}"
        return None

    def on_player_dead(self, current_floor: int, player_level: int,
                       player=None):
        # 统计结算
        g_meta.end_run(self.run_stats)
        # 结局判定
        from src.game.ending_director import g_ending_director
        all_bosses = (self.world_state.has(15))  # Boss3 defeated
        g_ending_director.evaluate(self.world_state, 0.0, all_bosses, current_floor)

    def on_game_clear(self, current_floor: int, player_level: int,
                      player=None, battle_report=None, collection_pct: float = 0.0):
        from src.systems.relic_archive import g_relic_archive
        self.run_stats.relics_collected = g_relic_archive.collected_count()
        g_meta.end_run(self.run_stats)
        # 结局判定
        from src.game.ending_director import g_ending_director
        from src.game.world_state import WorldFlag
        all_bosses = self.world_state.has(WorldFlag.All_Boss_Defeated) or True
        g_ending_director.evaluate(self.world_state, collection_pct,
                                    all_bosses, current_floor)
