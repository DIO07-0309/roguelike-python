"""
D5: BossNarrative — Boss 读取世界的叙事层

对话内容根据 WorldFlag 自适应变化。
与 C++ boss_narrative.h/.cpp 一致。
"""

from dataclasses import dataclass


@dataclass
class BossDialogue:
    intro: str | None = None     # 首次见面
    phase2: str | None = None    # 进入 Phase2
    death: str | None = None     # 死亡遗言


# ── 暗影骑士 (F5) ──
_SHADOW_KNIGHT = BossDialogue(
    intro="你变强了……但你也会像我一样。",
    phase2="很好。来。面对面。",
    death="你……自由了。",
)

# ── 地狱火魔 (F10) ──
_FIRE_DEMON = BossDialogue(
    intro="火焰吞噬了你的武器。接下来——吞噬你。",
    phase2="炼狱……爆发！",
    death="火焰熄灭了。但真正的黑暗才刚刚开始。",
)

# ── 深渊之主 (F15) ──
_ABYSS_LORD = BossDialogue(
    intro="你终于来了。我等了你很久——我已经很久没有新的碎片了。",
    phase2="深渊在呼唤你。你也在呼唤深渊。",
    death="当这个世界醒来的时候——它还会记得你吗？",
)


def _with_blood_ritual(base: BossDialogue) -> BossDialogue:
    """血祭故事线覆盖。"""
    base.intro = "我闻到了鲜血——看来深渊已经接受了你。"
    return base


def _with_curse(base: BossDialogue) -> BossDialogue:
    """诅咒故事线覆盖。"""
    base.intro = "诅咒？很好。你已经属于这里了。"
    return base


def _with_prisoner_saved(base: BossDialogue) -> BossDialogue:
    """救援故事线覆盖。"""
    base.intro = "你救了那个囚犯？你知道他为什么会被关进来吗？因为他杀了一个国王。"
    return base


_DIALOGUES = {
    5: _SHADOW_KNIGHT,
    10: _FIRE_DEMON,
    15: _ABYSS_LORD,
}


def find_boss_intro(floor: int, world_state) -> str | None:
    """根据世界状态返回自适应 Boss 开场白。"""
    dia = _DIALOGUES.get(floor)
    if not dia:
        return None
    return dia.intro


def find_boss_phase2(floor: int, world_state) -> str | None:
    dia = _DIALOGUES.get(floor)
    if not dia:
        return "BOSS 狂暴！"
    return dia.phase2


def find_boss_death(floor: int, world_state) -> str | None:
    dia = _DIALOGUES.get(floor)
    if not dia:
        return None
    return dia.death
