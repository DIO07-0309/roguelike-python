"""
──────────────────────────────────────────
道具系统 —— 武器 / 护甲 / 药水 + 稀有度
──────────────────────────────────────────

职责：
  - 定义稀有度枚举和属性倍率。
  - 定义三种道具类型（装备型 / 消耗型）。
  - 提供工厂函数生成随机道具。

设计原则：
  - 稀有度只影响数值，不改变道具行为。
  - 装备型通过 apply()/remove() 修改玩家的 CombatStats.modifiers。
  - 新增道具类型只需继承 Item 并实现 use()。
"""

import random
from enum import Enum


class Rarity(Enum):
    """稀有度枚举 —— 带中文名和属性倍率。

    属性：
        label: 中文显示名。
        multiplier: 基础属性 × 此倍率。
        color: 显示颜色（RGB 元组）。
    """
    COMMON = ("普通", 1.0, (180, 180, 180))
    RARE = ("稀有", 1.5, (80, 160, 255))
    EPIC = ("史诗", 2.0, (180, 80, 255))
    LEGENDARY = ("传说", 3.0, (255, 140, 40))

    def __init__(self, label: str, multiplier: float, color: tuple):
        self.label = label
        self.multiplier = multiplier
        self.color = color

    @classmethod
    def random(cls, weights: list[float] = None) -> "Rarity":
        """加权随机抽取一个稀有度。

        参数：
            weights: 四元素权重列表 [普通, 稀有, 史诗, 传说]。
                     默认值使高级稀有度概率递减。
        """
        if weights is None:
            weights = [60, 25, 12, 3]
        rarities = list(cls)
        chosen = random.choices(rarities, weights=weights)[0]
        return chosen


class Item:
    """道具抽象基类 —— 所有可拾取物品的公共接口。

    属性：
        name: 完整名（如"传说 铁剑"）。
        base_name: 基础名（如"铁剑"）。
        rarity: Rarity 枚举值。
        tile_char: 显示在地图上的字符。
        color: 稀有度对应的颜色。
    """

    def __init__(self, base_name: str, rarity: Rarity, tile_char: str):
        """创建道具。

        参数：
            base_name: 基础名称（不含稀有度前缀）。
            rarity: 稀有度枚举值。
            tile_char: 地图显示字符。
        """
        self.base_name = base_name
        self.rarity = rarity
        self.name = f"{rarity.label} {base_name}"          # 完整名
        self.tile_char = tile_char
        self.color = rarity.color

    def get_description(self) -> str:
        """道具描述文本（子类覆写）。"""
        return self.name


class EquipmentItem(Item):
    """可装备道具 —— 武器或防具，带双防分类加成。

    属性：
        slot: 装备槽位（"weapon" 或 "armor"）。
        stat_bonus: 加成字典。
        defense_type: "physical" / "magical"。
    """

    def __init__(self, base_name: str, rarity: Rarity,
                 slot: str, atk_bonus: int = 0,
                 pdef_bonus: int = 0, mdef_bonus: int = 0,
                 defense_type: str = "physical"):
        """创建装备。

        参数：
            base_name: 基础名称。
            rarity: 稀有度。
            slot: "weapon" 或 "armor"。
            atk_bonus: 攻击加成。
            pdef_bonus: 物理防御加成。
            mdef_bonus: 魔法防御加成。
            defense_type: 防御侧重类型。
        """
        tile = 'W' if slot == "weapon" else 'A'
        super().__init__(base_name, rarity, tile)
        self.slot = slot
        self.defense_type = defense_type
        m = rarity.multiplier
        self.stat_bonus = {
            "atk": max(1, int(atk_bonus * m)),
            "pdef": max(1, int(pdef_bonus * m)),
            "mdef": max(1, int(mdef_bonus * m)),
        }

    def apply(self, player) -> None:
        """将装备加成写入 CombatStats.modifiers。

        武器 → atk_flat + pdef_flat（物理防御）
        护甲 → mdef_flat（魔法防御）

        参数：
            player: Player 实例。
        """
        atk = self.stat_bonus.get("atk", 0)
        pdef = self.stat_bonus.get("pdef", 0)
        mdef = self.stat_bonus.get("mdef", 0)
        mod = player.combat.modifiers
        mod["atk_flat"] = mod.get("atk_flat", 0) + atk
        if pdef > 0:
            mod["pdef_flat"] = mod.get("pdef_flat", 0) + pdef
        if mdef > 0:
            mod["mdef_flat"] = mod.get("mdef_flat", 0) + mdef

    def remove(self, player) -> None:
        """移除本装备的加成。

        参数：
            player: Player 实例。
        """
        mod = player.combat.modifiers
        mod["atk_flat"] = mod.get("atk_flat", 0) - self.stat_bonus.get("atk", 0)
        mod["pdef_flat"] = mod.get("pdef_flat", 0) - self.stat_bonus.get("pdef", 0)
        mod["mdef_flat"] = mod.get("mdef_flat", 0) - self.stat_bonus.get("mdef", 0)

    def get_description(self) -> str:
        """返回属性描述文本。"""
        parts = []
        if self.stat_bonus.get("atk"):
            parts.append(f"ATK+{self.stat_bonus['atk']}")
        pd = self.stat_bonus.get("pdef", 0)
        md = self.stat_bonus.get("mdef", 0)
        if pd:
            parts.append(f"物防+{pd}")
        if md:
            parts.append(f"魔防+{md}")
        return f"{self.name} ({', '.join(parts)})"


