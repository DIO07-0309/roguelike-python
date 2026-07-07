"""
──────────────────────────────────────────
技能系统 —— 主动技能 / 被动技能 / 冷却 / 升级
──────────────────────────────────────────

职责：
  - 定义技能基类和两种子类型（主动/被动）。
  - 提供 3 个具体主动技能（斩击/神罚/自愈）+ 1 个被动技能（铁壁）。
  - SkillManager 管理技能的习得/释放/升级。

设计原则：
  - 技能是可组合的独立对象，不嵌入 Player 类。
  - 新增技能只需继承 ActiveSkill/PassiveSkill 并实现 execute/apply。
  - 冷却和升级逻辑在基类统一处理，子类只关心里不同的效果。
"""

import math
import random
import pygame
from src.entities.components import AttackType


class Skill:
    """技能抽象基类 —— 冷却管理 + 升级框架。

    属性：
        name: 技能名称。
        cooldown: 基础冷却时间（秒）。
        level: 当前等级（≥1）。
        max_level: 最大等级。
        icon_char: 显示用单字符图标。
        _last_use_time: 上次释放的游戏时间戳。
    """

    def __init__(self, name: str, cooldown: float,
                 max_level: int = 5, icon_char: str = '?'):
        """创建技能。"""
        self.name = name
        self._base_cooldown = cooldown
        self.cooldown = cooldown
        self.level = 1
        self.max_level = max_level
        self.icon_char = icon_char
        self._last_use_time = -999.0
        # 护符修正
        self._charm_cd_bonus = 0.0
        self._charm_power_bonus = 0.0

    # =========================================================
    #  冷却与状态
    # =========================================================

    def can_use(self, game_time: float) -> bool:
        """冷却是否就绪。

        参数：
            game_time: 当前游戏时间戳。

        返回：
            True 表示可以释放。
        """
        return (game_time - self._last_use_time) >= self.cooldown

    def remaining_cooldown(self, game_time: float) -> float:
        """剩余冷却时间（秒）。

        参数：
            game_time: 当前游戏时间戳。

        返回：
            剩余秒数，0 表示就绪。
        """
        elapsed = game_time - self._last_use_time
        return max(0.0, self.cooldown - elapsed)

    def mark_used(self, game_time: float):
        """记录本次释放时间。

        参数：
            game_time: 当前游戏时间戳。
        """
        self._last_use_time = game_time

    # =========================================================
    #  升级
    # =========================================================

    def can_upgrade(self) -> bool:
        """是否还可以升级。"""
        return self.level < self.max_level

    def upgrade(self) -> bool:
        """升级技能 —— 3 级体系，每级效果跃升。"""
        if not self.can_upgrade():
            return False
        self.level += 1
        self._on_level_up()
        return True

    def _on_level_up(self):
        """升级回调 —— 子类覆写以应用具体数值变化。"""
        self._base_cooldown = max(0.15, self._base_cooldown * 0.8)
        self._recalc_cooldown()

    def _recalc_cooldown(self):
        self.cooldown = max(0.1, self._base_cooldown * (1.0 - self._charm_cd_bonus))

    def get_power_multiplier(self) -> float:
        """3 级倍率: Lv1=1.0, Lv2=1.4, Lv3=2.0"""
        return {1: 1.0, 2: 1.4, 3: 2.0}[self.level] * (1.0 + self._charm_power_bonus)

    def get_level_bonus_text(self) -> str:
        """返回当前等级的效果描述文本（子类覆写）。"""
        return f"Lv{self.level} 倍率×{self.get_power_multiplier():.1f}"

    def apply_charm(self, cd_bonus: float, power_bonus: float):
        """护符穿戴时调用：设置额外加成。"""
        self._charm_cd_bonus = cd_bonus
        self._charm_power_bonus = power_bonus
        self._recalc_cooldown()

    def remove_charm(self):
        """卸下护符时调用：清除加成。"""
        self._charm_cd_bonus = 0.0
        self._charm_power_bonus = 0.0
        self._recalc_cooldown()


