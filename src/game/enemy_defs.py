"""
G5 sync: EnemyDef data-driven enemy loader (C++ parity)
"""
import json
import os
import sys
from dataclasses import dataclass, field


def _resolve_path(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


@dataclass
class EnemyAIDef:
    sight: float = 6.0
    speed: float = 80.0
    patrol: float = 2.0
    attack_range: float = 1.5


@dataclass
class EnemySkillDef:
    id: str = ""
    max_cooldown: float = 5.0
    initial_cooldown: float = 0.0


@dataclass
class EnemyDef:
    id: str = ""
    name: str = ""
    visual_id: str = "slime"
    hp: int = 15; atk: int = 3; pdef: int = 0; mdef: int = 1
    type_str: str = "normal"
    role_str: str = "none"
    attack_type_str: str = "physical"
    attack_cooldown: float = 1.5
    ai_archetype: str = "default"
    ai: EnemyAIDef = field(default_factory=EnemyAIDef)
    skills: list = field(default_factory=list)
    on_hit: list = field(default_factory=list)
    is_elite: bool = False
    elite_buffs: list = field(default_factory=list)


_g_enemy_defs: dict[str, EnemyDef] = {}


def load_enemy_defs(json_path: str = "resources/enemies.json") -> bool:
    global _g_enemy_defs
    try:
        path = _resolve_path(json_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            eid = item.get("id", "")
            if not eid: continue
            ai_data = item.get("ai", {})
            skills = []
            for sk in item.get("skills", []):
                skills.append(EnemySkillDef(
                    id=sk.get("id", ""),
                    max_cooldown=sk.get("max_cooldown", 5.0),
                    initial_cooldown=sk.get("initial_cooldown", 0.0),
                ))
            on_hit = []
            for oh in item.get("on_hit", []):
                on_hit.append(dict(buff=oh.get("buff",""), stacks=oh.get("stacks",1), chance=oh.get("chance",1.0)))
            elite_buffs = [dict(buff=e.get("buff",""), stacks=e.get("stacks",1)) for e in item.get("elite_buffs",[])]
            _g_enemy_defs[eid] = EnemyDef(
                id=eid, name=item.get("name",""), visual_id=item.get("visual_id","slime"),
                hp=item.get("hp",15), atk=item.get("atk",3), pdef=item.get("pdef",0), mdef=item.get("mdef",1),
                type_str=item.get("type","normal"), role_str=item.get("role","none"),
                attack_type_str=item.get("attack_type","physical"),
                attack_cooldown=item.get("attack_cooldown",1.5),
                ai_archetype=item.get("ai_archetype","default"),
                ai=EnemyAIDef(**ai_data) if isinstance(ai_data, dict) else EnemyAIDef(),
                skills=skills, on_hit=on_hit,
                is_elite=item.get("is_elite",False), elite_buffs=elite_buffs,
            )
        print(f"[EnemyDef] Loaded {len(data)} enemies from json")
        return True
    except Exception as e:
        print(f"[EnemyDef] Failed: {e}")
        return False


def get_enemy_def(eid: str) -> EnemyDef | None:
    return _g_enemy_defs.get(eid)


def get_all_enemy_defs() -> dict:
    return _g_enemy_defs
