"""
G5 sync: Boss system — BossAI + Phase2 signature mechanics + multi-boss presets
"""
import math, random, pygame, time
from config import TILE_SIZE
from src.entities.ai import MonsterAI, AIState
from src.entities.components import AttackType


class BossSkill:
    fx_kind = "circle"; fx_radius = 60; fx_color = (200, 40, 40)
    def __init__(self, name: str, cooldown: float):
        self.name = name; self.cooldown = cooldown; self._last_use_time = -999.0
    def can_use(self, gt: float) -> bool: return (gt - self._last_use_time) >= self.cooldown
    def execute(self, boss, player, monsters, game_map, gt) -> str: raise NotImplementedError
    def mark_used(self, gt): self._last_use_time = gt
    def get_fx_effect(self, boss) -> dict:
        if self.fx_kind == "none": return None
        return {"kind":self.fx_kind,"x":boss.entity.rect.centerx,"y":boss.entity.rect.centery,
                "radius":self.fx_radius,"color":self.fx_color,"duration":0.5,"elapsed":0.0}

class ConeAttack(BossSkill):
    fx_kind="circle";fx_radius=96;fx_color=(200,40,40)
    def __init__(s): super().__init__("暗影冲击",5.0)
    def execute(s,boss,player,monsters,gm,gt)->str:
        px,py=boss.entity.rect.centerx,boss.entity.rect.centery
        zone=pygame.Rect(px-64,py-32,128,64)
        if not zone.colliderect(player.entity.rect): return f"Boss 释放了 {s.name}，但你躲开了"
        from src.systems.combat_system import calculate_damage
        dmg=calculate_damage(int(boss.combat.get_effective_attack()*1.8),player.combat.get_effective_defense(AttackType.PHYSICAL),AttackType.PHYSICAL)
        player.combat.take_damage(dmg);s.mark_used(gt)
        return f"Boss {s.name}！造成 {dmg} 伤害"

class CircleAOE(BossSkill):
    fx_kind="circle";fx_radius=80;fx_color=(220,50,50)
    def __init__(s): super().__init__("地裂",7.0)
    def execute(s,boss,player,monsters,gm,gt)->str:
        d=math.hypot(player.entity.rect.centerx-boss.entity.rect.centerx,player.entity.rect.centery-boss.entity.rect.centery)
        if d>80: return f"Boss {s.name}，但你躲开了"
        from src.systems.combat_system import calculate_damage
        dmg=calculate_damage(int(boss.combat.get_effective_attack()*1.2),player.combat.get_effective_defense(AttackType.MAGICAL),AttackType.MAGICAL)
        player.combat.take_damage(dmg);s.mark_used(gt)
        return f"Boss {s.name}！造成 {dmg} 伤害"

class SummonMinions(BossSkill):
    fx_kind="circle";fx_radius=64;fx_color=(150,50,200)
    def __init__(s): super().__init__("召唤兽人",15.0)
    def execute(s,boss,player,monsters,gm,gt)->str:
        from src.entities.monster import spawn_monster
        count=0
        for _ in range(2):
            ox,oy=random.randint(-2,2),random.randint(-2,2)
            sx,sy=boss.entity.position.x+ox*TILE_SIZE,boss.entity.position.y+oy*TILE_SIZE
            tx,ty=gm.pixel_to_tile(sx,sy)
            if gm.is_walkable(tx,ty):
                m=spawn_monster(sx,sy,"orc");monsters.append(m);count+=1
        s.mark_used(gt)
        return f"Boss 召唤了 {count} 只兽人！"

# ── G5 sync: Phase2 signature skills ──

class WhirlwindSkill(BossSkill):
    """360°旋转斩 — Shadow Knight Phase2"""
    fx_kind="circle";fx_radius=140;fx_color=(180,20,200)
    def __init__(s): super().__init__("旋风斩",10.0);s._spin=0;s._hits=0;s._windup=0
    def execute(s,boss,player,monsters,gm,gt)->str:
        from src.systems.combat_system import calculate_damage
        dmg=calculate_damage(int(boss.combat.get_effective_attack()*1.3),player.combat.get_effective_defense(AttackType.PHYSICAL),AttackType.PHYSICAL)
        player.combat.take_damage(dmg);s._hits+=1
        if s._spin<=0.3: s.mark_used(gt); return f"旋风斩结束! {s._hits} hits"
        return ""