class ActiveSkill(Skill):
    """主动技能 —— 按键释放，有即时效果。

    子类必须覆写 execute() 实现具体效果。
    """

    def __init__(self, name: str, cooldown: float, max_level: int = 5,
                 icon_char: str = 'A', description: str = ""):
        """创建主动技能。

        参数：
            name, cooldown, max_level, icon_char: 见基类。
            description: 效果描述文本。
        """
        super().__init__(name, cooldown, max_level, icon_char)
        self.description = description

    def execute(self, caster, targets: list, game_map) -> str:
        """执行技能效果（子类覆写）。

        参数：
            caster: 释放者（玩家）。
            targets: 目标列表（怪物）。
            game_map: 地图对象（范围技能需要）。

        返回：
            效果描述文本（用于消息日志）。
        """
        raise NotImplementedError


class PassiveSkill(Skill):
    """被动技能 —— 习得后常驻生效，写入 modifiers。"""

    def __init__(self, name: str, modifier_key: str, base_value: int,
                 max_level: int = 3, icon_char: str = 'P'):
        super().__init__(name, cooldown=0, max_level=max_level,
                         icon_char=icon_char)
        self.modifier_key = modifier_key
        self.base_value = base_value

    def _on_level_up(self):
        # 被动技能不涉及冷却修改
        pass

    def get_value(self) -> int:
        """根据等级返回当前加成值（子类覆写）。"""
        return int(self.base_value * self.get_power_multiplier())

    def apply(self, player):
        value = self.get_value()
        player.combat.modifiers[self.modifier_key] = (
            player.combat.modifiers.get(self.modifier_key, 0) + value)

    def remove(self, player):
        value = self.get_value()
        player.combat.modifiers[self.modifier_key] = (
            player.combat.modifiers.get(self.modifier_key, 0) - value)


# =========================================================
#  具体主动技能
# =========================================================

class SlashSkill(ActiveSkill):
    """斩击 —— 3 级：Lv1扇形 / Lv2范围+1 / Lv3二连击。"""

    def __init__(self):
        super().__init__(
            name="斩击", cooldown=2.0, max_level=3,
            icon_char='S', description="前方扇形范围伤害",
        )
        self._cone_range = 1
        from src.systems.buff_system import BuffTrigger, BuffTarget
        self.triggers = [BuffTrigger("poison", 1, 0.30, BuffTarget.ENEMY)]

    def _on_level_up(self):
        if self.level == 2:
            self._base_cooldown = 1.6
            self._cone_range = 2
        elif self.level == 3:
            self._base_cooldown = 1.2
            self._cone_range = 2
        self._recalc_cooldown()

    def execute(self, caster, targets: list, game_map) -> str:
        from src.systems.skill_system import get_targets_in_cone
        hit_list = get_targets_in_cone(caster, targets, self._cone_range)
        if not hit_list:
            return "斩击挥空了（无目标）"
        total_dmg = 0
        base_dmg = int(caster.combat.get_effective_attack() * 1.5)
        power = self.get_power_multiplier()
        from src.systems.combat_system import calculate_damage
        # Lv3：二连击
        hits_per_target = 2 if self.level >= 3 else 1
        for target in hit_list:
            for _ in range(hits_per_target):
                dmg = calculate_damage(
                    int(base_dmg * power),
                    target.combat.get_effective_defense(AttackType.PHYSICAL),
                    AttackType.PHYSICAL)
                target.combat.take_damage(dmg)
                total_dmg += dmg
        # Buff 触发
        from src.systems.buff_system import apply_triggers
        for t in hit_list:
            apply_triggers(self.triggers, caster, t)
        desc = f"斩击Lv{self.level} 命中 {len(hit_list)} 目标"
        desc += "（二连击）" if hits_per_target > 1 else ""
        return f"{desc}，造成 {total_dmg} 点伤害"

    def get_level_bonus_text(self) -> str:
        r = self._cone_range
        double = "·二连击" if self.level >= 3 else ""
        return f"Lv{self.level} 范围{r}格 {self.cooldown:.1f}s{double}"


