"""
G5 sync: MonsterAI — 状态机 + 技能池 + AIArchetype 行为
"""
import math, random, time
from enum import Enum, auto
from dataclasses import dataclass
from config import TILE_SIZE, PLAYER_ATTACK_RANGE, MONSTER_SIGHT_RANGE, MONSTER_MOVE_SPEED, MONSTER_PATROL_INTERVAL

class MonsterSkillType(Enum):
    NONE = 0; RAPID_SHOT = auto(); TOTEM = auto(); LEAP = auto()
    SHIELD = auto(); SUMMON = auto(); CHARGE = auto(); MASS_SUMMON = auto()
    SNIPE = auto(); SCATTER = auto(); AMBUSH_ATTACK = auto(); GUARD_AURA = auto()

@dataclass
class MonsterSkillState:
    type: MonsterSkillType = MonsterSkillType.NONE
    cooldown: float = 0.0; max_cooldown: float = 5.0
    cast_left: float = 0.0; duration_left: float = 0.0
    shot_timer: float = 0.0; shot_count: int = 0; active: bool = False

class AIArchetype(Enum):
    DEFAULT = 0; BOMBER = auto(); SHAMAN = auto(); SNIPER = auto()
    CONTROLLER = auto(); AMBUSH = auto(); GUARDIAN = auto(); CHARGER = auto(); SUMMONER = auto()

class AIState(Enum):
    IDLE = auto(); CHASE = auto(); ATTACK = auto()

