"""
G6 sync: SimAI + SimRunner — automated balance simulation (C++ parity)
G7.4: DecisionAgent upgrade — build-aware behavioral profiles + action evaluator
"""
import math, random, time
from dataclasses import dataclass, field


@dataclass
class RunStats:
    seed: int = 0; floor_reached: int = 0; bosses_killed: int = 0
    total_kills: int = 0; elite_kills: int = 0; relics_collected: int = 0
    build_type: int = 0; build_name: str = ""

@dataclass
class BalanceReport:
    total_runs: int = 0; avg_floor: int = 0
    boss_kill_rate: list = field(default_factory=lambda: [0, 0, 0])
    build_distribution: list = field(default_factory=lambda: [0] * 13)
    death_floor_distribution: list = field(default_factory=lambda: [0] * 15)
    runs: list = field(default_factory=list)

    def summary(self) -> str:
        r = self
        lines = [f"═══ BALANCE REPORT: {r.total_runs} runs ═══",
                 f"  Average floor: {r.avg_floor}",
                 f"  Boss kills: F5={pct(r.boss_kill_rate[0],r.total_runs)}% F10={pct(r.boss_kill_rate[1],r.total_runs)}% F15={pct(r.boss_kill_rate[2],r.total_runs)}%",
                 f"  Build distribution:"]
        names = ["NONE","Berserker","FireMage","Poison","TimeM","Support","Projectile","IceMage","Lightning","Bleed","Shadow","Juggernaut","Summon"]
        for i in range(1, 13):
            if r.build_distribution[i] > 0:
                lines.append(f"    {names[i]}: {pct(r.build_distribution[i],r.total_runs)}%")
        lines.append("  Death floors:")
        for f in range(15):
            if r.death_floor_distribution[f] > 0:
                lines.append(f"    F{f+1}: {r.death_floor_distribution[f]}")
        return "\n".join(lines)


def pct(n, total): return f"{n*100.0/total:.1f}" if total > 0 else "0.0"

# ═══════════════════════════════════════════════════════════
#  G7.4: BuildType-aware behavioral profiles
# ═══════════════════════════════════════════════════════════

_BUILD_PROFILES = {
    "ICE_MAGE":       dict(range=0.9, aoe=0.8, skill=0.7, aggro=0.2),
    "FIRE_MAGE":      dict(range=0.7, aoe=0.7, skill=0.8, aggro=0.3),
    "LIGHTNING_MAGE": dict(range=0.6, aoe=0.6, skill=0.7, aggro=0.4),
    "BERSERKER":      dict(range=0.0, aoe=0.3, skill=0.3, aggro=0.9),
    "BLEED_BLADE":    dict(range=0.1, aoe=0.3, skill=0.5, aggro=0.7),
    "SHADOW_STRIKER": dict(range=0.0, aoe=0.0, skill=0.6, aggro=0.6),
    "SUPPORT":        dict(range=0.4, aoe=0.2, aggro=0.3),
    "JUGGERNAUT":     dict(range=0.0, aoe=0.4, skill=0.2, aggro=0.8),
    "SUMMON_LORD":     dict(range=0.6, aoe=0.2, skill=0.8, aggro=0.2),
    "POISON_MASTER":   dict(range=0.5, aoe=0.4, skill=0.5, aggro=0.4),
    "TIME_MASTER":     dict(range=0.5, aoe=0.2, skill=0.7, aggro=0.3),
    "PROJECTILE":      dict(range=0.6, aoe=0.3, skill=0.5, aggro=0.4),
}


