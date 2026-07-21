"""
G5 sync: SkillDef data-driven skill loader (C++ parity)
"""
import json, os, sys
from dataclasses import dataclass, field


def _resolve_path(path: str) -> str:
    if os.path.exists(path): return path
    base = getattr(sys, "_MEIPASS", os.getcwd())
    alt = os.path.join(base, path)
    return alt if os.path.exists(alt) else path


@dataclass
class SkillTriggerDef:
    buff: str = ""; stacks: int = 1; chance: float = 1.0; target: str = "enemy"


@dataclass
class SkillEvoDef:
    level: int = 1; name: str = ""; desc: str = ""
    required_tags: list = field(default_factory=list)


@dataclass
class SkillDef:
    id: str = ""; class_type: str = ""; name: str = ""
    cooldown: float = 2.0; max_level: int = 3
    tags: list = field(default_factory=list)
    triggers: list = field(default_factory=list)
    evolutions: list = field(default_factory=list)
    modifier_key: str = ""; base_value: int = 0
    values_per_level: list = field(default_factory=list)


_g_skill_defs: dict[str, SkillDef] = {}


def load_skill_defs(json_path: str = "resources/skills.json") -> bool:
    global _g_skill_defs
    try:
        path = _resolve_path(json_path)
        with open(path, "r", encoding="utf-8") as f: data = json.load(f)
        for item in data:
            sid = item.get("id","")
            if not sid: continue
            triggers = []
            for tr in item.get("triggers", []):
                triggers.append(SkillTriggerDef(
                    buff=tr.get("buff",""), stacks=tr.get("stacks",1),
                    chance=tr.get("chance",1.0), target=tr.get("target","enemy")))
            evos = []
            for ev in item.get("evolutions", []):
                evos.append(SkillEvoDef(
                    level=ev.get("level",1), name=ev.get("name",""),
                    desc=ev.get("desc",""), required_tags=ev.get("required_tags",[])))
            _g_skill_defs[sid] = SkillDef(
                id=sid, class_type=item.get("class_type",""), name=item.get("name",""),
                cooldown=item.get("cooldown",2.0), max_level=item.get("max_level",3),
                tags=item.get("tags",[]), triggers=triggers, evolutions=evos,
                modifier_key=item.get("modifier_key",""), base_value=item.get("base_value",0),
                values_per_level=item.get("values_per_level",[]),
            )
        print(f"[SkillDef] Loaded {len(data)} skills from json")
        return True
    except Exception as e:
        print(f"[SkillDef] Failed: {e}")
        return False


def get_skill_def(sid: str) -> SkillDef | None:
    return _g_skill_defs.get(sid)


def get_all_skill_defs() -> dict[str, SkillDef]:
    return _g_skill_defs
