"""
RelicArchive — 圣物图鉴跨局收集 (M18 Python port)

职责:
  - 追踪本会话中已解锁的圣物 (per-session persistence)
  - 熟练度: 每获得一次 +50, 满 500 即 5 星
  - 最高稀有度记录
  - 收集率统计

用法:
  from src.systems.relic_archive import g_relic_archive
  g_relic_archive.mark_obtained("blood_charm", 0)
  stars = g_relic_archive.mastery_level("blood_charm")  # 0-5
"""

from dataclasses import dataclass


@dataclass
class RelicArchiveEntry:
    id: str = ""
    obtained_count: int = 0      # 累计获得次数
    highest_rarity: int = 0      # 0=common, 1=rare, 2=epic
    mastery: int = 0             # 0-500


class RelicArchive:
    """全局圣物图鉴 (单例)。"""

    def __init__(self):
        self._entries: dict[str, RelicArchiveEntry] = {}

    # ---- 公开 API ----

    def mark_obtained(self, relic_id: str, rarity_level: int = 0):
        """每次获得 relic 时调用。"""
        if relic_id not in self._entries:
            e = RelicArchiveEntry(id=relic_id)
            self._entries[relic_id] = e
        e = self._entries[relic_id]
        e.obtained_count += 1
        if rarity_level > e.highest_rarity:
            e.highest_rarity = rarity_level
        e.mastery = min(500, e.mastery + 50)

    def mastery_level(self, relic_id: str) -> int:
        """返回 0-5 星标。0=未解锁, 5=满熟练。"""
        e = self._entries.get(relic_id)
        if not e:
            return 0
        return min(5, e.mastery // 100)

    def collected_count(self) -> int:
        """已永久解锁的 relic 数量。"""
        return len(self._entries)

    def total_relic_count(self) -> int:
        """全局 relic 种类总数。"""
        from src.systems.relic_system import get_all_relic_ids
        return len(get_all_relic_ids())

    def collection_pct(self) -> float:
        """收集百分比 (0.0 ~ 1.0)。"""
        total = self.total_relic_count()
        if total == 0:
            return 0.0
        return self.collected_count() / total

    def entry(self, relic_id: str) -> RelicArchiveEntry | None:
        return self._entries.get(relic_id)


# 全局单实例
g_relic_archive = RelicArchive()
