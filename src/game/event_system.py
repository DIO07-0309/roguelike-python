"""
D4: EventSystem — 动态事件类型与执行

与 C++ event_system.h/.cpp 一致。
"""

import random
from enum import Enum, auto


class EventType(Enum):
    NONE = 0
    AMBUSH = auto()         # 伏击
    CURSED_ROOM = auto()    # 诅咒房间
    BLOOD_RITUAL = auto()   # 血祭仪式
    LOST_CAMP = auto()      # 迷失营地
    TREASURE_GUARD = auto()  # 宝库守卫
    MERCHANT = auto()       # 旅行商人
    ALTAR_CHOICE = auto()   # 三选祭坛
    STATUE = auto()         # 神秘雕像
    PRISONER = auto()       # 囚犯
    NOTHING = auto()        # 寂静房间


_EVENT_NAMES = {
    EventType.AMBUSH: "伏击!",
    EventType.CURSED_ROOM: "诅咒房间",
    EventType.BLOOD_RITUAL: "血祭仪式",
    EventType.LOST_CAMP: "迷失营地",
    EventType.TREASURE_GUARD: "宝库守卫",
    EventType.MERCHANT: "旅行商人",
    EventType.ALTAR_CHOICE: "三选祭坛",
    EventType.STATUE: "神秘雕像",
    EventType.PRISONER: "囚犯",
    EventType.NOTHING: "寂静房间",
}


def event_type_name(et: EventType) -> str:
    return _EVENT_NAMES.get(et, "???")


_EVENT_POOLS: dict[EventType, list[str]] = {
    EventType.MERCHANT: [
        "一个褴褛的商人从阴影中走出，背包叮当作响。",
        "商贩推着一辆破旧的推车，里面装满了奇怪的货物。",
        '"欢迎！" 一个苍老的声音从角落传来。',
    ],
    EventType.AMBUSH: [
        "脚步声从四面八方涌来——这是埋伏！",
        "天花板上的碎石突然落下，一群怪物从暗处冲出！",
    ],
    EventType.CURSED_ROOM: [
        "空气中弥漫着古老的诅咒气息。",
        "墙壁上刻满了扭曲的符文，散发着暗紫色的光芒。",
    ],
    EventType.ALTAR_CHOICE: [
        "三束光芒从古老祭坛中升起。",
    ],
    EventType.STATUE: [
        "一座古老的雕像矗立在房间中央，散发着微弱的光。",
    ],
    EventType.PRISONER: [
        "铁栏杆后蜷缩着一个身影。",
    ],
    EventType.LOST_CAMP: [
        "一个废弃的营地在角落散发着温暖的篝火余烬。",
    ],
    EventType.TREASURE_GUARD: [
        "巨大的宝箱被一只沉睡的怪物守护着。",
    ],
    EventType.BLOOD_RITUAL: [
        "一个腥红色的祭坛在房间中央滴着血。",
    ],
    EventType.NOTHING: [
        "这间房间空无一物，只有风吹过缝隙的声音。",
    ],
}


def event_text_pool(event_idx: int) -> list[str]:
    """返回事件描述文字池。"""
    et = list(EventType)[event_idx + 1] if 0 <= event_idx < len(EventType) - 1 else EventType.NOTHING
    return _EVENT_POOLS.get(et, ["???"])


def generate_event(chapter: int, rng=None) -> 'DungeonEvent':
    """按章节生成随机事件。"""
    r = rng if rng else random
    pool = list(EventType)[1:]  # skip NONE
    # 权重: 不同章节有不同事件分布
    weights = [10] * len(pool)
    et = r.choices(pool, weights=weights, k=1)[0]
    return DungeonEvent(type=et)


class DungeonEvent:
    def __init__(self, type: EventType = EventType.NONE):
        self.type = type
        self.triggered = False