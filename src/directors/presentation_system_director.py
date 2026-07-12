"""
PresentationSystemDirector — 视觉表现层统一管理 (D1-D6)

接入: FloorIntro / ChapterIntro / RoomMessage / RelicMessage
"""


class PresentationSystemDirector:
    """视觉演出编排器。"""

    def __init__(self):
        self.damage_floats: list = []
        self.shake_timer: float = 0.0
        self.shake_intensity: float = 0.0
        self.freeze_timer: float = 0.0
        self.room_msg: str = ""
        self.room_msg_timer: float = 0.0
        self.boss_intro_text: str = ""
        self.boss_modifier_text: str = ""
        self.floor_intro_active: bool = False
        self.floor_intro_timer: float = 0.0
        self.floor_intro_fade: float = 0.0
        self.floor_intro_floor: int = 0
        self.chapter_intro_active: bool = False
        self.chapter_intro_timer: float = 0.0
        self.chapter_intro_ch: int = 0
        self.show_growth_debug: bool = False
        self.show_flow_debug: bool = False
        self.show_boss_behavior: bool = False
        self.show_boss_cmd: bool = False
        self.show_boss_report: bool = False
        self.combat_juice_on: bool = True

    def tick(self, dt: float):
        """逐帧更新所有视觉元素。"""
        if self.room_msg_timer > 0:
            self.room_msg_timer -= dt
            if self.room_msg_timer <= 0:
                self.room_msg_timer = 0
                self.room_msg = ""

        if self.floor_intro_active:
            self.floor_intro_timer -= dt
            self.floor_intro_fade = min(1.0, self.floor_intro_fade + dt * 2.5)
            if self.floor_intro_timer <= 0:
                self.floor_intro_active = False

        if self.chapter_intro_active:
            self.chapter_intro_timer -= dt
            if self.chapter_intro_timer <= 0:
                self.chapter_intro_active = False

        # 伤害数字衰减
        for df in self.damage_floats:
            df["lifetime"] -= dt
        self.damage_floats = [d for d in self.damage_floats if d["lifetime"] > 0]

        # 震动衰减
        if self.shake_timer > 0:
            self.shake_timer -= dt

    def spawn_damage(self, x: float, y: float, value: int,
                     color=(255, 255, 255), is_magic: bool = False):
        self.damage_floats.append({
            "x": x, "y": y, "value": value, "color": color,
            "lifetime": 0.6, "is_magic": is_magic
        })

    def trigger_shake(self, intensity: float):
        self.shake_intensity = intensity
        self.shake_timer = 0.12

    def trigger_freeze(self, duration: float):
        self.freeze_timer = duration

    def show_message(self, msg: str, duration: float = 2.0):
        """显示房间消息 toast，自动处理 RELIC 前缀 (金色)。"""
        self.room_msg = msg
        self.room_msg_timer = duration

    def show_relic_message(self, relic_name: str):
        """显示 relic 获得消息 (带 RELIC: 前缀)。"""
        self.show_message(f"RELIC:{relic_name}", 3.5)

    def is_room_msg_active(self) -> bool:
        return self.room_msg_timer > 0 and bool(self.room_msg)

    def is_intro_active(self) -> bool:
        return self.floor_intro_active or self.chapter_intro_active