class FireballSkill(ActiveSkill):
    """神罚 —— 3 级：Lv1单体 / Lv2双目标 / Lv3三目标。"""

    def __init__(self):
        super().__init__(
            name="神罚", cooldown=5.0, max_level=3,
            icon_char='F', description="远程多目标魔法",
        )
        self._target_count = 1
        self._range = 6.0
        from src.systems.buff_system import BuffTrigger, BuffTarget
        self.triggers = [BuffTrigger("slow", 1, 0.25, BuffTarget.ENEMY)]

    def _on_level_up(self):
        if self.level == 2:
            self._base_cooldown = 4.0
            self._target_count = 2
            self._range = 7.0
        elif self.level == 3:
            self._base_cooldown = 3.0
            self._target_count = 3
            self._range = 8.0
        self._recalc_cooldown()

    def execute(self, caster, targets: list, game_map) -> str:
        from src.systems.combat_system import find_attack_target
        # 按距离排序取前 N 个
        alive = [t for t in targets if hasattr(t, "entity") and t.combat.is_alive]
        alive.sort(key=lambda t: math.hypot(
            caster.entity.rect.centerx - t.entity.rect.centerx,
            caster.entity.rect.centery - t.entity.rect.centery))
        chosen = alive[:self._target_count]
        chosen = [t for t in chosen if math.hypot(
            caster.entity.rect.centerx - t.entity.rect.centerx,
            caster.entity.rect.centery - t.entity.rect.centery
            ) <= self._range * 32]
        if not chosen:
            return "神罚没有击中任何目标"
        base_dmg = int(caster.combat.get_effective_attack() * 2.5)
        power = self.get_power_multiplier()
        from src.systems.combat_system import calculate_damage
        total_dmg = 0
        for t in chosen:
            dmg = calculate_damage(
                int(base_dmg * power),
                t.combat.get_effective_defense(AttackType.MAGICAL),
                AttackType.MAGICAL)
            t.combat.take_damage(dmg)
            total_dmg += dmg
        # Buff 触发: 对最近目标附 slow
        from src.systems.buff_system import apply_triggers
        if chosen:
            apply_triggers(self.triggers, caster, chosen[0])
        return f"神罚Lv{self.level} 命中 {len(chosen)} 目标，造成 {total_dmg} 伤害"

    def get_level_bonus_text(self) -> str:
        n = self._target_count
        return f"Lv{self.level} {n}目标 {self.cooldown:.1f}s"


class SelfHealSkill(ActiveSkill):
    """自愈 —— 3 级：Lv1瞬回 / Lv2加大回复 / Lv3持续再生。"""

    def __init__(self):
        super().__init__(
            name="自愈", cooldown=8.0, max_level=3,
            icon_char='H', description="恢复+持续再生",
        )
        self._regen_left = 0.0
        from src.systems.buff_system import BuffTrigger, BuffTarget
        self.triggers = [BuffTrigger("attack_up", 1, 1.0, BuffTarget.SELF)]

    def _on_level_up(self):
        if self.level == 2:
            self._base_cooldown = 6.5
        elif self.level == 3:
            self._base_cooldown = 5.0
        self._recalc_cooldown()

    def execute(self, caster, targets: list, game_map) -> str:
        # 瞬间回复
        heal_pcts = {1: 0.20, 2: 0.35, 3: 0.35}
        pct = heal_pcts[self.level]
        power = self.get_power_multiplier()
        instant = int(caster.combat.max_hp * pct * power)
        recovered = caster.combat.heal(instant)
        desc = f"自愈Lv{self.level} 瞬回 {recovered} HP"
        # Lv3 额外持续再生
        if self.level >= 3:
            self._regen_left = 4.0
            desc += "（+4秒持续再生）"
        # Buff 触发: 给自身 attack_up
        from src.systems.buff_system import apply_triggers_self
        apply_triggers_self(self.triggers, caster)
        return desc

    def tick_regen(self, caster, delta_time: float):
        """Lv3 持续再生：每帧执行。"""
        if self._regen_left <= 0:
            return
        self._regen_left -= delta_time
        heal_per_tick = int(caster.combat.max_hp * 0.03 * delta_time)
        if heal_per_tick > 0:
            caster.combat.heal(heal_per_tick)

    def get_level_bonus_text(self) -> str:
        regen = "" if self.level < 3 else "+再生"
        return f"Lv{self.level} {self.cooldown:.1f}s{regen}"


