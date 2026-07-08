"""
Scene 基类 —— 轻量级生命周期管理。

每个场景对应一个游戏状态（标题/战斗/选关/教程/死亡/通关）。
引擎持有共享状态，场景通过 self.engine 访问。
"""


class Scene:
    """场景基类 —— 定义 enter / exit / update / render / on_keydown 生命周期。

    子类只需覆写需要的方法，不需要的留空即可。
    """

    def __init__(self, engine):
        """绑定引擎引用。

        参数：
            engine: GameEngine 实例，持有所有共享状态。
        """
        self.engine = engine

    def enter(self):
        """进入场景时调用一次。"""

    def exit(self):
        """离开场景时调用一次。"""

    def update(self, delta_time: float):
        """每帧更新逻辑。

        参数：
            delta_time: 上一帧耗时（秒）。
        """

    def render(self):
        """每帧渲染。"""

    def on_keydown(self, key: int):
        """按键事件分发。

        参数：
            key: pygame 按键常量。
        """

    @staticmethod
    def _clamp_cursor(cursor: int, item_count: int) -> int:
        """修正光标，防止越界。"""
        if item_count == 0:
            return 0
        return min(cursor, item_count - 1)
