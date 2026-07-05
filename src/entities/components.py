"""
──────────────────────────────────────────
实体组件 —— 可复用的数据与行为模块
──────────────────────────────────────────

职责：
  - 将实体能力拆分为独立组件，通过组合挂载到实体上。
  - 每个组件只管理一个关注面（战斗/属性/AI/...）。

设计原则：
  - 组件是纯数据 + 少量自管理逻辑（如 take_damage）。
  - 复杂计算（伤害公式、命中判定）放在 systems/ 中。
  - 预留 modifiers 字典接口，方便 Buff/装备/技能叠加修正值。
"""

from enum import Enum


class AttackType(Enum):
    """攻击伤害类型枚举。"""
    PHYSICAL = "physical"       # 物理伤害 — 受物理防御减免
    MAGICAL = "magical"         # 魔法伤害 — 受魔法防御减免
    TRUE = "true"               # 真实伤害 — 无视所有防御


class CombatStats:
    """战斗属性组件 —— 血量 / 攻防 / 生死状态。

    属性：
        max_hp: 最大生命值。
        current_hp: 当前生命值。
        attack: 基础攻击力。
        physical_defense: 物理防御力。
        magical_defense: 魔法防御力。
        is_alive: 存活标记。
        modifiers: 预留给 Buff/装备/技能系统的修正字典。
    """

    def __init__(self, max_hp: int, attack: int = 5,
                 physical_defense: int = 0, magical_defense: int = 0):
        """创建战斗属性。

        参数：
            max_hp: 最大生命值。
            attack: 基础攻击力。
            physical_defense: 物理防御力。
            magical_defense: 魔法防御力。
        """
        self.max_hp = max_hp
        self.current_hp = max_hp
        self.attack = attack
        self.physical_defense = physical_defense
        self.magical_defense = magical_defense
        self.is_alive = True
        self.modifiers: dict[str, float] = {}

    # =========================================================
    #  生命值操作
    # =========================================================

    def take_damage(self, amount: int) -> int:
        """受到伤害 —— 扣减当前生命值。

        参数：
            amount: 伤害值。

        返回：
            实际扣除量。
        """
        if not self.is_alive:
            return 0
        self.current_hp = max(0, self.current_hp - amount)
        if self.current_hp <= 0:
            self.is_alive = False
        return amount

    def heal(self, amount: int) -> int:
        """恢复生命值。

        参数：
            amount: 恢复量。

        返回：
            实际恢复量。
        """
        if not self.is_alive:
            return 0
        old_hp = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + amount)
        return self.current_hp - old_hp

    def get_effective_attack(self) -> int:
        """计算有效攻击力（基础 + 修正）。

        返回：
            修正后的攻击力（不低于 1）。
        """
        bonus = int(self.modifiers.get("atk_flat", 0))
        multiplier = self.modifiers.get("atk_pct", 0.0)
        effective = int(self.attack * (1 + multiplier)) + bonus
        return max(1, effective)

    def get_effective_defense(self, atk_type: "AttackType" = None) -> int:
        """按攻击类型选择对应有效防御力。

        pdef_flat / mdef_flat 来自装备
        def_flat 来自被动技能（双防通用）

        参数：
            atk_type: AttackType 枚举值。

        返回：
            修正后的防御力。
        """
        if atk_type is None:
            atk_type = AttackType.PHYSICAL
        if atk_type == AttackType.TRUE:
            return 0
        is_phys = (atk_type == AttackType.PHYSICAL)
        base = self.physical_defense if is_phys else self.magical_defense
        slot_key = "pdef_flat" if is_phys else "mdef_flat"
        all_bonus = (int(self.modifiers.get("def_flat", 0))
                     + int(self.modifiers.get(slot_key, 0)))
        multiplier = self.modifiers.get("def_pct", 0.0)
        effective = int(base * (1 + multiplier)) + all_bonus
        return max(0, effective)
