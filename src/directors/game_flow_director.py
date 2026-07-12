"""
GameFlowDirector — 场景流程 / 游戏结束 / 通关编排 (D1-D6)

接入: Ending / Victory / Death / Credits 流程
"""


class GameFlowDirector:
    """游戏流程编排器。"""

    def __init__(self):
        self._scene = None

    def bind(self, scene):
        """绑定到 GameScene 实例。"""
        self._scene = scene

    def new_game(self):
        pass

    def load_game(self, floor: int, max_floor: int, player_obj,
                  seed: int = 0, spr: list = None, spd: list = None):
        pass

    def on_boss_intro_confirm(self):
        pass

    def on_player_dead(self):
        """玩家死亡 → 死亡画面。"""
        from src.game.ending_director import g_ending_director
        ending = g_ending_director.ending_name()

    def on_game_clear(self):
        """通关 → 胜利画面 / 结局。"""
        from src.game.ending_director import g_ending_director
        ending = g_ending_director.ending_name()
