"""
游戏主场景 —— 地图探索 / 战斗 / 背包 / Boss。

这是最大的场景，承载原 game.py PLAYING + BOSS_INTRO + BOSS_CINEMATIC 三个状态。
每个方法不超过 40 行，渲染与逻辑分离。
"""

import math
import time
import random
import pygame
from config import (TILE_SIZE, MAP_WIDTH, MAP_HEIGHT, MAX_FLOORS, BOSS_FLOORS,
                     COLOR_BLACK, COLOR_WHITE, COLOR_RED, COLOR_GREEN,
                     COLOR_YELLOW, COLOR_GRAY, COLOR_BLUE,
                     PLAYER_ATTACK_RANGE, PICKUP_RANGE,
                     LOOT_DROP_CHANCE, XP_PER_KILL_BASE, XP_PER_KILL_BOSS,
                     FLOOR_MONSTER_HP_MULT, FLOOR_MONSTER_ATK_MULT,
                     FLOOR_MONSTER_COUNT)
from src.core.scene import Scene
from game import get_font
from src.ui_helpers import (draw_panel, draw_glow_text, draw_progress_bar,
                             ParticleSystem, PANEL_BG, GOLD,
                             DARK_RED, CYBER_BLUE)
from src.world.dungeon_generator import DungeonGenerator
from src.world.tile import TileType
from src.world.special_room import (SpecialRoom, SpecialRoomType,
                                     execute_special_room, get_discovery_message)
from src.entities.monster import Monster, spawn_monster
from src.entities.item import (DroppedItem, Item, EquipmentItem,
                                ConsumableItem, Rarity, generate_random_item,
                                generate_charm_for_skill)
from src.entities.boss import spawn_boss, get_boss_info
from src.entities.player import Direction
from src.entities.components import AttackType
from src.systems.combat_system import find_attack_target, calculate_damage
from src.systems.buff_system import (get_effective_attack, get_effective_speed,
                                      get_buff_display_name, get_buff_short_name,
                                      get_buff_hud_color, format_buff_time,
                                      tick_buffs, apply_triggers)
from src.fx_engine import (player_attack_fx, slash_skill_fx, fireball_fx,
                            heal_fx, monsters_attack_fx, boss_cone_fx,
                            boss_circle_fx, boss_summon_fx, time_stop_fx,
                            hit_flash_fx, draw_fx_on_screen)
from src.sfx_engine import play_sfx
from src.bgm_engine import (play_dungeon_bgm, play_boss_bgm, stop_bgm,
                             init_bgm)