# =========================================================
#  具体被动技能
# =========================================================

class IronSkinSkill(PassiveSkill):
    """铁壁 —— Lv1:+3 / Lv2:+7 / Lv3:+12 双防。"""

    LEVEL_VALUES = {1: 3, 2: 7, 3: 12}

    def __init__(self):
        super().__init__(name="铁壁", modifier_key="def_flat",
                         base_value=3, max_level=3, icon_char='D')

    def get_value(self) -> int:
        return self.LEVEL_VALUES.get(self.level, 3)

    def get_level_bonus_text(self) -> str:
        v = self.get_value()
        return f"Lv{self.level} DEF+{v}"


class BerserkSkill(PassiveSkill):
    """狂暴 —— Lv1:+3 / Lv2:+7 / Lv3:+12 攻击。"""

    LEVEL_VALUES = {1: 3, 2: 7, 3: 12}

    def __init__(self):
        super().__init__(name="狂暴", modifier_key="atk_flat",
                         base_value=3, max_level=3, icon_char='B')

    def get_value(self) -> int:
        return self.LEVEL_VALUES.get(self.level, 3)

    def get_level_bonus_text(self) -> str:
        v = self.get_value()
        return f"Lv{self.level} ATK+{v}"


# =========================================================
#  技能管理器
# =========================================================

class SkillManager:
    """技能管理器 —— 挂载在玩家上，管理技能习得/释放/升级。

    属性：
        active_skills: 已习得的主动技能列表。
        passives: 已习得的被动技能列表。
        max_active: 主动技能槽位上限（默认 4）。
    """

    def __init__(self, max_active: int = 4):
        """创建技能管理器。

        参数：
            max_active: 主动技能槽位上限。
        """
        self.active_skills: list[ActiveSkill] = []
        self.passives: list[PassiveSkill] = []
        self.max_active = max_active

    # =========================================================
    #  学习
    # =========================================================

    def can_learn(self) -> bool:
        """是否还有空余的主动技能槽位。"""
        return len(self.active_skills) < self.max_active

    def learn(self, skill: Skill):
        """学习一个技能 —— 主动技能放入 active_skills，被动放入 passives。

        如果主动槽位已满则丢弃该技能。

        参数：
            skill: 要学习的技能实例。

        返回：
            True 表示学习成功。
        """
        if isinstance(skill, PassiveSkill):
            self.passives.append(skill)
            return True
        if isinstance(skill, ActiveSkill):
            if not self.can_learn():
                return False
            self.active_skills.append(skill)
            return True
        return False

    # =========================================================
    #  释放
    # =========================================================

    def use_active(self, index: int, caster, targets: list,
                   game_map, game_time: float) -> str | None:
        """释放指定索引的主动技能。

        参数：
            index: 主动技能在列表中的索引。
            caster: 释放者（玩家）。
            targets: 目标列表。
            game_map: 地图。
            game_time: 当前时间戳。

        返回：
            效果描述文本，或 None（索引无效/冷却中）。
        """
        if index < 0 or index >= len(self.active_skills):
            return None
        skill = self.active_skills[index]
        if not skill.can_use(game_time):
            remain = skill.remaining_cooldown(game_time)
            return f"{skill.name} 冷却中 ({remain:.1f}s)"
        result = skill.execute(caster, targets, game_map)
        skill.mark_used(game_time)
        return result

    # =========================================================
    #  被动管理
    # =========================================================

    def apply_all_passives(self, player):
        """将所有被动技能加成写入玩家的 modifiers。

        参数：
            player: Player 实例。
        """
        for p in self.passives:
            p.apply(player)

    def upgrade_passive_at(self, index: int) -> str | None:
        """升级指定索引的被动技能。

        参数：
            index: 被动技能索引。

        返回：
            操作描述或 None。
        """
        if index < 0 or index >= len(self.passives):
            return None
        skill = self.passives[index]
        if skill.upgrade():
            return f"{skill.name} 升至 Lv{skill.level}"
        return f"{skill.name} 已达满级"

    def upgrade_active_at(self, index: int) -> str | None:
        """升级指定索引的主动技能。

        参数：
            index: 主动技能索引。

        返回：
            操作描述或 None。
        """
        if index < 0 or index >= len(self.active_skills):
            return None
        skill = self.active_skills[index]
        if skill.upgrade():
            return f"{skill.name} 升至 Lv{skill.level}"
        return f"{skill.name} 已达满级"


