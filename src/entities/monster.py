"""
──────────────────────────────────────────
怪物类 —— G5 sync: EnemyDef JSON driven
──────────────────────────────────────────
"""
import pygame
import random
from src.entities.entity import Entity
from src.entities.components import CombatStats, AttackType
from src.entities.ai import MonsterAI
from src.systems.combat_system import calculate_damage


class Monster:
    """地牢怪物 —— 组合实体与战斗属性。"""
    DEFAULT_HP = 20; DEFAULT_ATK = 4; DEFAULT_PDEF = 1; DEFAULT_MDEF = 0
    DEFAULT_SIZE = 28; DEFAULT_COLOR = (200, 80, 80); ATTACK_COOLDOWN = 1.5

    def __init__(self, x: float, y: float, name: str = "史莱姆",
                 max_hp: int = DEFAULT_HP, attack: int = DEFAULT_ATK,
                 physical_defense: int = DEFAULT_PDEF, magical_defense: int = DEFAULT_MDEF,
                 color: tuple = DEFAULT_COLOR, ai: MonsterAI | None = None,
                 attack_type: AttackType = AttackType.PHYSICAL):
        self.entity = Entity(x, y, self.DEFAULT_SIZE, self.DEFAULT_SIZE)
        self.combat = CombatStats(max_hp, attack, physical_defense, magical_defense)
        self.name = name; self.color = color; self._last_attack_time = 0.0
        self.ai = ai if ai is not None else MonsterAI()
        self.is_boss = False; self.attack_type = attack_type
        self.active_buffs = []; self.on_hit_triggers = []

    def take_damage(self, amount: int) -> bool:
        self.combat.take_damage(amount); return not self.combat.is_alive

    def can_attack(self, game_time: float) -> bool:
        return (game_time - self._last_attack_time) >= self.ATTACK_COOLDOWN

    def update_ai(self, player, game_map, delta_time: float,
                  game_time: float, monsters: list | None = None, effects: list | None = None):
        self.ai.update(self, player, game_map, delta_time, game_time, monsters, effects)

    def attack_target(self, target, game_time: float = 0.0) -> int:
        from src.systems.buff_system import get_effective_attack, apply_triggers
        atk = get_effective_attack(self)
        target_def = target.combat.get_effective_defense(self.attack_type)
        damage = calculate_damage(atk, target_def, self.attack_type)
        target.combat.take_damage(damage)
        self._last_attack_time = game_time
        apply_triggers(self.on_hit_triggers, None, target)
        return damage

    def render(self, screen: pygame.Surface, camera_x: int = 0, camera_y: int = 0):
        import math, time
        dr = self.entity.rect.move(-camera_x, -camera_y)
        if self.is_boss:
            pulse = int(3 + abs(math.sin(time.time() * 6)) * 5)
            pygame.draw.rect(screen, (60, 5, 5), dr.inflate(pulse*2, pulse*2), 3, border_radius=8)
        sh = dr.inflate(-2, -2).move(2, 3)
        pygame.draw.ellipse(screen, (0, 0, 0, 80), sh)
        pygame.draw.rect(screen, self.color, dr, border_radius=4)
        hl = self._lighten_color(self.color, 60)
        pygame.draw.rect(screen, hl, (dr.x+3, dr.y+2, dr.w-6, 6), border_radius=3)
        if "史莱姆" in self.name:
            ey = dr.y + dr.h//2 - 2
            for ox in [dr.w//3, dr.w*2//3]:
                pygame.draw.circle(screen, (255,255,255), (dr.x+ox, ey), 5)
                pygame.draw.circle(screen, (20,20,20), (dr.x+ox+1, ey+1), 3)
        elif "兽人" in self.name:
            ey = dr.y + dr.h//2 - 1
            for sx in [dr.x+5, dr.x+dr.w-9]:
                pygame.draw.polygon(screen, (255,50,50), [(sx,ey),(sx+5,ey+2),(sx,ey+5)])
        bc = (255, 180, 30) if self.is_boss else (0, 0, 0)
        pygame.draw.rect(screen, bc, dr, 2, border_radius=4)
        if not self.is_boss and self.combat.current_hp < self.combat.max_hp:
            ratio = self.combat.current_hp / self.combat.max_hp
            pygame.draw.rect(screen, (40,10,10), (dr.x, dr.y-8, dr.w, 4))
            hc = (200,40,40) if ratio > 0.5 else (200,20,20)
            pygame.draw.rect(screen, hc, (dr.x, dr.y-8, int(dr.w*ratio), 4))

    @staticmethod
    def _lighten_color(c: tuple, amt: int) -> tuple:
        return tuple(min(255, v + amt) for v in c[:3])


# ═══════════════════════════════════════════════════════════════
# G5 sync: spawn_monster — EnemyDef JSON优先, 24+类型回退
# ═══════════════════════════════════════════════════════════════

_VISUAL_COLORS = {
    "slime":(100,180,100),"orc":(200,80,80),"archer":(80,160,80),
    "shaman":(160,100,200),"bomber":(255,140,40),"tank":(120,120,140),
    "elite_slime":(100,220,100),"elite_orc":(240,60,60),
    "charger":(200,140,60),"summoner":(180,120,220),
    "necromancer":(80,180,80),"fire_demon":(240,100,20),
    "demon_lord":(180,20,20),"golem":(100,100,130),"vampire":(180,40,60),
}

_FALLBACK_PRESETS = {
    "slime": ("史莱姆", 15, 3, 0, 1, (100,180,100)),
    "orc": ("兽人", 30, 7, 3, 1, (200,80,80)),
    "archer": ("哥布林弓箭手", 22, 8, 1, 1, (80,160,80)),
    "shaman": ("哥布林萨满", 28, 4, 2, 4, (160,100,200)),
    "bomber": ("爆炸史莱姆", 25, 0, 2, 2, (255,140,40)),
    "tank": ("重甲兽人", 70, 6, 8, 3, (120,120,140)),
    "elite": ("精英兽人", 75, 16, 6, 3, (240,60,60)),
    "charger": ("冲锋兽人", 40, 10, 4, 2, (200,140,60)),
    "summoner": ("哥布林召唤师", 35, 5, 3, 5, (180,120,220)),
    "frost_slime": ("冰霜史莱姆", 20, 4, 1, 2, (150,200,240)),
    "shadow_stalker": ("暗影潜伏者", 25, 12, 2, 2, (100,30,150)),
    "fire_imp": ("火魔仆从", 20, 10, 1, 3, (255,120,30)),
    "blood_leech": ("鲜血水蛭", 22, 8, 2, 1, (180,30,50)),
    "golem": ("魔像", 100, 12, 12, 5, (100,100,130)),
    "skeleton_archer": ("骷髅弓手", 22, 12, 2, 2, (200,200,190)),
    "dark_mage": ("暗术师", 30, 8, 3, 6, (120,40,180)),
    "shadow_assassin": ("暗影刺客", 24, 16, 2, 3, (80,20,130)),
    "stone_guardian": ("石像守卫", 90, 10, 14, 8, (140,140,160)),
}


def spawn_monster(x: int, y: int, monster_type: str = "slime") -> Monster:
    from src.systems.buff_system import BuffTrigger, BuffTarget, apply_buff
    from src.entities.ai import MonsterSkillState, MonsterSkillType

    # try EnemyDef JSON first
    try:
        from src.game.enemy_defs import get_enemy_def
        defn = get_enemy_def(monster_type)
        if defn:
            color = _VISUAL_COLORS.get(defn.visual_id, (100,180,100))
            at = AttackType.MAGICAL if defn.attack_type_str=="magical" else AttackType.PHYSICAL
            m = Monster(x, y, defn.name, defn.hp, defn.atk, defn.pdef, defn.mdef, color, attack_type=at)
            m.attack_cooldown = defn.attack_cooldown
            for oh in defn.on_hit:
                tgt = BuffTarget.SELF if oh.get("target","")=="self" else BuffTarget.ENEMY
                m.on_hit_triggers.append(BuffTrigger(oh["buff"], oh["stacks"], oh["chance"], tgt))
            sk_map = {"rapid_shot":MonsterSkillType.RAPID_SHOT,"totem":MonsterSkillType.TOTEM,
                "leap":MonsterSkillType.LEAP,"shield":MonsterSkillType.SHIELD,
                "summon":MonsterSkillType.SUMMON,"charge":MonsterSkillType.CHARGE,
                "mass_summon":MonsterSkillType.MASS_SUMMON}
            for sk in defn.skills:
                st = sk_map.get(sk.id)
                if st: m.ai._skills.append(MonsterSkillState(type=st, max_cooldown=sk.max_cooldown, cooldown=sk.initial_cooldown))
            if defn.is_elite and defn.elite_buffs:
                eb = random.choice(defn.elite_buffs)
                if eb.get("buff"): apply_buff(m, eb["buff"], eb["stacks"])
            return m
    except Exception:
        pass

    # fallback
    preset = _FALLBACK_PRESETS.get(monster_type, _FALLBACK_PRESETS["slime"])
    m = Monster(x, y, preset[0], preset[1], preset[2], preset[3], preset[4], preset[5])
    triggers_s = {"slime":("slow",1,0.25),"orc":("poison",1,0.25),
        "frost_slime":("freeze",1,0.20),"blood_leech":("bleed",1,0.35),
        "fire_imp":("burn",1,0.40),"shadow_stalker":("fear",1,0.15),
        "shadow_assassin":("fear",1,0.20),"dark_mage":("curse",1,0.25)}
    t = triggers_s.get(monster_type)
    if t: m.on_hit_triggers = [BuffTrigger(t[0], t[1], t[2], BuffTarget.ENEMY)]
    return m