class DecisionAgent:
    """G7.4: BuildType-aware AI with behavioral profiles + action evaluation."""
    def __init__(self):
        self._frame = 0; self._dir_timer = 0; self._current_dir = -1
        self._prefer_range = 0.3; self._prefer_aoe = 0.2
        self._prefer_skill = 0.4; self._aggro_bias = 0.5
        self._prefer_heal = 0.35

    def start(self, player=None):
        self._frame = 0; self._dir_timer = 0; self._current_dir = -1
        self._resolve_profile(player)

    def _resolve_profile(self, player):
        if not player: return
        try:
            from src.game.build_score import calculate_build
            bt = calculate_build(player).identify()
            # Map BuildType number → name (1=BERSERKER, 7=ICE_MAGE, etc.)
            bnames = {0:"NONE",1:"BERSERKER",2:"FIRE_MAGE",3:"POISON_MASTER",
                      4:"TIME_MASTER",5:"SUPPORT",6:"PROJECTILE",7:"ICE_MAGE",
                      8:"LIGHTNING_MAGE",9:"BLEED_BLADE",10:"SHADOW_STRIKER",
                      11:"JUGGERNAUT",12:"SUMMON_LORD"}
            name = bnames.get(bt.value, "NONE")
            profile = _BUILD_PROFILES.get(name, {})
            self._prefer_range = profile.get("range", 0.3)
            self._prefer_aoe = profile.get("aoe", 0.2)
            self._prefer_skill = profile.get("skill", 0.4)
            self._aggro_bias = profile.get("aggro", 0.5)
        except Exception:
            pass

    def tick(self): self._frame += 1

    def _find_nearest(self, player, monsters):
        best, bd = None, 99999
        px, py = player.entity.rect.centerx, player.entity.rect.centery
        for m in monsters:
            if not m.combat.is_alive: continue
            d = math.hypot(m.entity.rect.centerx-px, m.entity.rect.centery-py)
            if d < bd: bd = d; best = m
        return best, bd

    def _count_in_range(self, player, monsters, range_px):
        n = 0; px, py = player.entity.rect.centerx, player.entity.rect.centery
        for m in monsters:
            if not m.combat.is_alive: continue
            d = math.hypot(m.entity.rect.centerx-px, m.entity.rect.centery-py)
            if d < range_px: n += 1
        return n

    def _hp_ratio(self, player):
        return player.combat.current_hp / max(1, player.combat.max_hp)

    def accept_event(self, risk_pct, effect_desc, player):
        if not player: return False
        hp = self._hp_ratio(player)
        if risk_pct > 0.40 and hp < 0.50: return False
        if risk_pct > 0.25 and hp < 0.30: return False
        if risk_pct > 0.10 and hp < 0.15: return False
        high_value = any(k in effect_desc for k in ("relic", "skill", "legendary"))
        if high_value and hp > 0.60: return True
        if risk_pct == 0: return True
        return hp > risk_pct * 2.0 + 0.25

    def is_action_just_pressed(self, name, player, monsters, game_map=None, stairs_active=False, boss_intro=False):
        if not player: return False
        if boss_intro and name == "confirm": return self._frame % 60 == 0
        if stairs_active and name == "descend": return self._frame % 30 == 0

        # G7.4: Heal decision (HP < threshold → prioritize heal)
        for si in range(4):
            if name == f"skill_{si+1}":
                has_enemy = self._find_nearest(player, monsters)[0] is not None
                if has_enemy and self._hp_ratio(player) < self._prefer_heal:
                    return self._frame % 30 == 0

        t, d = self._find_nearest(player, monsters)

        # Attack
        if name == "attack" and t and d < 2.0 * 32:
            score = (1.0 - self._prefer_range) * (1.0 - d / (3.0 * 32))
            return score > 0.2 and self._frame % max(5, int(20 * (1.0 - self._aggro_bias))) == 0

        # Skills (AoE builds prefer multi-target)
        if name in ("skill_1","skill_2","skill_3","skill_4") and t:
            n = self._count_in_range(player, monsters, 5.0 * 32)
            aoe_bonus = self._prefer_aoe * (1.0 if n > 1 else 0.3)
            sk_score = self._prefer_skill * (0.3 + aoe_bonus)
            if sk_score > 0.3:
                return self._frame % max(15, int(90 * (1.0 - self._prefer_skill))) == 0

        # Movement
        self._dir_timer -= 0.016
        if self._dir_timer <= 0 or self._current_dir < 0:
            if t:
                # Melee: move toward, Ranged: move away
                dx = t.entity.rect.centerx - player.entity.rect.centerx
                dy = t.entity.rect.centery - player.entity.rect.centery
                if self._prefer_range > 0.6:
                    dx, dy = -dx, -dy
                self._current_dir = 3 if dx > abs(dy) else 2 if dx < -abs(dy) else 1 if dy > 0 else 0
            else:
                self._current_dir = random.randint(0, 3)
            self._dir_timer = 0.3 + random.random() * 0.5
        dirs = {0:"move_up",1:"move_down",2:"move_left",3:"move_right"}
        if name == dirs.get(self._current_dir, ""): return self._frame % 2 == 0

        # Pickup
        if name == "pickup" and game_map:
            for sr in getattr(game_map, "special_rooms", []):
                dx = player.entity.rect.centerx - (sr.cx * 32 + 16)
                dy = player.entity.rect.centery - (sr.cy * 32 + 16)
                if math.hypot(dx, dy) < 3.0 * 32: return self._frame % 15 == 0
        return False


# backward compat
SimAI = DecisionAgent


class SimRunner:
    _instance = None

    def __new__(cls):
        if cls._instance is None: cls._instance = super().__new__(cls); cls._instance._init()
        return cls._instance

    def _init(self):
        self._active = False; self._current_run = 0; self._total_runs = 0
        self._report = BalanceReport()

    def begin(self, total_runs: int):
        self._active = True; self._current_run = 0; self._total_runs = total_runs
        self._report = BalanceReport(); self._report.runs = []
        print(f"[SIM] Starting {total_runs} runs")

    def record_run(self, stats: RunStats):
        r = self._report; r.runs.append(stats); r.total_runs += 1
        r.avg_floor = (r.avg_floor * (r.total_runs-1) + stats.floor_reached) // r.total_runs
        if stats.bosses_killed >= 1: r.boss_kill_rate[0] += 1
        if stats.bosses_killed >= 2: r.boss_kill_rate[1] += 1
        if stats.bosses_killed >= 3: r.boss_kill_rate[2] += 1
        bt = stats.build_type
        if 0 <= bt < 13: r.build_distribution[bt] += 1
        f = stats.floor_reached
        if 1 <= f <= 15: r.death_floor_distribution[f-1] += 1
        self._current_run += 1
        if self._current_run % 10 == 0: print(f"[SIM] {self._current_run}/{self._total_runs}")

    @property
    def should_restart(self) -> bool: return self._active and self._current_run < self._total_runs

    @property
    def is_active(self) -> bool: return self._active

    @property
    def current_run(self) -> int: return self._current_run

    def total_runs(self) -> int: return self._total_runs

    def finalize(self) -> BalanceReport:
        self._active = False
        print(self._report.summary())
        return self._report

    @staticmethod
    def inst() -> 'SimRunner': return SimRunner()