class LaserBarrageSkill(BossSkill):
    """3方向贯穿弹 — Fire Demon Phase2"""
    fx_kind="cone";fx_radius=200;fx_color=(255,100,20)
    def __init__(s): super().__init__("炼狱激光",9.0);s._windup=0
    def execute(s,boss,player,monsters,gm,gt)->str:
        bx,by=boss.entity.rect.centerx,boss.entity.rect.centery
        dx=player.entity.rect.centerx-bx;dy=player.entity.rect.centery-by
        ba=math.atan2(dy,dx);total=0
        from src.systems.combat_system import calculate_damage
        for i in(-1,0,1):
            a=ba+i*0.25;lx,ly=math.cos(a),math.sin(a)
            px,py=player.entity.rect.centerx,player.entity.rect.centery
            dot=(px-bx)*lx+(py-by)*ly;perp=abs((px-bx)*(-ly)+(py-by)*lx)
            if perp<60 and 0<dot<300:
                dmg=calculate_damage(int(boss.combat.get_effective_attack()*1.8),player.combat.get_effective_defense(AttackType.MAGICAL),AttackType.MAGICAL)
                player.combat.take_damage(dmg);total+=dmg
        s.mark_used(gt)
        return f"激光弹幕 造成 {total} 伤害" if total else "激光未命中"


BOSS_SKILLS = [ConeAttack, CircleAOE, SummonMinions]


class BossAI(MonsterAI):
    def __init__(self):
        super().__init__(sight_range=10,move_speed=60,patrol_interval=3.0,attack_range=2.0)
        self.skills:list[BossSkill]=[cls() for cls in BOSS_SKILLS]
        self.is_enraged=False;self._boss_id=None
        self._whirlwind=WhirlwindSkill();self._laser=LaserBarrageSkill()
        self._phase2_timer=0

    def update(self, monster, player, game_map, dt, gt, monsters=None, effects=None):
        if not monster.combat.is_alive: return
        # Phase2 check
        if not self.is_enraged and self._hp_ratio(monster) < 0.4:
            self._enter_enrage(monster)
        # G5 sync: Phase2 signature skill injection
        self._phase2_timer += dt
        self._tick_phase2(monster, player, game_map, dt, gt, monsters, effects)
        # Base AI
        super().update(monster, player, game_map, dt, gt, monsters, effects)
        # Try boss skills
        for sk in self.skills:
            if sk.can_use(gt):
                ml = monsters if monsters is not None else []
                result = sk.execute(monster, player, ml, game_map, gt)
                if effects is not None:
                    from src.fx_engine import boss_cone_fx, boss_circle_fx, boss_summon_fx
                    mx,my=monster.entity.rect.centerx,monster.entity.rect.centery
                    if isinstance(sk, ConeAttack): effects+=boss_cone_fx(mx,my)
                    elif isinstance(sk, CircleAOE): effects+=boss_circle_fx(mx,my)
                    elif isinstance(sk, SummonMinions): effects+=boss_summon_fx(mx,my)
                break

    def _tick_phase2(self, monster, player, game_map, dt, gt, monsters, effects):
        if not self.is_enraged or not self._boss_id: return
        every_6s = (int(self._phase2_timer*10)%60==0)
        bid = self._boss_id
        # Shadow Knight: Whirlwind every 9s
        if bid=="shadow_knight" and int(self._phase2_timer)%9==0 and every_6s:
            if not hasattr(self,"_ww_active"): self._ww_active=False
            if not self._ww_active:
                self._ww_active=True;self._whirlwind._spin=1.2;self._whirlwind._hits=0
            if self._whirlwind._spin>0:
                self._whirlwind._spin-=dt
                self._whirlwind.execute(monster,player,[],game_map,gt)
                dx=player.entity.rect.centerx-monster.entity.rect.centerx
                dy=player.entity.rect.centery-monster.entity.rect.centery
                length=math.hypot(dx,dy) or 1
                self._apply_movement(monster,game_map,dx/length,dy/length,dt*0.6)
                if self._whirlwind._spin<=0: self._ww_active=False
        # Fire Demon: Laser every 8s
        if bid=="fire_demon" and int(self._phase2_timer)%8==0 and every_6s:
            if not hasattr(self,"_laser_windup"): self._laser_windup=0
            if self._laser_windup<=0: self._laser_windup=0.8
            self._laser_windup-=dt
            if self._laser_windup<=0:
                self._laser.execute(monster,player,[],game_map,gt)
        # Demon Lord: Gravity pull every 10s
        if bid=="demon_lord" and int(self._phase2_timer)%10==0 and every_6s:
            bx,by=monster.entity.rect.centerx,monster.entity.rect.centery
            px,py=player.entity.rect.centerx,player.entity.rect.centery
            dx,dy=bx-px,by-py;length=math.hypot(dx,dy) or 1
            if length<300:player.entity.position.x+=dx/length*120*dt;player.entity.position.y+=dy/length*120*dt;player.entity.sync_rect()
            if int(self._phase2_timer*10)%2==0:
                from src.systems.combat_system import calculate_damage
                dmg=calculate_damage(int(monster.combat.get_effective_attack()*1.5),player.combat.get_effective_defense(AttackType.MAGICAL),AttackType.MAGICAL)
                player.combat.take_damage(dmg)
        # Vampire: Lifesteal + speed boost in Phase2
        if bid=="vampire":
            monster.attack_cooldown = 0.35
            if monster.can_attack(gt) and self._distance_to(monster,player)<2.0*TILE_SIZE:
                dmg = monster.attack_target(player, gt)
                monster.combat.heal(int(dmg*0.3))
        # Necromancer: summon buffs in Phase2
        if bid=="necromancer" and monsters:
            for m in monsters:
                if m and m.combat.is_alive and random.random()<0.02:
                    from src.systems.buff_system import apply_buff
                    apply_buff(m,"defense_up",1)
        # Golem: periodic shield refresh
        if bid=="golem" and int(self._phase2_timer)%6==0 and every_6s:
            from src.systems.buff_system import apply_buff
            apply_buff(monster,"stone_skin",1);apply_buff(monster,"shield",1)

    def _enter_enrage(self, monster):
        self.is_enraged=True;self.move_speed=int(self.move_speed*1.6)
        for sk in self.skills: sk.cooldown*=0.7
        self._phase2_timer=0

    def _hp_ratio(self, monster)->float:
        return monster.combat.current_hp/monster.combat.max_hp