# =========================================================
#  工厂函数 —— 随机生成技能
# =========================================================

# =========================================================
#  具体主动技能（续）
# =========================================================

class TheWorldSkill(ActiveSkill):
    """The World —— 3 级：Lv1停5s / Lv2停7s / Lv3停10s。"""

    def __init__(self):
        super().__init__(
            name="The World", cooldown=20.0, max_level=3,
            icon_char='W', description="时停全屏冻结",
        )
        self._stop_duration = [0, 5.0, 7.0, 10.0]   # level -> 秒数

    def _on_level_up(self):
        if self.level == 2:
            self._base_cooldown = 16.0
        elif self.level == 3:
            self._base_cooldown = 12.0
        self._recalc_cooldown()

    def get_stop_duration(self) -> float:
        """返回时停秒数（含护符加成，不受等级倍率影响）。"""
        base = self._stop_duration[self.level]
        return base * (1.0 + self._charm_power_bonus)

    def get_level_bonus_text(self) -> str:
        d = self.get_stop_duration()
        return f"Lv{self.level} 停{d:.0f}s {self.cooldown:.1f}s"

    def execute(self, caster, targets: list, game_map) -> str:
        return "__TIME_STOP__"


ALL_ACTIVE_SKILLS = [SlashSkill, FireballSkill, SelfHealSkill, TheWorldSkill]
ALL_PASSIVE_SKILLS = [IronSkinSkill, BerserkSkill]


def random_active_skill(exclude_names: list[str] | None = None) -> ActiveSkill:
    """随机返回一个主动技能实例，排除已有技能。

    参数：
        exclude_names: 已习得的技能名列表，避免重复。

    返回：
        新的 ActiveSkill 实例。
    """
    if exclude_names is None:
        exclude_names = []
    available = [c for c in ALL_ACTIVE_SKILLS
                 if c.__name__ not in exclude_names]
    if not available:
        available = ALL_ACTIVE_SKILLS  # 回退：全随机
    cls = random.choice(available)
    return cls()


def random_passive_skill(exclude_names: list[str] | None = None) -> PassiveSkill:
    """随机返回一个被动技能实例，排除已有技能。"""
    if exclude_names is None:
        exclude_names = []
    available = [c for c in ALL_PASSIVE_SKILLS
                 if c.__name__ not in exclude_names]
    if not available:
        available = ALL_PASSIVE_SKILLS
    cls = random.choice(available)
    return cls()


def random_skill(exclude_names: list[str] | None = None) -> Skill:
    """随机返回一个技能（主动或被动），排除已有技能。"""
    if random.random() < 0.7:
        return random_active_skill(exclude_names)
    return random_passive_skill(exclude_names)

def get_learned_skill_names(manager) -> list[str]:
    """获取 SkillManager 中已习得的所有技能类名。

    参数：
        manager: SkillManager 实例。

    返回：
        类名字符串列表（用于去重）。
    """
    names = []
    for s in manager.active_skills:
        names.append(type(s).__name__)
    for s in manager.passives:
        names.append(type(s).__name__)
    return names
