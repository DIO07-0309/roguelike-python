"""
G6.7: ConditionEvaluator — unified string DSL for encounter conditions.

DSL format:
  "flag:X"      → flag X is set (RunFlag or MetaFlag)
  "!flag:X"     → flag X is NOT set
  "floor>=N"    → current floor >= N
  "floor<=N"    → current floor <= N
  "biome:Y"     → current biome == Y
  "!biome:Y"    → current biome != Y

All conditions in the list must pass (AND logic). Empty list = always true.
"""

from dataclasses import dataclass, field


@dataclass
class EvalContext:
    """G6.7: evaluation context for condition checking."""
    run_flags: set = field(default_factory=set)
    meta_flags: set = field(default_factory=set)
    floor: int = 1
    biome_id: str = ""


def evaluate_conditions(conditions: list[str], ctx: EvalContext) -> bool:
    """ALL conditions must pass (AND logic). Empty list = always true."""
    if not conditions:
        return True
    for cond in conditions:
        if not _eval_one(cond, ctx):
            return False
    return True


def _eval_one(cond: str, ctx: EvalContext) -> bool:
    if cond.startswith("!flag:"):
        fid = int(cond[6:])
        return fid not in ctx.run_flags and fid not in ctx.meta_flags
    if cond.startswith("flag:"):
        fid = int(cond[5:])
        return fid in ctx.run_flags or fid in ctx.meta_flags
    if cond.startswith("floor>="):
        return ctx.floor >= int(cond[7:])
    if cond.startswith("floor<="):
        return ctx.floor <= int(cond[7:])
    if cond.startswith("!biome:"):
        return ctx.biome_id != cond[7:]
    if cond.startswith("biome:"):
        return ctx.biome_id == cond[6:]
    return True  # unknown = pass
