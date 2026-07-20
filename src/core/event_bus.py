"""
G6 sync: EventBus — global pub/sub event system (C++ parity)
30 event types, subscribe/unsubscribe/emit pattern
"""
from enum import Enum, auto
from collections import defaultdict
from typing import Callable, Any


class GameEventType(Enum):
    NONE = 0
    PLAYER_ATTACK = auto(); PLAYER_DAMAGED = auto(); PLAYER_DEAD = auto()
    PLAYER_LEVEL_UP = auto()
    MONSTER_SPAWN = auto(); MONSTER_DIED = auto()
    BOSS_SPAWN = auto(); BOSS_PHASE2 = auto(); BOSS_LAST_STAND = auto(); BOSS_DEAD = auto()
    ITEM_PICKUP = auto(); ITEM_USE = auto(); RELIC_GAIN = auto()
    ATTACK_EVOLVED = auto()
    SKILL_EVOLVED = auto()
    BOSS_RULE_ACTIVATED = auto()
    BUFF_APPLIED = auto(); BUFF_EXPIRED = auto()
    SPECIAL_ROOM_ENTER = auto(); SPECIAL_ROOM_TRIGGER = auto()
    NPC_DIALOGUE_START = auto(); NPC_DIALOGUE_END = auto()
    QUEST_ACCEPT = auto(); QUEST_COMPLETE = auto()
    FLOOR_ENTER = auto(); FLOOR_CLEAR = auto()
    GAME_CLEAR = auto(); GAME_OVER = auto()
    ENDING_REACHED = auto(); META_GAIN = auto()


class GameEvent:
    """Lightweight event data (matching C++ GameEvent struct)."""
    __slots__ = ('type','sender','int_val','float_val','str_val')
    def __init__(self, etype=GameEventType.NONE, sender=None, int_val=0, float_val=0.0, str_val=None):
        self.type = etype; self.sender = sender
        self.int_val = int_val; self.float_val = float_val; self.str_val = str_val


EventCallback = Callable[[GameEvent], None]


class EventBus:
    """Singleton global event bus — decouples gameplay from presentation."""
    _instance = None

    def __new__(cls):
        if cls._instance is None: cls._instance = super().__new__(cls); cls._instance._init()
        return cls._instance

    def _init(self):
        self._listeners: dict[int, list[tuple[EventCallback, str]]] = defaultdict(list)

    def subscribe(self, etype: GameEventType, cb: EventCallback, name: str = ""):
        self._listeners[etype.value].append((cb, name))

    def unsubscribe(self, etype: GameEventType, cb: EventCallback):
        lst = self._listeners.get(etype.value)
        if lst: self._listeners[etype.value] = [(c, n) for c, n in lst if c is not cb]

    def emit(self, ev: GameEvent):
        for cb, _ in self._listeners.get(ev.type.value, []):
            try: cb(ev)
            except Exception: pass  # subscriber errors should not crash the bus

    def emit_simple(self, etype: GameEventType, sender=None, int_val=0, float_val=0.0, str_val=None):
        self.emit(GameEvent(etype, sender, int_val, float_val, str_val))

    def clear(self):
        self._listeners.clear()

    def listener_count(self, etype: GameEventType) -> int:
        return len(self._listeners.get(etype.value, []))

    @staticmethod
    def inst() -> 'EventBus':
        return EventBus()
