"""G8.2: A* grid pathfinder — Python port from C++ roguelike_cpp."""
from __future__ import annotations
import heapq
from dataclasses import dataclass
from typing import Callable

WalkableFn = Callable[[int, int], bool]


@dataclass
class PathResult:
    path: list[tuple[int, int]]
    nodes_visited: int = 0
    reachable: bool = False


def find_path(start: tuple[int, int], goal: tuple[int, int],
              is_walkable: WalkableFn, map_w: int, map_h: int,
              max_steps: int = 400) -> PathResult:
    """A* search on a grid. Returns shortest path or empty if unreachable."""
    sx, sy = start
    gx, gy = goal
    result = PathResult([], 0, False)

    size = map_w * map_h
    g_cost = [float('inf')] * size
    parent = [-1] * size
    closed = [False] * size

    def pack(x: int, y: int) -> int:
        return x * map_h + y

    def unpack(idx: int) -> tuple[int, int]:
        return idx // map_h, idx % map_h

    def heuristic(ax: int, ay: int, bx: int, by: int) -> float:
        return abs(ax - bx) + abs(ay - by)

    DX = [1, -1, 0, 0]
    DY = [0, 0, 1, -1]

    si = pack(sx, sy)
    gi = pack(gx, gy)
    g_cost[si] = 0
    open_set = [(heuristic(sx, sy, gx, gy), si)]

    while open_set and result.nodes_visited < max_steps:
        _, ci = heapq.heappop(open_set)
        if closed[ci]:
            continue
        closed[ci] = True
        result.nodes_visited += 1

        if ci == gi:
            result.reachable = True
            p = ci
            while p != -1:
                result.path.append(unpack(p))
                p = parent[p]
            result.path.reverse()
            return result

        cx, cy = unpack(ci)
        for d in range(4):
            nx, ny = cx + DX[d], cy + DY[d]
            if nx < 0 or nx >= map_w or ny < 0 or ny >= map_h:
                continue
            ni = pack(nx, ny)
            if closed[ni] or not is_walkable(nx, ny):
                continue
            ng = g_cost[ci] + 1.0
            if ng < g_cost[ni]:
                g_cost[ni] = ng
                parent[ni] = ci
                f = ng + heuristic(nx, ny, gx, gy)
                heapq.heappush(open_set, (f, ni))

    return result
