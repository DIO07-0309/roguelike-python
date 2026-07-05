"""
──────────────────────────────────────────
《Roguelike 肉鸽游戏》— 全局配置文件
──────────────────────────────────────────

说明：
  - 所有游戏常量集中管理，不散落在各模块里。
  - 模块通过 `from config import <NAME>` 引用。
"""

# ===============================================
# 窗口
# ===============================================
WINDOW_TITLE = "Roguelike — 重庆大学大数据与软件学院"
WINDOW_WIDTH = 960
WINDOW_HEIGHT = 640
FPS = 60
FULLSCREEN = False              # 是否以全屏模式启动

# ===============================================
# 字体
# ===============================================
# 字体 — 自动检测 Windows 中文字体，找不到则用默认
def _detect_cjk_font() -> str:
    candidates = [
        "C:/Windows/Fonts/msyh.ttc",     # 微软雅黑
        "C:/Windows/Fonts/msyhbd.ttc",   # 微软雅黑粗体
        "C:/Windows/Fonts/simhei.ttf",   # 黑体
        "C:/Windows/Fonts/simsun.ttc",   # 宋体
        "C:/Windows/Fonts/simkai.ttf",   # 楷体
    ]
    import os
    for path in candidates:
        if os.path.exists(path):
            return path
    return None                          # 无中文字体→pygame默认字体

CJK_FONT_PATH = _detect_cjk_font()       # 微软雅黑（支持中文）

# ===============================================
# 地图
# ===============================================
TILE_SIZE = 32                          # 每个瓷砖的像素尺寸
MAP_WIDTH = 40                          # 地图最大宽度（单位：瓷砖）
MAP_HEIGHT = 30                         # 地图最大高度（单位：瓷砖）

# BSP 地牢生成器参数
DUNGEON_MIN_PARTITION = 8              # 分区递归停止的最小尺寸（瓦片）
DUNGEON_MIN_ROOM = 5                   # 房间最小宽/高（瓦片）
DUNGEON_ROOM_MARGIN = 1               # 房间与分区边界的间距（瓦片）
DUNGEON_CORRIDOR_MIN = 1              # 走廊最小半宽
DUNGEON_CORRIDOR_MAX = 2              # 走廊最大半宽

# ===============================================
# 关卡系统
# ===============================================
MAX_FLOORS = 15                                 # 总关卡数
BOSS_FLOORS = [5, 10, 15]                       # Boss 关
XP_PER_KILL_BASE = 10                           # 击杀基础经验
XP_PER_KILL_BOSS = 150                          # Boss 击杀经验

# 怪物属性倍率 (每层递增，Boss关不缩放)
FLOOR_MONSTER_HP_MULT = [
    1.0, 1.15, 1.3, 1.5, 1.0,   # 1-5  (5=暗影骑士)
    1.6, 1.8, 2.0, 2.2, 1.0,   # 6-10 (10=地狱火魔)
    2.4, 2.7, 3.0, 3.3, 1.0    # 11-15 (15=深渊之主)
]
FLOOR_MONSTER_ATK_MULT = [
    1.0, 1.12, 1.25, 1.4, 1.0,
    1.5, 1.65, 1.8, 2.0, 1.0,
    2.2, 2.4, 2.6, 2.9, 1.0
]
FLOOR_MONSTER_COUNT = [
    5, 5, 6, 6, 1,              # 1-5
    6, 6, 7, 7, 1,              # 6-10
    7, 7, 8, 8, 1               # 11-15
]

# ===============================================
# 玩家 / 背包
# ===============================================
PLAYER_SPEED = 200                      # 移动速度（像素/秒）
PLAYER_MAX_HP = 100                     # 最大生命值
PLAYER_ATTACK = 10                      # 基础攻击力
PLAYER_PHYSICAL_DEFENSE = 3             # 基础物理防御
PLAYER_MAGICAL_DEFENSE = 1              # 基础魔法防御
PLAYER_ATTACK_RANGE = 1.5               # 攻击范围（瓦片数）
INVENTORY_MAX_SIZE = 16                 # 背包最大容量
LOOT_DROP_CHANCE = 0.5                  # 怪物死亡掉落概率
PICKUP_RANGE = 2.0                      # 拾取距离（瓦片数）

# ===============================================
# 怪物 AI
# ===============================================
MONSTER_SIGHT_RANGE = 6                 # 发现玩家的视野距离（瓦片数）
MONSTER_MOVE_SPEED = 80                 # 移动速度（像素/秒）
MONSTER_PATROL_INTERVAL = 2.0           # 巡逻方向切换间隔（秒）

# ===============================================
# 颜色（RGB 元组）
# ===============================================
COLOR_BLACK = (0, 0, 0)
COLOR_WHITE = (255, 255, 255)
COLOR_GRAY = (128, 128, 128)
COLOR_DARK_GRAY = (64, 64, 64)
COLOR_RED = (200, 50, 50)
COLOR_GREEN = (50, 200, 50)
COLOR_BLUE = (50, 50, 200)
COLOR_YELLOW = (200, 200, 50)