class CharmItem(EquipmentItem):
    """护符装备 —— 装备后强化指定主动技能的效果。

    属性：
        skill_class_name: 目标技能类名（如 "SlashSkill"）。
        cd_bonus: 冷却缩减比例（0.0~1.0）。
        power_bonus: 威力加成比例（0.0~1.0）。
    """

    def __init__(self, base_name: str, rarity: Rarity,
                 skill_class_name: str, cd_bonus: float, power_bonus: float):
        """创建护符。"""
        super().__init__(base_name, rarity, "charm",
                         pdef_bonus=0, mdef_bonus=0)
        self.tile_char = 'C'     # Charm 标识
        self.skill_class_name = skill_class_name
        self.cd_bonus = cd_bonus
        self.power_bonus = power_bonus

    def apply(self, player) -> None:
        """装备护符 —— 查找匹配技能并应用加成。"""
        if not player or not hasattr(player, "skills"):
            return
        for sk in player.skills.active_skills:
            if type(sk).__name__ == self.skill_class_name:
                sk.apply_charm(self.cd_bonus, self.power_bonus)
                return

    def remove(self, player) -> None:
        """卸下护符 —— 还原技能属性。"""
        if not player or not hasattr(player, "skills"):
            return
        for sk in player.skills.active_skills:
            if type(sk).__name__ == self.skill_class_name:
                sk.remove_charm()
                return

    def get_description(self) -> str:
        """返回护符效果描述。"""
        parts = []
        if self.cd_bonus > 0:
            parts.append(f"冷却-{int(self.cd_bonus*100)}%")
        if self.power_bonus > 0:
            parts.append(f"威力+{int(self.power_bonus*100)}%")
        return f"{self.name}（{', '.join(parts)}）"


class ConsumableItem(Item):
    """消耗型道具 —— 使用后从背包移除、产生即时效果。

    属性：
        effect_type: 效果类型（"heal" 等）。
        effect_value: 效果数值（受稀有度倍率影响）。
    """

    def __init__(self, base_name: str, rarity: Rarity,
                 effect_type: str, effect_value: int):
        """创建消耗品。

        参数：
            base_name: 基础名称。
            rarity: 稀有度。
            effect_type: 效果类型（heal / buff_strength 等）。
            effect_value: 效果基础值。
        """
        super().__init__(base_name, rarity, 'P')
        self.effect_type = effect_type
        self.effect_value = max(1, int(effect_value * rarity.multiplier))

    def use(self, player) -> str:
        """使用消耗品 —— 应用效果后返回描述文本。

        参数：
            player: 玩家实例。

        返回：
            效果描述文本（用于消息日志）。
        """
        if self.effect_type == "heal":
            recovered = player.combat.heal(self.effect_value)
            return f"使用 {self.name}，恢复了 {recovered} HP"
        # 预留其他效果类型
        return f"使用了 {self.name}（效果未实现）"

    def get_description(self) -> str:
        """返回效果描述文本。"""
        labels = {"heal": f"恢复 {self.effect_value} HP"}
        effect_text = labels.get(self.effect_type, str(self.effect_value))
        return f"{self.name} ({effect_text})"