# ── G5 sync: 6 Boss presets + boss_factory ──

BOSS_PRESETS = {
    5: {"name":"暗影骑士","hp":250,"atk":15,"pdef":10,"mdef":4,"color":(120,20,180),
        "title":"第一狱守 · 暗影骑士","lore":"曾是王城最荣耀的骑士，被黑暗吞噬后成为地牢第一道门的永恒守门人。","skills_text":"暗影冲击 · 地裂 · 召唤·螺旋斩(Phase2)","boss_id":"shadow_knight"},
    "necromancer":{"name":"亡灵法师","hp":240,"atk":14,"pdef":9,"mdef":7,"color":(80,180,80),
        "title":"第一狱守 · 亡灵法师","lore":"从墓地中召唤亡灵的黑暗法师。","skills_text":"暗影冲击 · 召唤·亡灵大军(Phase2)","boss_id":"necromancer"},
    "vampire":{"name":"血族伯爵","hp":220,"atk":18,"pdef":8,"mdef":6,"color":(180,40,60),
        "title":"第一狱守 · 血族伯爵","lore":"永夜古堡的遗族，以鲜血为食。","skills_text":"暗影冲击 · 嗜血(Phase2)","boss_id":"vampire"},
    10: {"name":"地狱火魔","hp":500,"atk":24,"pdef":14,"mdef":8,"color":(240,100,20),
        "title":"第二狱守 · 地狱火魔","lore":"熔岩深渊中诞生的远古恶魔。","skills_text":"暗影冲击 · 地裂 · 炼狱激光(Phase2)","boss_id":"fire_demon"},
    "golem":{"name":"远古魔像","hp":520,"atk":23,"pdef":18,"mdef":13,"color":(100,100,130),
        "title":"第二狱守 · 远古魔像","lore":"由熔岩冷却后的黑曜石组成。","skills_text":"暗影冲击 · 地裂 · 石甲护盾(Phase2)","boss_id":"golem"},
    15: {"name":"深渊之主·终焉","hp":900,"atk":35,"pdef":22,"mdef":14,"color":(180,20,20),
        "title":"终焉 · 深渊之主","lore":"一切黑暗的源头。击败他，地牢将重获光明。","skills_text":"暗影冲击 · 地裂 · 引力拉扯(Phase2)","boss_id":"demon_lord"},
}


def spawn_boss(tile_x:int, tile_y:int, floor_num:int=5, boss_id:str=None) -> "Monster":
    from src.entities.monster import Monster
    # G5 sync: auto-pick boss by floor (randomize for F5/F10)
    if boss_id is None:
        if floor_num==5: boss_id = random.choice(["5","necromancer","vampire"])
        elif floor_num==10: boss_id = random.choice(["10","golem"])
        else: boss_id = str(floor_num)
    cfg = BOSS_PRESETS.get(boss_id, BOSS_PRESETS.get(str(floor_num), BOSS_PRESETS[5]))
    boss = Monster(x=tile_x*TILE_SIZE,y=tile_y*TILE_SIZE,name=cfg["name"],
        max_hp=cfg["hp"],attack=cfg["atk"],physical_defense=cfg["pdef"],magical_defense=cfg["mdef"],
        color=cfg["color"],ai=BossAI(),attack_type=AttackType.PHYSICAL)
    boss.is_boss=True;boss.entity.size=(48,48);boss.entity.rect.width=48;boss.entity.rect.height=48
    # G5 sync: pass boss_id to BossAI for Phase2 behavior
    if hasattr(boss.ai,"_boss_id"): boss.ai._boss_id=cfg.get("boss_id","shadow_knight")
    return boss


def get_boss_info(floor_num:int)->dict|None:
    return BOSS_PRESETS.get(floor_num)