class MonsterAI:
    def __init__(self, sight_range:int=MONSTER_SIGHT_RANGE, move_speed:int=MONSTER_MOVE_SPEED,
                 patrol_interval:float=MONSTER_PATROL_INTERVAL, attack_range:float=PLAYER_ATTACK_RANGE):
        self.state = AIState.IDLE
        self.sight_range=sight_range; self.move_speed=move_speed
        self.patrol_interval=patrol_interval; self.attack_range=attack_range
        self._patrol_timer=0.0; self._patrol_dir=(0.0,0.0)
        self._pick_new_patrol_direction()
        self._skills:list[MonsterSkillState]=[]
        self.archetype = AIArchetype.DEFAULT
        self._archetype_timer = 0.0; self._archetype_active = False

    def update(self, monster, player, game_map, delta_time, game_time, monsters=None, effects=None):
        if not monster.combat.is_alive: return
        # Archetype behaviors (G5 sync)
        self._tick_archetype(monster, player, game_map, delta_time, game_time, monsters, effects)
        # Think & cast skills
        if self._skills and self._think_and_cast(monster, player, game_map, delta_time, game_time, monsters, effects):
            return
        self._decide_state(monster, player)
        if self.state == AIState.IDLE: self._execute_idle(monster, game_map, delta_time)
        elif self.state == AIState.CHASE: self._execute_chase(monster, player, game_map, delta_time)
        elif self.state == AIState.ATTACK: self._execute_attack(monster, player, game_time, effects)

    def _tick_archetype(self, monster, player, game_map, dt, gt, monsters, effects):
        a = self.archetype
        dist = self._distance_to(monster, player)

        if a == AIArchetype.BOMBER:
            if dist <= self.attack_range * TILE_SIZE:
                if not hasattr(monster, "_explode_timer"): monster._explode_timer = 0
                if monster._explode_timer <= 0: monster._explode_timer = 2.0
                monster._explode_timer -= dt
                if monster._explode_timer <= 0:
                    dmg = int(monster.combat.max_hp * 0.4)
                    monster.combat.take_damage(monster.combat.max_hp)
                    if effects:
                        from src.fx_engine import boss_circle_fx
                        effects += boss_circle_fx(monster.entity.rect.centerx, monster.entity.rect.centery)
                    if dist <= 3.0 * TILE_SIZE:
                        aoe = dmg
                        player.combat.take_damage(aoe)
                return
            else: monster._explode_timer = 0.0

        elif a == AIArchetype.SHAMAN:
            if not hasattr(monster, "_support_cd"): monster._support_cd = 0
            monster._support_cd -= dt
            if monster._support_cd <= 0 and monsters:
                best, bd = None, 5.0 * TILE_SIZE
                for o in monsters:
                    if not o or o is monster or not o.combat.is_alive: continue
                    d = math.hypot(o.entity.rect.x - monster.entity.rect.x, o.entity.rect.y - monster.entity.rect.y)
                    if d < bd: bd = d; best = o
                if best:
                    from src.systems.buff_system import apply_buff
                    if random.random()<0.5: apply_buff(best, "attack_up", 1)
                    else: best.combat.heal(int(best.combat.max_hp * 0.15))
                    monster._support_cd = 4.0; return

        elif a == AIArchetype.SNIPER:
            if dist < 6.0 * TILE_SIZE:
                dx = monster.entity.rect.x - player.entity.rect.x
                dy = monster.entity.rect.y - player.entity.rect.y
                length = math.hypot(dx, dy) or 1
                self._apply_movement(monster, game_map, dx/length, dy/length, dt)
            if 4.0*TILE_SIZE < dist < 12.0*TILE_SIZE:
                self._archetype_timer += dt
                if self._archetype_timer > 2.5:
                    self._archetype_timer = 0.0
                    from src.systems.combat_system import calculate_damage
                    dmg = calculate_damage(monster.combat.get_effective_attack()*2, player.combat.get_effective_defense(0), 0)
                    player.combat.take_damage(dmg)
                    if effects: effects.append({"kind":"bolt","x":monster.entity.rect.centerx,"y":monster.entity.rect.centery,"target_x":player.entity.rect.centerx,"target_y":player.entity.rect.centery,"radius":4,"duration":0.3,"color":(255,255,255,200)})
                    return

        elif a == AIArchetype.CONTROLLER:
            self._archetype_timer += dt
            if self._archetype_timer > 5.0:
                self._archetype_timer = 0.0
                px, py = player.entity.rect.centerx, player.entity.rect.centery
                for i in range(4):
                    angle = i * 1.5708 + random.randint(0,30) * 0.01745
                    tx, ty = px + math.cos(angle)*80, py + math.sin(angle)*80
                    if effects: effects.append({"kind":"pulse","x":tx,"y":ty,"radius":32,"duration":0.5,"color":(200,60,200,150)})
                    if math.hypot(px-tx, py-ty) < 48:
                        from src.systems.combat_system import calculate_damage
                        dmg = calculate_damage(monster.combat.get_effective_attack(), player.combat.get_effective_defense(1), 1)
                        player.combat.take_damage(dmg)
                from src.systems.buff_system import apply_buff
                apply_buff(player, "slow", 1)
                return
            if dist < 4.0*TILE_SIZE:
                dx, dy = monster.entity.rect.x-player.entity.rect.x, monster.entity.rect.y-player.entity.rect.y
                length = math.hypot(dx, dy) or 1
                self._apply_movement(monster, game_map, dx/length, dy/length, dt); return

        elif a == AIArchetype.AMBUSH:
            self._archetype_timer += dt
            if not self._archetype_active and self._archetype_timer > 8.0:
                self._archetype_active = True; self._archetype_timer = 0.0
            if self._archetype_active:
                dx = player.entity.rect.centerx - monster.entity.rect.centerx
                dy = player.entity.rect.centery - monster.entity.rect.centery
                length = math.hypot(dx, dy) or 1
                self._apply_movement(monster, game_map, dx/length, dy/length, dt*1.3)
                if length < 2.0*TILE_SIZE:
                    self._archetype_active = False
                    from src.systems.combat_system import calculate_damage
                    dmg = calculate_damage(monster.combat.get_effective_attack()*3, player.combat.get_effective_defense(0))
                    player.combat.take_damage(dmg)
                    from src.systems.buff_system import apply_buff
                    apply_buff(player, "stun", 1)
                return

        elif a == AIArchetype.GUARDIAN:
            self._archetype_timer += dt
            if self._archetype_timer > 6.0:
                self._archetype_timer = 0.0
                if monsters:
                    from src.systems.buff_system import apply_buff
                    for o in monsters:
                        if not o or o is monster or not o.combat.is_alive: continue
                        if math.hypot(o.entity.rect.x-monster.entity.rect.x, o.entity.rect.y-monster.entity.rect.y) < 6.0*TILE_SIZE:
                            apply_buff(o, "defense_up", 1); apply_buff(o, "shield", 1)
                return
            if dist < 3.0*TILE_SIZE:
                dx, dy = monster.entity.rect.x-player.entity.rect.x, monster.entity.rect.y-player.entity.rect.y
                length = math.hypot(dx, dy) or 1
                self._apply_movement(monster, game_map, dx/length, dy/length, dt)

    def _think_and_cast(self, monster, player, game_map, dt, gt, monsters, effects):
        for sk in self._skills:
            if sk.cooldown > 0: sk.cooldown -= dt; continue
            if sk.cast_left > 0:
                sk.cast_left -= dt
                if sk.cast_left <= 0:
                    if sk.type == MonsterSkillType.CHARGE: self._exec_charge(monster, player, game_map, effects, sk)
                    elif sk.type == MonsterSkillType.SNIPE: self._exec_snipe(monster, player, effects, sk)
                    elif sk.type == MonsterSkillType.AMBUSH_ATTACK: self._exec_ambush(monster, player, game_map, effects, sk)
                    sk.cooldown = sk.max_cooldown; return True
                return True
            if sk.duration_left > 0:
                sk.duration_left -= dt
                if sk.duration_left <= 0: sk.active = False
                return False if sk.type == MonsterSkillType.TOTEM else True
            if sk.active and sk.type == MonsterSkillType.RAPID_SHOT and sk.shot_count < 3:
                sk.shot_timer -= dt
                if sk.shot_timer <= 0: self._exec_rapid_shot(monster, player, gt, effects, sk)
                return True
            dist = self._distance_to(monster, player)
            should = False
            if sk.type == MonsterSkillType.RAPID_SHOT: should = (dist <= self.sight_range*TILE_SIZE and dist > self.attack_range*TILE_SIZE)
            elif sk.type == MonsterSkillType.TOTEM: should = (monsters is not None)
            elif sk.type == MonsterSkillType.LEAP: should = (4.0*TILE_SIZE < dist < 10.0*TILE_SIZE)
            elif sk.type == MonsterSkillType.SHIELD: should = (dist <= self.attack_range*TILE_SIZE)
            elif sk.type == MonsterSkillType.SUMMON: should = (monsters and len(monsters) < 8)
            elif sk.type == MonsterSkillType.CHARGE: should = (3.0*TILE_SIZE < dist < 8.0*TILE_SIZE)
            elif sk.type == MonsterSkillType.MASS_SUMMON: should = (monsters and len(monsters) < 10)
            elif sk.type == MonsterSkillType.SNIPE: should = (4.0*TILE_SIZE < dist < 12.0*TILE_SIZE)
            elif sk.type == MonsterSkillType.SCATTER: should = (3.0*TILE_SIZE < dist < 9.0*TILE_SIZE)
            elif sk.type == MonsterSkillType.AMBUSH_ATTACK: should = (5.0*TILE_SIZE < dist < 10.0*TILE_SIZE)
            elif sk.type == MonsterSkillType.GUARD_AURA: should = (monsters and len(monsters) >= 2)
            if not should: continue
            if sk.type == MonsterSkillType.RAPID_SHOT: sk.cast_left = 0.35; sk.shot_count = 0
            elif sk.type == MonsterSkillType.TOTEM: self._exec_totem(monster, player, monsters, effects, sk); sk.cooldown = sk.max_cooldown
            elif sk.type == MonsterSkillType.LEAP: self._exec_leap(monster, player, game_map, sk); sk.cooldown = sk.max_cooldown
            elif sk.type == MonsterSkillType.SHIELD: self._exec_shield(monster, sk); sk.cast_left = 0.2
            elif sk.type == MonsterSkillType.SUMMON: self._exec_summon(monster, player, game_map, monsters, effects, sk); sk.cooldown = sk.max_cooldown
            elif sk.type == MonsterSkillType.CHARGE: sk.cast_left = 0.5
            elif sk.type == MonsterSkillType.MASS_SUMMON: self._exec_mass_summon(monster, player, game_map, monsters, effects, sk); sk.cooldown = sk.max_cooldown
            elif sk.type == MonsterSkillType.SNIPE: sk.cast_left = 1.2
            elif sk.type == MonsterSkillType.SCATTER: self._exec_scatter(monster, player, effects, sk); sk.cooldown = sk.max_cooldown
            elif sk.type == MonsterSkillType.AMBUSH_ATTACK: sk.cast_left = 0.3
            elif sk.type == MonsterSkillType.GUARD_AURA: self._exec_guard_aura(monster, monsters, effects, sk); sk.cooldown = sk.max_cooldown
            return True
        return False

    # Skill executors
    def _exec_rapid_shot(self, monster, player, gt, effects, sk):
        from src.systems.combat_system import calculate_damage
        dmg = calculate_damage(monster.combat.get_effective_attack(), player.combat.get_effective_defense(0))
        player.combat.take_damage(dmg); sk.shot_count += 1; sk.shot_timer = 0.2
        if sk.shot_count >= 3: sk.active = False; sk.cooldown = sk.max_cooldown; sk.shot_count = 0

    def _exec_totem(self, monster, player, monsters, effects, sk):
        from src.systems.buff_system import apply_buff
        cx, cy = monster.entity.rect.centerx, monster.entity.rect.centery
        if monsters:
            for ally in monsters:
                if not ally or ally is monster or not ally.combat.is_alive: continue
                if math.hypot(ally.entity.rect.centerx-cx, ally.entity.rect.centery-cy) <= 80:
                    apply_buff(ally, "attack_up", 1); ally.combat.heal(int(ally.combat.max_hp * 0.1))
        sk.duration_left = 0.1

    def _exec_leap(self, monster, player, game_map, sk):
        dx = player.entity.rect.centerx - monster.entity.rect.centerx
        dy = player.entity.rect.centery - monster.entity.rect.centery
        dist = math.hypot(dx, dy) or 1
        leap = dist - 2.0*TILE_SIZE
        if leap < 0: leap = 0
        monster.entity.position.x += dx/dist*leap; monster.entity.position.y += dy/dist*leap
        monster.entity.sync_rect()
        if not game_map.is_rect_walkable(monster.entity.rect):
            monster.entity.position.x -= dx/dist*leap; monster.entity.position.y -= dy/dist*leap
            monster.entity.sync_rect()

    def _exec_shield(self, monster, sk):
        monster.combat.modifiers["def_pct"] = monster.combat.modifiers.get("def_pct", 0) + 0.70
        sk.duration_left = 3.0

    def _exec_summon(self, monster, player, game_map, monsters, effects, sk):
        from src.entities.monster import spawn_monster
        for _ in range(3):
            ox, oy = random.randint(-2,2), random.randint(-2,2)
            sx, sy = monster.entity.position.x+ox*TILE_SIZE, monster.entity.position.y+oy*TILE_SIZE
            tx, ty = game_map.pixel_to_tile(sx, sy)
            if game_map.is_walkable(tx, ty):
                m = spawn_monster(sx, sy, "orc" if random.random()>0.33 else "slime")
                if m and monsters is not None: monsters.append(m); break

    def _exec_charge(self, monster, player, game_map, effects, sk):
        dx = player.entity.rect.centerx - monster.entity.rect.centerx
        dy = player.entity.rect.centery - monster.entity.rect.centery
        dist = math.hypot(dx, dy) or 1
        charge = min(dist, 4.0*TILE_SIZE)
        monster.entity.position.x += dx/dist*charge; monster.entity.position.y += dy/dist*charge
        monster.entity.sync_rect()
        if game_map and not game_map.is_rect_walkable(monster.entity.rect):
            monster.entity.position.x -= dx/dist*charge; monster.entity.position.y -= dy/dist*charge
            monster.entity.sync_rect()
        if self._distance_to(monster, player) <= self.attack_range*TILE_SIZE*2:
            from src.systems.combat_system import calculate_damage
            dmg = calculate_damage(monster.combat.get_effective_attack()*2, player.combat.get_effective_defense(0))
            player.combat.take_damage(dmg)
            player.entity.position.x += dx/dist*48; player.entity.position.y += dy/dist*48
            player.entity.sync_rect()

    def _exec_mass_summon(self, monster, player, game_map, monsters, effects, sk):
        from src.entities.monster import spawn_monster
        for _ in range(2):
            ox, oy = random.randint(-3,3), random.randint(-3,3)
            sx, sy = monster.entity.position.x+ox*TILE_SIZE, monster.entity.position.y+oy*TILE_SIZE
            tx, ty = game_map.pixel_to_tile(sx, sy)
            if game_map.is_walkable(tx, ty):
                m = spawn_monster(sx, sy, "archer" if random.random()<0.5 else "slime")
                if m and monsters is not None: monsters.append(m)

    # G5 sync: new skill executors
    def _exec_snipe(self, monster, player, effects, sk):
        from src.systems.combat_system import calculate_damage
        dmg = calculate_damage(int(monster.combat.get_effective_attack()*2.5), max(1, player.combat.get_effective_defense(0)//2))
        player.combat.take_damage(dmg)
        if effects: effects.append({"kind":"bolt","x":monster.entity.rect.centerx,"y":monster.entity.rect.centery,"target_x":player.entity.rect.centerx,"target_y":player.entity.rect.centery,"radius":5,"duration":0.3,"color":(255,255,255,220)})

    def _exec_scatter(self, monster, player, effects, sk):
        cx, cy = monster.entity.rect.centerx, monster.entity.rect.centery
        count = 3 + random.randint(0, 1)
        for i in range(count):
            angle = (i - count/2 + 0.5)*0.35
            dx, dy = math.cos(angle)*200, math.sin(angle)*200
            if effects: effects.append({"kind":"bolt","x":cx,"y":cy,"target_x":cx+dx,"target_y":cy+dy,"radius":3,"duration":0.25,"color":(200,100,255,180)})
            px, py = player.entity.rect.centerx, player.entity.rect.centery
            close = abs((px-cx)*(-math.sin(angle))+(py-cy)*math.cos(angle))
            along = (px-cx)*math.cos(angle)+(py-cy)*math.sin(angle)
            if close < 48 and along > 0 and along < 250:
                from src.systems.combat_system import calculate_damage
                dmg = calculate_damage(int(monster.combat.get_effective_attack()*0.6), player.combat.get_effective_defense(1), 1)
                player.combat.take_damage(dmg)

    def _exec_ambush(self, monster, player, game_map, effects, sk):
        px, py = player.entity.rect.centerx, player.entity.rect.centery
        behind_x = px - 64 - monster.entity.rect.w//2
        behind_y = py - monster.entity.rect.h//2
        monster.entity.position.x, monster.entity.position.y = behind_x, behind_y
        monster.entity.sync_rect()
        if game_map and not game_map.is_rect_walkable(monster.entity.rect):
            monster.entity.position.x, monster.entity.position.y = px+64-monster.entity.rect.w//2, py-monster.entity.rect.h//2
            monster.entity.sync_rect()
        from src.systems.combat_system import calculate_damage
        dmg = calculate_damage(int(monster.combat.get_effective_attack()*3.0), player.combat.get_effective_defense(0))
        player.combat.take_damage(dmg)
        from src.systems.buff_system import apply_buff
        apply_buff(player, "stun", 1)
        if effects: effects.append({"kind":"pulse","x":monster.entity.rect.centerx,"y":monster.entity.rect.centery,"radius":48,"duration":0.4,"color":(100,30,180,200)})

    def _exec_guard_aura(self, monster, monsters, effects, sk):
        from src.systems.buff_system import apply_buff
        apply_buff(monster, "stone_skin", 2); apply_buff(monster, "defense_up", 2)
        if monsters:
            cx, cy = monster.entity.rect.centerx, monster.entity.rect.centery
            for ally in monsters:
                if not ally or ally is monster or not ally.combat.is_alive: continue
                if math.hypot(ally.entity.rect.centerx-cx, ally.entity.rect.centery-cy) < 6.0*TILE_SIZE:
                    apply_buff(ally, "defense_up", 1); apply_buff(ally, "shield", 1)
        if effects: effects.append({"kind":"pulse","x":cx,"y":cy,"radius":80,"duration":0.5,"color":(60,140,255,150)})

    # State machine (existing)
    def _decide_state(self, monster, player):
        dist = self._distance_to(monster, player)
        if dist <= self.attack_range*TILE_SIZE: self.state = AIState.ATTACK
        elif dist <= self.sight_range*TILE_SIZE: self.state = AIState.CHASE
        else: self.state = AIState.IDLE

    def _execute_idle(self, monster, game_map, dt):
        self._patrol_timer -= dt
        if self._patrol_timer <= 0: self._pick_new_patrol_direction(); self._patrol_timer = self.patrol_interval
        self._apply_movement(monster, game_map, self._patrol_dir[0], self._patrol_dir[1], dt)

    def _execute_chase(self, monster, player, game_map, dt):
        dx = player.entity.rect.centerx - monster.entity.rect.centerx
        dy = player.entity.rect.centery - monster.entity.rect.centery
        dist = math.hypot(dx, dy) or 1
        self._apply_movement(monster, game_map, dx/dist, dy/dist, dt)

    def _execute_attack(self, monster, player, gt, effects):
        if monster.can_attack(gt):
            monster.attack_target(player, gt)
            if effects is not None:
                from src.fx_engine import monsters_attack_fx
                effects += monsters_attack_fx(monster.entity.rect.centerx, monster.entity.rect.centery, player.entity.rect.centerx, player.entity.rect.centery, getattr(monster,"color",(255,255,255)))

    def _apply_movement(self, monster, game_map, mx, my, dt):
        from src.systems.buff_system import get_effective_speed
        speed = get_effective_speed(monster, self.move_speed)
        e = monster.entity
        e.position.x += mx*speed*dt; e.sync_rect()
        if mx != 0 and not game_map.is_rect_walkable(e.rect): e.position.x -= mx*speed*dt; e.sync_rect()
        e.position.y += my*speed*dt; e.sync_rect()
        if my != 0 and not game_map.is_rect_walkable(e.rect): e.position.y -= my*speed*dt; e.sync_rect()

    def _distance_to(self, monster, player) -> float:
        return math.hypot(monster.entity.rect.centerx-player.entity.rect.centerx, monster.entity.rect.centery-player.entity.rect.centery)

    def _pick_new_patrol_direction(self):
        if random.random() < 0.3: self._patrol_dir = (0.0, 0.0); return
        candidates=[(-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)]
        dx, dy = random.choice(candidates)
        length = math.hypot(dx, dy) or 1
        self._patrol_dir = (dx/length, dy/length)
