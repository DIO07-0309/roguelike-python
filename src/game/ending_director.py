"""
D6: EndingDirector — 结局判定系统

根据 WorldState + Boss 击杀 + NPC 关系推断结局类型。
与 C++ ending_director.h/.cpp 一致。
"""

from enum import Enum, auto


class EndingType(Enum):
    BAD_END = auto()       # 深红: 什么都没做就死了
    NORMAL_END = auto()    # 灰暗: 击败Boss但走黑暗路线
    GOOD_END = auto()      # 金色: 完成主要任务
    TRUE_END = auto()      # 纯白: 完美路线
    SECRET_END = auto()    # 彩虹: 隐藏结局


_ENDING_NAMES = {
    EndingType.BAD_END: "深红",
    EndingType.NORMAL_END: "灰暗",
    EndingType.GOOD_END: "金色",
    EndingType.TRUE_END: "纯白",
    EndingType.SECRET_END: "彩虹",
}


_ENDING_DESCRIPTIONS = {
    EndingType.BAD_END:
        "黑暗吞噬了一切。你在深渊中迷失——成为了它新的狱卒。",
    EndingType.NORMAL_END:
        "深渊之主倒下了。黑暗开始褪去——但你已被地牢改变，再也无法回到从前。",
    EndingType.GOOD_END:
        "你救下了能够拯救的灵魂。神殿重新亮起了光——虽然微弱，但足以指引后人。",
    EndingType.TRUE_END:
        "你战胜了深渊，也战胜了自己。守望者的祈祷穿越三千年，终于得到了回应。你自由了——真正的自由。",
    EndingType.SECRET_END:
        "你做到了凡人不可能做到的事。每一座神殿的灯火都被重新点燃。守望者流泪了——三千年来的第一滴泪。",
}


class EndingDirector:
    """结局判定器。"""

    def __init__(self):
        self._type = EndingType.BAD_END
        self._debug_override = None

    def evaluate(self, world_state, collection_pct: float,
                 all_bosses: bool, floors_reached: int) -> EndingType:
        """根据世界状态判定结局类型。"""
        if self._debug_override:
            return self._debug_override

        from src.game.world_state import WorldFlag

        # SECRET: 全收集 + 完美路线
        if (collection_pct >= 0.90 and all_bosses
                and world_state.has(WorldFlag.Saved_Prisoner)
                and world_state.has(WorldFlag.Saved_Priest)
                and world_state.has(WorldFlag.Met_Watcher)
                and not world_state.has(WorldFlag.Accepted_Curse)
                and not world_state.has(WorldFlag.Blood_Ritual)):
            return EndingType.SECRET_END

        # TRUE: 全Boss + 不诅咒 + 不血祭 + 好感
        if (all_bosses
                and not world_state.has(WorldFlag.Accepted_Curse)
                and not world_state.has(WorldFlag.Blood_Ritual)
                and not world_state.has(WorldFlag.Merchant_Killed)):
            return EndingType.TRUE_END

        # GOOD: 击败了最终Boss
        if all_bosses:
            return EndingType.GOOD_END

        # NORMAL: 至少打到了10层
        if floors_reached >= 10:
            return EndingType.NORMAL_END

        return EndingType.BAD_END

    def ending_type(self) -> EndingType:
        return self._type

    def ending_name(self) -> str:
        return _ENDING_NAMES.get(self._type, "???")

    def ending_description(self) -> str:
        return _ENDING_DESCRIPTIONS.get(self._type, "")

    def debug_override(self, et: EndingType):
        self._debug_override = et


# 全局单例
g_ending_director = EndingDirector()
