"""
G6 sync: SimAI + SimRunner — automated balance simulation (C++ parity)
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


class SimAI:
    """Simple AI that drives the player in sim mode."""
    def __init__(self):
        self._frame = 0; self._dir_timer = 0; self._current_dir = -1

    def start(self): self._frame = 0; self._dir_timer = 0; self._current_dir = -1
    def tick(self): self._frame += 1

    def _find_nearest(self, player, monsters):
        best, bd = None, 99999
        px, py = player.entity.rect.centerx, player.entity.rect.centery
        for m in monsters:
            if not m.combat.is_alive: continue
            d = math.hypot(m.entity.rect.centerx-px, m.entity.rect.centery-py)
            if d < bd: bd = d; best = m
        return best

    def _pick_direction(self, player, monsters):
        t = self._find_nearest(player, monsters)
        if t:
            dx = t.entity.rect.centerx - player.entity.rect.centerx
            dy = t.entity.rect.centery - player.entity.rect.centery
            self._current_dir = 3 if dx > abs(dy) else 2 if dx < -abs(dy) else 1 if dy > 0 else 0
        else:
            self._current_dir = random.randint(0, 3)

    def is_action_just_pressed(self, name, player, monsters, game_map=None, stairs_active=False, boss_intro=False):
        if not player: return False
        if boss_intro and name == "confirm": return self._frame % 60 == 0
        if stairs_active and name == "descend": return self._frame % 30 == 0
        self._dir_timer -= 0.016
        if self._dir_timer <= 0 or self._current_dir < 0:
            self._pick_direction(player, monsters)
            self._dir_timer = 0.3 + random.random() * 0.5
        dirs = {0:"move_up",1:"move_down",2:"move_left",3:"move_right"}
        if name == dirs.get(self._current_dir, ""): return self._frame % 2 == 0
        if name == "attack":
            t = self._find_nearest(player, monsters)
            if t:
                d = math.hypot(t.entity.rect.centerx-player.entity.rect.centerx, t.entity.rect.centery-player.entity.rect.centery)
                if d < 2.0 * 32: return self._frame % 12 == 0
        if name in ("skill_1","skill_2","skill_3","skill_4"):
            t = self._find_nearest(player, monsters)
            if t: return self._frame % 90 == random.randint(0, 3) * 20
        if name == "pickup" and game_map:
            for sr in getattr(game_map, "special_rooms", []):
                dx = player.entity.rect.centerx - (sr.cx * 32 + 16)
                dy = player.entity.rect.centery - (sr.cy * 32 + 16)
                if math.hypot(dx, dy) < 3.0 * 32: return self._frame % 15 == 0
        return False


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