class GameScene(Scene):
    """核心游戏场景 —— 包含地图探索/战斗/背包/Boss战。"""

    def __init__(self, engine):
        super().__init__(engine)
        self._state = "playing"   # playing | boss_intro | boss_cinematic
        self._room_message = ""                # B10: 临时消息文字
        self._room_message_timer = 0.0         # B10: 消息剩余显示秒数

    # ═══════════════════════════════════════════════════════════
    #  生命周期
    # ═══════════════════════════════════════════════════════════

    def update(self, delta_time: float):
        eng = self.engine
        eng._game_time += delta_time

        if self._state == "boss_cinematic":
            self._update_boss_cinematic(delta_time)
        elif self._state == "playing":
            self._update_playing(delta_time)

        self._decay_effects(delta_time)

    def _decay_effects(self, delta_time: float):
        """衰减所有活跃攻击特效 + 时停倒计时。"""
        eng = self.engine
        for fx in eng._attack_effects:
            fx["elapsed"] += delta_time
        eng._attack_effects = [f for f in eng._attack_effects
                               if f["elapsed"] < f["duration"]]
        if eng._time_stop_remaining > 0:
            eng._time_stop_remaining -= delta_time
            if eng._time_stop_remaining <= 0:
                eng._time_stop_remaining = 0
                self._apply_pending_damage()

    def render(self):
        if self._state == "boss_intro":
            self._render_boss_intro()
            return
        self._render_playing()
        if self._state == "boss_cinematic":
            self._render_boss_cinematic_overlay()

    # ═══════════════════════════════════════════════════════════
    #  楼层管理
    # ═══════════════════════════════════════════════════════════

    def enter_floor(self, floor_num: int, seed: int = 0):
        """进入指定关卡 — 生成地图 + 放置实体 + 设置BGM。

        seed=0: 随机生成; seed!=0: 读档恢复 (B8)。
        """
        eng = self.engine
        eng.current_floor = floor_num
        eng._game_time = 0.0
        eng.ground_items = []
        eng.inventory_open = False
        eng.inventory_cursor = 0
        eng.stairs_active = False
        eng._attack_effects = []
        eng._time_stop_remaining = 0.0
        eng._pending_damage = []
        self._room_message = ""
        self._room_message_timer = 0.0

        # B8: seed=0 → 随机, seed!=0 → 读档恢复
        if seed != 0:
            eng._dungeon_seed = seed
        else:
            eng._dungeon_seed = random.randint(0, 2**32 - 1)

        generator = DungeonGenerator(MAP_WIDTH, MAP_HEIGHT, TILE_SIZE)
        eng.game_map = generator.generate(eng._dungeon_seed)
        room_centers = generator.get_room_centers()
        self._place_player_in_room(room_centers)

        idx = min(floor_num - 1, 14)
        n = FLOOR_MONSTER_COUNT[idx]
        is_boss = floor_num in BOSS_FLOORS
        if is_boss:
            eng.monsters = []
        else:
            other = room_centers[1:] if len(room_centers) > 1 else []
            eng.monsters = self._spawn_monsters_scaled(other, n, floor_num)

        eng.stairs_pos = (room_centers[-1] if room_centers
                           else (MAP_WIDTH // 2, MAP_HEIGHT // 2))
        eng.player.combat.current_hp = eng.player.combat.max_hp
        eng.player.reset_attack_timers()

        if is_boss:
            eng._boss_intro_data = get_boss_info(floor_num)
            self._state = "boss_intro"
            play_boss_bgm()
        else:
            self._state = "playing"
            play_dungeon_bgm()
        eng._bgm_stopped_for_title = False

    def _place_player_in_room(self, room_centers: list):
        """玩家置于第一个房间中心。"""
        eng = self.engine
        tx, ty = room_centers[0] if room_centers else (MAP_WIDTH // 2, MAP_HEIGHT // 2)
        px, py = eng.game_map.tile_to_pixel(tx, ty)
        eng.player.entity.position = pygame.Vector2(px, py)
        eng.player.entity.sync_rect()

    def _spawn_monsters_scaled(self, room_centers: list,
                                 count: int, floor: int) -> list:
        """按楼层难度缩放生成怪物。"""
        eng = self.engine
        if not room_centers:
            return []
        hp_mult = FLOOR_MONSTER_HP_MULT[min(floor - 1, 14)]
        atk_mult = FLOOR_MONSTER_ATK_MULT[min(floor - 1, 14)]
        spawned = []
        room_index = 0
        while len(spawned) < count and room_index < 500:
            tx, ty = room_centers[room_index % len(room_centers)]
            off_x, off_y = random.randint(-2, 2), random.randint(-2, 2)
            stx, sty = tx + off_x, ty + off_y
            if eng.game_map.is_walkable(stx, sty):
                px, py = eng.game_map.tile_to_pixel(stx, sty)
                m = spawn_monster(px, py, random.choice(["slime", "slime", "orc"]))
                m.combat.max_hp = int(m.combat.max_hp * hp_mult)
                m.combat.current_hp = m.combat.max_hp
                m.combat.attack = int(m.combat.attack * atk_mult)
                spawned.append(m)
            room_index += 1
        return spawned

    def _get_camera_offset(self) -> tuple:
        """计算摄像机偏移——玩家居中。"""
        eng = self.engine
        if not eng.player:
            return 0, 0
        sw, sh = eng.screen.get_width(), eng.screen.get_height()
        cx = eng.player.entity.rect.centerx - sw // 2
        cy = eng.player.entity.rect.centery - sh // 2
        if eng.game_map:
            cx = max(0, min(cx, eng.game_map.pixel_width - sw))
            cy = max(0, min(cy, eng.game_map.pixel_height - sh))
        return int(cx), int(cy)

    # ═══════════════════════════════════════════════════════════
    #  每帧更新（playing 状态）
    # ═══════════════════════════════════════════════════════════

    def _update_playing(self, delta_time: float):
        """playing 状态帧更新 — 背包打开时暂停怪物AI。"""
        eng = self.engine
        keys = pygame.key.get_pressed()
        if eng.inventory_open:
            eng.player.update(delta_time)
            return
        # 移动 + 碰撞
        move_x, move_y = eng.player.handle_input(keys)
        speed = get_effective_speed(eng.player, eng.player.speed)
        self._apply_movement(move_x, move_y, speed, delta_time)
        # B10: 检测是否步入特殊房间
        self._check_special_room_discovery()
        # 怪物 + 楼层检测（时停期间冻结）
        if eng._time_stop_remaining <= 0:
            self._update_monsters(delta_time)
            self._check_floor_transition()
        eng.player.update(delta_time)
        self._tick_skill_regen(delta_time)
        self._tick_buff_system(delta_time)
        # B10: 房间消息计时器
        if self._room_message_timer > 0:
            self._room_message_timer -= delta_time
        if not eng.stairs_active and self._all_monsters_dead():
            self._activate_stairs()

    def _apply_movement(self, move_x: float, move_y: float,
                        speed: float, dt: float):
        """分轴移动 + 地图碰撞检测。"""
        eng = self.engine
        entity = eng.player.entity
        entity.position.x += move_x * speed * dt
        entity.sync_rect()
        if not eng.game_map.is_rect_walkable(entity.rect):
            entity.position.x -= move_x * speed * dt
            entity.sync_rect()
        entity.position.y += move_y * speed * dt
        entity.sync_rect()
        if not eng.game_map.is_rect_walkable(entity.rect):
            entity.position.y -= move_y * speed * dt
            entity.sync_rect()

    def _tick_skill_regen(self, dt: float):
        """自愈 Lv3 持续回复。"""
        for sk in self.engine.player.skills.active_skills:
            if hasattr(sk, "tick_regen"):
                sk.tick_regen(self.engine.player, dt)

    def _tick_buff_system(self, dt: float):
        """每帧结算所有 Buff — 玩家 + 怪物。"""
        eng = self.engine
        tick_buffs(eng.player, dt)
        for m in eng.monsters:
            tick_buffs(m, dt)
        if not eng.player.combat.is_alive:
            self._on_player_death()
            return
        dead = [m for m in eng.monsters if not m.combat.is_alive]
        for m in dead:
            self._on_monster_killed(m)
        eng.monsters = [m for m in eng.monsters if m.combat.is_alive]

    def _on_player_death(self):
        """玩家死亡 → 切到死亡场景。"""
        from src.scenes.death_scene import DeathScene
        stop_bgm()
        self.engine._bgm_stopped_for_title = True
        self.engine.change_scene(DeathScene(self.engine))

    # ═══════════════════════════════════════════════════════════
    #  渲染（playing 状态）
    # ═══════════════════════════════════════════════════════════

    def _render_playing(self):
        """渲染游戏画面 — 地图→怪物→掉落物→玩家→HUD→背包。"""
        eng = self.engine
        screen = eng.screen
        screen.fill(COLOR_BLACK)
        cam_x, cam_y = self._get_camera_offset()

        if eng.game_map:
            eng.game_map.render(screen, cam_x, cam_y)
        for monster in eng.monsters:
            monster.render(screen, cam_x, cam_y)
            self._draw_monster_buffs(monster, cam_x, cam_y)
        self._render_ground_items(cam_x, cam_y)
        if eng.player:
            eng.player.render(screen, cam_x, cam_y)
        self._render_attack_effects(cam_x, cam_y)
        self._render_hud()

        if not eng.inventory_open:
            self._draw_text_center(
                "WASD移动 | 空格攻击 | 1-4技能 | E拾取 | I背包 | >下楼 | F11全屏 | Esc返回",
                size=13, color=COLOR_WHITE,
                offset_y=screen.get_height() // 2 - 25)
        if eng.inventory_open:
            self._render_inventory_panel()
        if eng._time_stop_remaining > 0:
            self._render_time_stop_overlay()
        pygame.display.flip()

    # ═══════════════════════════════════════════════════════════
    #  输入处理
    # ═══════════════════════════════════════════════════════════

    def on_keydown(self, key: int):
        """游戏中按键 — 区分普通模式和背包模式。"""
        eng = self.engine
        if self._state == "boss_intro":
            self._on_boss_intro_keydown(key)
            return
        if eng.inventory_open:
            self._handle_inventory_key(key)
            return
        if key == pygame.K_ESCAPE:
            self._save_and_quit_to_title()
        elif key == pygame.K_SPACE:
            self._handle_player_attack()
        elif key == pygame.K_e:
            # B8: 优先特殊房间交互, 否则走拾取
            if eng.player and eng.game_map:
                tx, ty = eng.game_map.pixel_to_tile(
                    eng.player.entity.rect.centerx,
                    eng.player.entity.rect.centery)
                room = eng.game_map.get_special_room_at(tx, ty)
                if room and not room.triggered:
                    self._interact_special()
                else:
                    self._handle_pickup()
            else:
                self._handle_pickup()
        elif key == pygame.K_i:
            eng.inventory_open = True
            eng.inventory_cursor = 0
        elif pygame.K_1 <= key <= pygame.K_4:
            self._use_skill(key - pygame.K_1)

    def _save_and_quit_to_title(self):
        """Esc → 自动存档 → 返回标题。"""
        from saves.save_manager import save_game
        from src.scenes.title_scene import TitleScene
        eng = self.engine
        if eng.player and eng.player.combat.is_alive:
            eng._max_unlocked_floor = max(eng._max_unlocked_floor, eng.current_floor)
            spr, spd = self._collect_special_state()
            save_game(eng.player, eng.current_floor, eng._max_unlocked_floor,
                      getattr(eng, '_dungeon_seed', 0), spr, spd)
        eng.change_scene(TitleScene(eng))

    # ═══════════════════════════════════════════════════════════
    #  战斗
    # ═══════════════════════════════════════════════════════════

    def _handle_player_attack(self):
        """普攻 — 找最近目标 → 伤害计算 → SFX + 特效。"""
        eng = self.engine
        player = eng.player
        if not player or not player.combat.is_alive or not player.can_attack(eng._game_time):
            return
        cr = player.entity.rect
        eng._attack_effects += player_attack_fx(
            cr.centerx, cr.centery, int(PLAYER_ATTACK_RANGE * TILE_SIZE))
        play_sfx("melee")
        target = find_attack_target(player.entity.rect, eng.monsters, PLAYER_ATTACK_RANGE)
        if target is None:
            return
        dmg = calculate_damage(
            get_effective_attack(player),
            target.combat.get_effective_defense(player.attack_type),
            player.attack_type)
        player._last_attack_time = eng._game_time
        if eng._time_stop_remaining > 0:
            eng._pending_damage.append((target, dmg))
        else:
            target.combat.take_damage(dmg)
            play_sfx("hit")
            eng._attack_effects += hit_flash_fx(
                int(target.entity.position.x), int(target.entity.position.y),
                target.entity.size[0])
            if not target.combat.is_alive:
                self._on_monster_killed(target)
                eng.monsters.remove(target)

    # ── 技能 ─────────────────────────────────────────────

    def _use_skill(self, index: int):
        """释放技能 — 路由到时停/普通分支。"""
        eng = self.engine
        player = eng.player
        if not player or index >= len(player.skills.active_skills):
            return
        skill = player.skills.active_skills[index]
        if skill.name == "The World":
            self._activate_time_stop(skill, index)
        elif eng._time_stop_remaining > 0:
            self._use_skill_in_time_stop(skill, index)
        else:
            self._use_skill_normal(skill, index)

    def _activate_time_stop(self, skill, index: int):
        """激活 The World — 冻结全屏 + 暂存伤害。"""
        eng = self.engine
        result = eng.player.skills.use_active(
            index, eng.player, eng.monsters, eng.game_map, eng._game_time)
        if result and "冷却中" not in result:
            eng._time_stop_remaining = skill.get_stop_duration()
            eng._pending_damage = []
            play_sfx("timestop", 1.0)
            fx = time_stop_fx(eng.player.entity.rect.centerx,
                              eng.player.entity.rect.centery)
            for f in fx:
                f["duration"] = min(f["duration"], eng._time_stop_remaining * 0.3)
            eng._attack_effects += fx

    def _use_skill_in_time_stop(self, skill, index: int):
        """时停期间技能 — 伤害暂存不结算。"""
        eng = self.engine
        pre_hp = {id(m): m.combat.current_hp for m in eng.monsters}
        result = eng.player.skills.use_active(
            index, eng.player, eng.monsters, eng.game_map, eng._game_time)
        if result and "冷却中" not in result:
            self._add_skill_effect(skill)
        if result:
            for m in eng.monsters:
                if id(m) in pre_hp:
                    delta = pre_hp[id(m)] - m.combat.current_hp
                    if delta > 0:
                        eng._pending_damage.append((m, delta))
                        m.combat.current_hp = pre_hp[id(m)]
                        m.combat.is_alive = True

    def _use_skill_normal(self, skill, index: int):
        """正常释放技能 + 死亡处理。"""
        eng = self.engine
        result = eng.player.skills.use_active(
            index, eng.player, eng.monsters, eng.game_map, eng._game_time)
        if result and "冷却中" not in result:
            self._add_skill_effect(skill)
        if result:
            dead = [m for m in eng.monsters if not m.combat.is_alive]
            for m in dead:
                self._on_monster_killed(m)
                eng.monsters.remove(m)

    def _add_skill_effect(self, skill):
        """根据技能类型+等级写入视觉特效。"""
        eng = self.engine
        if not eng.player:
            return
        cx = eng.player.entity.rect.centerx
        cy = eng.player.entity.rect.centery
        lv, name = skill.level, skill.name
        if name == "斩击":
            eng._attack_effects += slash_skill_fx(cx, cy, eng.player.direction, lv)
            play_sfx("slash")
        elif name == "神罚":
            t = find_attack_target(eng.player.entity.rect, eng.monsters, 10.0)
            tx = t.entity.rect.centerx if t else cx + 100
            ty = t.entity.rect.centery if t else cy
            eng._attack_effects += fireball_fx(cx, cy, tx, ty, lv)
            play_sfx("bolt")
        elif name == "自愈":
            eng._attack_effects += heal_fx(cx, cy, lv)
            play_sfx("heal")

    def _apply_pending_damage(self):
        """时停结束 — 一次性结算所有暂存伤害。"""
        eng = self.engine
        if not eng._pending_damage:
            return
        for target, dmg in eng._pending_damage:
            if target.combat.is_alive:
                target.combat.take_damage(dmg)
        dead = [m for m in eng.monsters if not m.combat.is_alive]
        for m in dead:
            self._on_monster_killed(m)
            eng.monsters.remove(m)
        eng._pending_damage = []

    # ═══════════════════════════════════════════════════════════
    #  怪物管理
    # ═══════════════════════════════════════════════════════════

    def _update_monsters(self, delta_time: float):
        """更新所有怪物AI — 检测玩家受伤播放音效。"""
        eng = self.engine
        if not eng.player or not eng.player.combat.is_alive:
            return
        hp_before = eng.player.combat.current_hp
        for m in eng.monsters:
            m.update_ai(eng.player, eng.game_map, delta_time,
                       eng._game_time, eng.monsters, eng._attack_effects)
        if eng.player.combat.current_hp < hp_before:
            play_sfx("hit")

    def _on_monster_killed(self, monster: Monster):
        """怪物死亡 — 经验 + 掉落 + 粒子 + Boss奖励。"""
        eng = self.engine
        self._spawn_death_particles(monster)
        if monster.is_boss:
            if eng.player and eng.player.give_xp(XP_PER_KILL_BOSS):
                play_sfx("levelup")
            self._drop_boss_reward(monster)
            return
        xp_gained = XP_PER_KILL_BASE + int(monster.combat.max_hp * 0.5)
        if eng.player and eng.player.give_xp(xp_gained):
            play_sfx("levelup")
        if random.random() > LOOT_DROP_CHANCE:
            return
        tx, ty = eng.game_map.pixel_to_tile(
            monster.entity.position.x, monster.entity.position.y)
        eng.ground_items.append(DroppedItem(generate_random_item(), tx, ty))

    def _drop_boss_reward(self, monster: Monster):
        """Boss击杀奖励 — 传说武器 + 护符 + 药水 + 技能。"""
        eng = self.engine
        tx, ty = eng.game_map.pixel_to_tile(
            monster.entity.position.x, monster.entity.position.y)
        weapon = EquipmentItem("魔渊之刃", Rarity.LEGENDARY,
                               "weapon", atk_bonus=18, pdef_bonus=3, mdef_bonus=0)
        eng.ground_items.append(DroppedItem(weapon, tx, ty))
        skill_names = [type(s).__name__ for s in eng.player.skills.active_skills]
        if skill_names:
            charm = generate_charm_for_skill(random.choice(skill_names), Rarity.LEGENDARY)
            if charm:
                eng.ground_items.append(DroppedItem(charm, tx + 1, ty))
        potion = ConsumableItem("神谕药剂", Rarity.LEGENDARY, "heal", 80)
        eng.ground_items.append(DroppedItem(potion, tx + 2, ty))
        from src.entities.skill import get_learned_skill_names, random_skill
        if eng.player.skills.can_learn():
            names = get_learned_skill_names(eng.player.skills)
            eng.player.skills.learn(random_skill(names))
            eng.player.skills.apply_all_passives(eng.player)

    def _spawn_death_particles(self, monster: Monster):
        """怪物死亡彩色粒子爆散。"""
        eng = self.engine
        cx = monster.entity.rect.centerx
        cy = monster.entity.rect.centery
        n = 10 if monster.is_boss else 5
        for _ in range(n):
            dx, dy = random.randint(-20, 20), random.randint(-20, 20)
            eng._attack_effects.append({
                "kind": "spark", "x": cx + dx * 3, "y": cy + dy * 3,
                "radius": 2 + random.randint(0, 3), "color": monster.color,
                "duration": 0.4, "elapsed": 0.0,
            })

    def _get_boss(self):
        """获取当前存活的Boss怪物。"""
        for m in self.engine.monsters:
            if m.is_boss and m.combat.is_alive:
                return m
        return None

    # ═══════════════════════════════════════════════════════════
    #  楼梯 & 楼层切换
    # ═══════════════════════════════════════════════════════════

    def _all_monsters_dead(self) -> bool:
        return all(not m.combat.is_alive for m in self.engine.monsters)

    def _activate_stairs(self):
        """激活楼梯 + 自动存档（Boss存活时禁止）。"""
        eng = self.engine
        if not eng.stairs_pos or eng.stairs_active:
            return
        boss = self._get_boss()
        if boss and boss.combat.is_alive:
            return
        eng.game_map.set_tile(eng.stairs_pos[0], eng.stairs_pos[1], TileType.STAIRS_DOWN)
        eng.stairs_active = True
        eng._max_unlocked_floor = max(eng._max_unlocked_floor, eng.current_floor)
        from saves.save_manager import save_game
        spr, spd = self._collect_special_state()
        save_game(eng.player, eng.current_floor, eng._max_unlocked_floor,
                  getattr(eng, '_dungeon_seed', 0), spr, spd)

    def _check_floor_transition(self):
        """检测玩家是否站在激活楼梯上按 > 键。"""
        eng = self.engine
        if not eng.stairs_active or not eng.player or not eng.stairs_pos:
            return
        keys = pygame.key.get_pressed()
        if not keys[pygame.K_PERIOD]:
            return
        px, py = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx, eng.player.entity.rect.centery)
        if (px, py) != eng.stairs_pos:
            return
        next_floor = eng.current_floor + 1
        if next_floor > MAX_FLOORS:
            from src.scenes.victory_scene import VictoryScene
            self.engine.change_scene(VictoryScene(self.engine))
        else:
            self.enter_floor(next_floor)

    # ═══════════════════════════════════════════════════════════
    #  拾取
    # ═══════════════════════════════════════════════════════════

    def _handle_pickup(self):
        """拾取玩家附近最近的地面物品。"""
        eng = self.engine
        if not eng.player:
            return
        best, best_dist = None, PICKUP_RANGE * TILE_SIZE
        pr = eng.player.entity.rect
        for dropped in eng.ground_items:
            px = dropped.tile_x * TILE_SIZE + TILE_SIZE // 2
            py = dropped.tile_y * TILE_SIZE + TILE_SIZE // 2
            dist = ((pr.centerx - px) ** 2 + (pr.centery - py) ** 2) ** 0.5
            if dist < best_dist:
                best_dist, best = dist, dropped
        if best and eng.player.inventory.add(best.item, eng.player):
            eng.ground_items.remove(best)
            play_sfx("pickup", 0.4)

    # ═══════════════════════════════════════════════════════════
    #  特殊房间交互 (B8/B9/B10)
    # ═══════════════════════════════════════════════════════════

    def _interact_special(self):
        """E 键触发特殊房间 —— 每个房间仅一次。"""
        eng = self.engine
        if not eng.player or not eng.game_map:
            return
        tx, ty = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx,
            eng.player.entity.rect.centery)
        room = eng.game_map.get_special_room_at(tx, ty)
        if not room or room.triggered:
            return
        msg = execute_special_room(room.type, eng.player)
        room.triggered = True
        self._show_room_message(msg)

    def _check_special_room_discovery(self):
        """每帧检测玩家是否首次步入特殊房间 (B10)。"""
        eng = self.engine
        if not eng.game_map or not eng.player:
            return
        tx, ty = eng.game_map.pixel_to_tile(
            eng.player.entity.rect.centerx,
            eng.player.entity.rect.centery)
        room = eng.game_map.get_special_room_at(tx, ty)
        if not room or room.discovered:
            return
        room.discovered = True
        self._show_room_message(get_discovery_message(room.type))

    def _show_room_message(self, msg: str):
        """显示临时消息 (2.5秒后自动消失)。"""
        self._room_message = msg
        self._room_message_timer = 2.5

    def _collect_special_state(self):
        """收集当前楼层特殊房间 triggered / discovered 状态。"""
        eng = self.engine
        spr, spd = [], []
        if eng.game_map:
            for sr in eng.game_map.special_rooms:
                spr.append(sr.triggered)
                spd.append(sr.discovered)
        return spr, spd

    def _draw_room_message(self, screen):
        """渲染房间消息条 —— 屏幕底部中央。"""
        if self._room_message_timer <= 0 or not self._room_message:
            return
        sw, sh = screen.get_width(), screen.get_height()
        font = get_font(18)
        if not font:
            return
        alpha = min(1.0, self._room_message_timer / 0.6)
        text = font.render(self._room_message, True,
                           (int(255 * alpha), int(255 * alpha),
                            int(200 * alpha)))
        tw = text.get_width()
        px = sw // 2 - tw // 2
        py = sh - 70
        bg = pygame.Surface((tw + 32, 28), pygame.SRCALPHA)
        bg.fill((10, 10, 20, int(180 * alpha)))
        screen.blit(bg, (px - 16, py - 4))
        screen.blit(text, (px, py))

    # ═══════════════════════════════════════════════════════════
    #  HUD 渲染
    # ═══════════════════════════════════════════════════════════

    def _render_hud(self):
        """左上角：血条 + 属性 + 等级/XP + 楼层 + Boss血条 + 技能栏 + Buff。"""
        eng = self.engine
        if not eng.player:
            return
        combat = eng.player.combat
        bar_x, bar_y, bar_w, bar_h = 10, 10, 200, 16
        self._draw_player_hp_bar(combat, bar_x, bar_y, bar_w, bar_h)
        lvl, xp, xp_next = eng.player.get_level_info()
        self._draw_xp_bar(bar_x, bar_y + bar_h + 4, bar_w, 10, xp, xp_next, lvl)
        boss = self._get_boss()
        if boss:
            self._render_boss_hp_bar(boss)
        font = get_font(16)
        floor_text = f"第 {eng.current_floor}/{MAX_FLOORS} 层"
        eng.screen.blit(font.render(floor_text, True, COLOR_YELLOW),
                        (bar_x + bar_w + 10, bar_y + bar_h + 4))
        if eng.stairs_active:
            s = font.render("楼梯已开启！按 > 下楼", True, (100, 255, 100))
            eng.screen.blit(s, (bar_x, bar_y + bar_h + 28))
        self._render_skill_bar(bar_x, bar_y + bar_h + 50)
        self._draw_player_buffs()
        # B10: 房间消息条
        self._draw_room_message(eng.screen)

    def _draw_player_hp_bar(self, combat, x: int, y: int, w: int, h: int):
        """美化玩家血条。"""
        screen = self.engine.screen
        ratio = combat.current_hp / combat.max_hp
        clr = (50, 200, 50) if ratio > 0.5 else (200, 200, 50) if ratio > 0.25 else (200, 50, 50)
        draw_progress_bar(screen, x, y, w, h, ratio, clr, (40, 20, 20))
        pd = combat.get_effective_defense(AttackType.PHYSICAL)
        md = combat.get_effective_defense(AttackType.MAGICAL)
        txt = get_font(16).render(
            f"HP:{combat.current_hp}/{combat.max_hp}  ATK:{combat.get_effective_attack()}"
            f"  PD:{pd} MD:{md}", True, (220, 220, 220))
        screen.blit(txt, (x + w + 10, y))

    def _draw_xp_bar(self, x: int, y: int, w: int, h: int,
                     xp: int, xp_next: int, level: int):
        """美化经验条。"""
        screen = self.engine.screen
        ratio = min(1.0, xp / max(1, xp_next))
        draw_progress_bar(screen, x, y, w, h, ratio, (80, 120, 255), (30, 30, 60))
        txt = get_font(13).render(f"Lv{level}  XP:{xp}/{xp_next}", True, (180, 200, 255))
        screen.blit(txt, (x + 2, y + h + 2))

    def _render_skill_bar(self, start_x: int, start_y: int):
        """美化技能栏 — 编号框 + 名称 + 冷却条。"""
        eng = self.engine
        screen = eng.screen
        active = eng.player.skills.active_skills
        if not active:
            return
        f, bw, bh = get_font(14), 90, 10
        for i, sk in enumerate(active):
            ry = start_y + i * (bh + 20)
            ready = sk.can_use(eng._game_time)
            num_bg = (50, 160, 50) if ready else (60, 60, 60)
            nr = pygame.Rect(start_x, ry, 22, 18)
            pygame.draw.rect(screen, num_bg, nr, border_radius=3)
            screen.blit(f.render(str(i + 1), True, (255, 255, 255)), (start_x + 7, ry + 1))
            bonus = (sk.get_level_bonus_text() if hasattr(sk, "get_level_bonus_text")
                     else f"Lv{sk.level}")
            label = f.render(f"{sk.name} {bonus}", True,
                             (180, 220, 255) if ready else (100, 100, 100))
            screen.blit(label, (start_x + 26, ry + 2))
            ratio = 1.0 - sk.remaining_cooldown(eng._game_time) / sk.cooldown
            draw_progress_bar(screen, start_x + 26, ry + 16, bw, bh, ratio,
                              (60, 180, 255) if ready else (70, 70, 70), (30, 30, 45))

    def _render_boss_hp_bar(self, boss: Monster):
        """顶部中央 Boss 血条 — 双线框+渐变填充+脉冲。"""
        screen = self.engine.screen
        c = boss.combat
        bw, bh = 400, 20
        bx = (screen.get_width() - bw) // 2
        by = 4
        ratio = c.current_hp / c.max_hp
        pulse = int(220 + 25 * math.sin(time.time() * 5))
        pygame.draw.rect(screen, (pulse, 40, 40), (bx - 2, by - 2, bw + 4, bh + 4), 2)
        pygame.draw.rect(screen, (30, 5, 5), (bx, by, bw, bh))
        fill_w = int(bw * ratio)
        segments = 10
        seg_w = fill_w // segments if segments else 0
        for i in range(segments):
            t = i / segments
            cr = int(200 - t * 60); cg = int(40 + t * 120); cb = int(30 + t * 20)
            sx = bx + i * seg_w
            sw = seg_w + (fill_w - (i + 1) * seg_w if i == segments - 1 else 0)
            if sw > 0:
                pygame.draw.rect(screen, (cr, cg, cb), (sx, by, sw, bh))
        pygame.draw.rect(screen, (255, 150, 80, 100), (bx, by, fill_w, bh // 3))
        f = get_font(18)
        txt = f.render(f"⚔ {boss.name}  HP:{c.current_hp}/{c.max_hp}", True, (255, 220, 100))
        screen.blit(txt, (bx + (bw - txt.get_width()) // 2, by + bh + 3))

    def _draw_player_buffs(self):
        """玩家 Buff HUD — 技能栏下方。"""
        eng = self.engine
        if not eng.player or not eng.player.active_buffs:
            return
        x, y = 10, 56 + len(eng.player.skills.active_skills) * 28 + 4
        for b in eng.player.active_buffs:
            line = f"{get_buff_display_name(b.id)} x{b.stacks}  {format_buff_time(b.remaining)}"
            surf = get_font(14).render(line, True, get_buff_hud_color(b.id))
            eng.screen.blit(surf, (x, y))
            y += 18

    def _draw_monster_buffs(self, monster, cam_x, cam_y):
        """怪物头顶 Buff 简写标签。"""
        if not monster.active_buffs:
            return
        label = " ".join(f"{get_buff_short_name(b.id)}x{b.stacks}"
                         for b in monster.active_buffs)
        surf = get_font(12).render(label, True, get_buff_hud_color(monster.active_buffs[0].id))
        px = monster.entity.rect.x - cam_x + (monster.entity.rect.w - surf.get_width()) / 2
        py = monster.entity.rect.y - cam_y - 16
        self.engine.screen.blit(surf, (px, py))

    # ═══════════════════════════════════════════════════════════
    #  背包面板
    # ═══════════════════════════════════════════════════════════

    def _render_inventory_panel(self):
        """美化背包面板 — 装备槽 + 物品列表。"""
        eng = self.engine
        screen = eng.screen
        sw, sh = screen.get_width(), screen.get_height()
        dark = pygame.Surface((sw, sh)); dark.set_alpha(180); dark.fill((0, 0, 0))
        screen.blit(dark, (0, 0))
        inv = eng.player.inventory
        pw, ph = 440, 480
        pr = pygame.Rect(sw // 2 - pw // 2, sh // 2 - ph // 2, pw, ph)
        draw_panel(screen, pr, title="背 包  I关闭")
        x0, y0 = pr.x + 30, pr.y + 40
        self._inv_draw_equipped(inv, x0, y0, pr)
        self._inv_draw_items(inv, x0, y0)
        tips = "↑↓选择  X装备  U使用  D丢弃  I关闭"
        tip = get_font(16).render(tips, True, (140, 140, 140))
        screen.blit(tip, (pr.x + (pw - tip.get_width()) // 2, pr.bottom - 30))

    def _inv_draw_equipped(self, inv, x0: int, y0: int, pr: pygame.Rect):
        """绘制装备槽。"""
        screen = self.engine.screen
        f18 = get_font(18)
        eq_text = "◆ 装备: "
        for slot, eq in inv.equipped.items():
            eq_text += f"【{slot}】{eq.get_description()}  " if eq else f"【{slot}】空  "
        eq = f18.render(eq_text, True, GOLD)
        screen.blit(eq, (x0, y0))
        pygame.draw.line(screen, (60, 60, 90), (x0, y0 + 28),
                         (pr.right - 30, y0 + 28), 1)

    def _inv_draw_items(self, inv, x0: int, y0: int):
        """绘制物品列表。"""
        screen = self.engine.screen
        f18 = get_font(18)
        for idx, item in enumerate(inv.items):
            ry = y0 + 38 + idx * 30
            mk = "▶" if idx == self.engine.inventory_cursor else " "
            t = f18.render(f"{mk} [{idx+1:>2}] {item.get_description()}", True, item.color)
            screen.blit(t, (x0, ry))
        if not inv.items:
            em = f18.render("背包空空如也", True, (120, 120, 120))
            screen.blit(em, (x0, y0 + 38))

    def _handle_inventory_key(self, key: int):
        """背包面板按键 — 导航 / 装备 / 使用 / 丢弃。"""
        eng = self.engine
        inv = eng.player.inventory
        if key in (pygame.K_i, pygame.K_ESCAPE):
            eng.inventory_open = False
        elif key == pygame.K_UP:
            eng.inventory_cursor = max(0, eng.inventory_cursor - 1)
        elif key == pygame.K_DOWN:
            eng.inventory_cursor = min(
                max(0, len(inv.items) - 1), eng.inventory_cursor + 1)
        elif key == pygame.K_x:
            inv.equip(eng.inventory_cursor, eng.player)
            eng.inventory_cursor = self._clamp_cursor(
                eng.inventory_cursor, len(inv.items))
        elif key == pygame.K_u:
            inv.use(eng.inventory_cursor, eng.player)
            eng.inventory_cursor = self._clamp_cursor(
                eng.inventory_cursor, len(inv.items))
        elif key == pygame.K_d:
            inv.remove(eng.inventory_cursor)
            eng.inventory_cursor = self._clamp_cursor(
                eng.inventory_cursor, len(inv.items))

    # ═══════════════════════════════════════════════════════════
    #  掉落物 & 攻击特效渲染
    # ═══════════════════════════════════════════════════════════

    def _render_ground_items(self, camera_x: int, camera_y: int):
        """绘制掉落物 — 光晕+脉冲+高光。"""
        eng = self.engine
        screen = eng.screen
        for dropped in eng.ground_items:
            px = dropped.tile_x * TILE_SIZE - camera_x
            py = dropped.tile_y * TILE_SIZE - camera_y
            size = TILE_SIZE - 4
            cx, cy = px + TILE_SIZE // 2, py + TILE_SIZE // 2
            pulse = 6 + int(3 * math.sin(time.time() * 5 + px * 0.1))
            glow = pygame.Rect(cx - pulse, cy - pulse, pulse * 2, pulse * 2)
            c = dropped.item.color
            pygame.draw.rect(screen, (c[0]//3, c[1]//3, c[2]//3), glow, 1, border_radius=3)
            rect = pygame.Rect(px + 2, py + 2, size, size)
            pygame.draw.rect(screen, c, rect, border_radius=4)
            hl = tuple(min(255, v + 80) for v in c[:3])
            pygame.draw.rect(screen, hl, (px + 4, py + 3, size - 8, 5), border_radius=2)
            pygame.draw.rect(screen, (0, 0, 0), rect, 1, border_radius=4)
            txt = get_font(16).render(dropped.item.tile_char, True, (255, 255, 255))
            screen.blit(txt, (px + 10, py + 6))

    def _render_attack_effects(self, camera_x: int, camera_y: int):
        """委托 fx_engine 绘制所有活跃攻击特效。"""
        for fx in self.engine._attack_effects:
            draw_fx_on_screen(self.engine.screen, fx, camera_x, camera_y)

    def _render_time_stop_overlay(self):
        """时停 B&W 去色层 + 中央大字倒计时。"""
        eng = self.engine
        screen = eng.screen
        sw, sh = screen.get_width(), screen.get_height()
        overlay = pygame.Surface((sw, sh))
        overlay.set_alpha(130); overlay.fill((90, 90, 100))
        screen.blit(overlay, (0, 0))
        remain = max(0, eng._time_stop_remaining)
        title = get_font(24).render("The World · 时停", True, (255, 255, 255))
        screen.blit(title, (sw // 2 - title.get_width() // 2, 60))
        big_font = get_font(80)
        pulse = 1.0 + 0.06 * math.sin(time.time() * 6)
        big = big_font.render(f"{remain:.0f}", True, (255, 255, 255))
        scaled = pygame.transform.smoothscale(
            big, (int(big.get_width() * pulse), int(big.get_height() * pulse)))
        screen.blit(scaled, (sw // 2 - scaled.get_width() // 2,
                             sh // 2 - scaled.get_height() // 2 - 20))

    # ═══════════════════════════════════════════════════════════
    #  Boss 介绍 & 特写
    # ═══════════════════════════════════════════════════════════

    def _render_boss_intro(self):
        """Boss 介绍画面 — 粒子背景 + 属性面板。"""
        eng = self.engine
        screen = eng.screen
        screen.fill(COLOR_BLACK)
        eng._bg_particles.draw(screen)
        if not eng._boss_intro_data:
            return
        d = eng._boss_intro_data
        sw, sh = screen.get_width(), screen.get_height()
        pw, ph = 500, 380
        pr = pygame.Rect(sw // 2 - pw // 2, sh // 2 - ph // 2, pw, ph)
        draw_panel(screen, pr, title="⚠ Boss 遭遇 ⚠")
        draw_glow_text(screen, d["title"], sw // 2, pr.y + 45,
                       font_size=30, color=d["color"], glow_color=(60, 0, 0), center=True)
        f16 = get_font(16)
        stats = [f"HP: {d['max_hp']}    ATK: {d['attack']}",
                 (f"物防: {d.get('physical_defense',0)}    "
                  f"魔防: {d.get('magical_defense',0)}"),
                 f"技能: {d['skills']}"]
        for i, line in enumerate(stats):
            t = f16.render(line, True, (200, 200, 200))
            screen.blit(t, (sw // 2 - t.get_width() // 2, pr.y + 110 + i * 28))
        f18 = get_font(18)
        for i, line in enumerate(d["lore"].split('\n')):
            t = f18.render(line, True, (160, 160, 180))
            screen.blit(t, (sw // 2 - t.get_width() // 2, pr.y + 210 + i * 26))
        pulse = 0.8 + 0.2 * math.sin(eng._title_anim * 4)
        hint = get_font(20).render("按 Enter 进入战斗...", True, DARK_RED)
        screen.blit(hint, (sw // 2 - hint.get_width() // 2, sh - 60))
        pygame.display.flip()

    def _on_boss_intro_keydown(self, key: int):
        """Boss 介绍画面 Enter → 生成 Boss + 切换到特写。"""
        eng = self.engine
        if key == pygame.K_RETURN and eng._boss_intro_data:
            self._spawn_boss_from_intro()
            eng._boss_cinematic_timer = 1.0
            self._state = "boss_cinematic"

    def _spawn_boss_from_intro(self):
        """根据当前楼层生成 Boss 实体。"""
        eng = self.engine
        room_tx = eng.stairs_pos[0] if eng.stairs_pos else MAP_WIDTH // 2
        room_ty = eng.stairs_pos[1] if eng.stairs_pos else MAP_HEIGHT // 2
        boss = spawn_boss(room_tx, room_ty, eng.current_floor)
        eng.monsters.append(boss)

    def _update_boss_cinematic(self, delta_time: float):
        """Boss 1秒特写倒计时 → 切换到 playing。"""
        eng = self.engine
        eng._boss_cinematic_timer -= delta_time
        if eng._boss_cinematic_timer <= 0:
            eng._boss_cinematic_timer = 0
            eng._boss_intro_data = None
            self._state = "playing"

    def _render_boss_cinematic_overlay(self):
        """Boss 特写 — 全屏暗色遮罩 + 脉冲警告文字。"""
        eng = self.engine
        screen = eng.screen
        sw, sh = screen.get_width(), screen.get_height()
        dark = pygame.Surface((sw, sh))
        dark.set_alpha(160); dark.fill((0, 0, 0))
        screen.blit(dark, (0, 0))
        pulse = 1.0 + 0.08 * math.sin(time.time() * 8)
        big = get_font(48)
        txt = big.render("BOSS 来了！", True, COLOR_RED)
        s2 = (int(txt.get_width() * pulse), int(txt.get_height() * pulse))
        scaled = pygame.transform.smoothscale(txt, s2)
        screen.blit(scaled, (sw // 2 - s2[0] // 2, sh // 2 - s2[1] // 2))

    # ═══════════════════════════════════════════════════════════
    #  辅助工具
    # ═══════════════════════════════════════════════════════════

    def _draw_text_center(self, text: str, size: int, color: tuple,
                          offset_y: int = 0):
        """在窗口中央绘制单行文本。"""
        screen = self.engine.screen
        font = get_font(size)
        surf = font.render(text, True, color)
        rect = surf.get_rect(center=(screen.get_width() // 2,
                                      screen.get_height() // 2 + offset_y))
        screen.blit(surf, rect)