class DroppedItem:
    """掉落在地面上的物品 —— 位置 + 物品实例。

    属性：
        item: Item 实例。
        tile_x, tile_y: 瓦片坐标。
    """

    def __init__(self, item: Item, tile_x: int, tile_y: int):
        self.item = item
        self.tile_x = tile_x
        self.tile_y = tile_y


# =========================================================
#  工厂函数 —— 随机生成道具
# =========================================================

def generate_random_item() -> Item:
    """随机生成一件道具（护符/武器/防具/药水）。"""
    rarity = Rarity.random()
    category = random.choices(
        ["weapon", "armor", "potion", "charm"],
        weights=[30, 30, 25, 15],
    )[0]
    if category == "charm":
        return generate_random_charm()
    elif category == "weapon":
        return _random_weapon(rarity)
    elif category == "armor":
        return _random_armor(rarity)
    else:
        return _random_potion(rarity)


def _random_weapon(rarity: Rarity) -> EquipmentItem:
    """生成随机武器（加攻击力 + 少量物理防御）。"""
    names = ["短剑", "长剑", "战斧", "匕首", "弯刀", "重锤", "长矛"]
    base_name = random.choice(names)
    atk = random.randint(5, 12)
    pdef = random.randint(0, 2)
    return EquipmentItem(base_name, rarity, "weapon",
                         atk_bonus=atk, pdef_bonus=pdef,
                         defense_type="physical")


def _random_armor(rarity: Rarity) -> EquipmentItem:
    """生成随机防具（物理护甲或魔法护甲）。"""
    is_magic = random.random() < 0.4
    names = (["法师袍", "灵纹斗篷", "符文衣"]
             if is_magic else ["皮甲", "锁子甲", "铁铠", "鳞甲", "板甲"])
    base_name = random.choice(names)
    pdef = random.randint(2, 5) if not is_magic else 0
    mdef = random.randint(3, 8) if is_magic else random.randint(1, 3)
    if not is_magic:
        pdef = random.randint(3, 8)
    return EquipmentItem(base_name, rarity, "armor",
                         pdef_bonus=pdef, mdef_bonus=mdef,
                         defense_type="magical" if is_magic else "physical")


def _random_potion(rarity: Rarity) -> ConsumableItem:
    """生成随机药水。"""
    names = ["生命药水", "治疗药剂", "恢复灵药", "大生命瓶"]
    base_name = random.choice(names)
    heal = random.randint(15, 40)
    return ConsumableItem(base_name, rarity, "heal", heal)


# =========================================================
#  护符工厂
# =========================================================

# 技能类名 → (护符名, cd缩减%, 威力加成%)
CHARM_SKILL_MAP: dict[str, tuple[str, float, float]] = {
    "SlashSkill": ("斩击纹章", 0.15, 0.40),
    "FireballSkill": ("烈焰之心", 0.20, 0.50),
    "SelfHealSkill": ("生命之泉", 0.25, 0.40),
    "TheWorldSkill": ("时光沙漏", 0.25, 0.25),
}


def generate_charm_for_skill(skill_class_name: str,
                              rarity: Rarity | None = None) -> CharmItem | None:
    """为指定技能类生成对应护符。

    参数：
        skill_class_name: 技能类名（如 "SlashSkill"）。
        rarity: 稀有度（None 则随机）。

    返回：
        CharmItem 或 None（无匹配时）。
    """
    info = CHARM_SKILL_MAP.get(skill_class_name)
    if not info:
        return None
    base_name, cd_pct, power_pct = info
    if rarity is None:
        rarity = Rarity.random()
    # 稀有度提升效果
    m = rarity.multiplier
    cd_bonus = min(0.7, cd_pct * m)
    power_bonus = power_pct * m
    return CharmItem(base_name, rarity, skill_class_name, cd_bonus, power_bonus)


def generate_random_charm() -> CharmItem:
    """随机生成一个护符（从四种技能中选一）。"""
    skill_name = random.choice(list(CHARM_SKILL_MAP.keys()))
    return generate_charm_for_skill(skill_name)
