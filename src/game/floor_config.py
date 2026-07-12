"""
D1: FloorConfig / ChapterConfig / FloorNarrative — 统一楼层配置

职责:
  - 替代 config.py 中硬编码的 FLOOR_MONSTER_HP_MULT/ATK_MULT/COUNT 数组
  - 楼层叙事数据: 标题/副标题/环境描写/随机旁白
  - 章节定义: 地牢入口/幽暗深渊/熔岩炼狱

数据与 C++ floor_config.cpp + floor_narrative.cpp 完全一致。
"""

from dataclasses import dataclass, field


# ═══════════════════════════════════════════════════════════════
#  FloorConfig — 单层难度/敌人/特殊房间/BGM 配置
# ═══════════════════════════════════════════════════════════════

@dataclass
class FloorConfig:
    floor: int                    # 1-15
    chapter: int                  # 0=地牢入口, 1=幽暗深渊, 2=熔岩炼狱
    chapter_label: str            # "地牢入口" / "幽暗深渊" / "熔岩炼狱"
    story_msg: str | None         # 首次进入剧情文字 (None=无)
    hp_mult: float                # 怪物 HP 倍率
    atk_mult: float               # 怪物 ATK 倍率
    monster_count: int            # 基础怪物数量
    special_room_count: int       # 特殊房间数量
    is_boss: bool                 # Boss 层
    is_rest_floor: bool           # 休息层
    bgm: str                      # "dungeon" | "boss"


# ═══════════════════════════════════════════════════════════════
#  ChapterConfig — 章节定义
# ═══════════════════════════════════════════════════════════════

@dataclass
class ChapterConfig:
    chapter: int
    name: str                     # "地牢入口"
    start_floor: int
    end_floor: int


# ═══════════════════════════════════════════════════════════════
#  FloorNarrative — 楼层叙事 (D4 Step3)
# ═══════════════════════════════════════════════════════════════

@dataclass
class FloorNarrative:
    floor: int
    title: str                    # 楼层名称 e.g. "沉睡牢狱"
    subtitle: str                 # 英文副标题
    description: str | None       # 1-2句环境描写
    enter_dialogue: str | None    # 首次进入独白
    exit_dialogue: str | None     # 离开楼层独白
    boss_hint: str | None         # Boss前3层伏笔
    narrations: list[str | None]  # 3-5条环境旁白
    ambience: str                 # 环境音效 hook (D5接入)
    ambient_color: tuple          # (r, g, b) 环境色调


# ═══════════════════════════════════════════════════════════════
#  NarrativeState — 旁白状态
# ═══════════════════════════════════════════════════════════════

@dataclass
class NarrativeState:
    floor_intro_played: list[bool] = field(default_factory=lambda: [False] * 15)
    last_narration_idx: int = -1
    narration_timer: float = 0.0


# ═══════════════════════════════════════════════════════════════
#  15 层配置表 (与 C++ floor_config.cpp FLOORS[] 一致)
# ═══════════════════════════════════════════════════════════════

_FLOORS: list[FloorConfig] = [
    # 第一章: 地牢入口 (F1-5)
    FloorConfig( 1, 0, "地牢入口", "你推开沉重的铁门，空气弥漫着腐败的气息。",
                 1.00, 1.00, 5, 2, False, False, "dungeon"),
    FloorConfig( 2, 0, "地牢入口", "昏暗的走廊深处传来低沉的嘶吼。",
                 1.15, 1.12, 5, 2, False, False, "dungeon"),
    FloorConfig( 3, 0, "地牢入口", "墙上的火把已燃尽了千年，你只能依靠直觉。",
                 1.30, 1.25, 6, 2, False, False, "dungeon"),
    FloorConfig( 4, 0, "地牢入口", "前方出现温暖的火光——一个安全的喘息之地。",
                 1.50, 1.40, 5, 3, False, True,  "dungeon"),
    FloorConfig( 5, 0, "地牢入口", None,
                 1.00, 1.00, 1, 0, True,  False, "boss"),
    # 第二章: 幽暗深渊 (F6-10)
    FloorConfig( 6, 1, "幽暗深渊", "你顺着裂缝下坠，落入了地牢更深的黑暗中。",
                 1.60, 1.50, 6, 2, False, False, "dungeon"),
    FloorConfig( 7, 1, "幽暗深渊", "黑暗中传来施法的吟唱声——这里有萨满。",
                 1.80, 1.65, 6, 2, False, False, "dungeon"),
    FloorConfig( 8, 1, "幽暗深渊", "洞穴越来越窄，每一步都需要格外小心。",
                 2.00, 1.80, 7, 2, False, False, "dungeon"),
    FloorConfig( 9, 1, "幽暗深渊", "荧光苔藓照亮了开阔的洞窟——你可以休整。",
                 2.20, 2.00, 6, 3, False, True,  "dungeon"),
    FloorConfig(10, 1, "幽暗深渊", None,
                 1.00, 1.00, 1, 0, True,  False, "boss"),
    # 第三章: 熔岩炼狱 (F11-15)
    FloorConfig(11, 2, "熔岩炼狱", "灼热的气流迎面扑来，这是地牢最深处。",
                 2.40, 2.20, 7, 3, False, False, "dungeon"),
    FloorConfig(12, 2, "熔岩炼狱", "空气中弥漫着硫磺的味道，前方的敌人更加危险。",
                 2.70, 2.40, 7, 3, False, False, "dungeon"),
    FloorConfig(13, 2, "熔岩炼狱", "你听到无数怪物的嘶吼从四面八方涌来。",
                 3.00, 2.60, 8, 3, False, False, "dungeon"),
    FloorConfig(14, 2, "熔岩炼狱", "一座宏伟的遗迹出现——远古文明的最后痕迹。",
                 3.30, 2.90, 7, 3, False, True,  "dungeon"),
    FloorConfig(15, 2, "熔岩炼狱", None,
                 1.00, 1.00, 1, 0, True,  False, "boss"),
]

_CHAPTERS: list[ChapterConfig] = [
    ChapterConfig(0, "地牢入口", 1, 5),
    ChapterConfig(1, "幽暗深渊", 6, 10),
    ChapterConfig(2, "熔岩炼狱", 11, 15),
]


# ═══════════════════════════════════════════════════════════════
#  15 层叙事表 (与 C++ floor_narrative.cpp NARRATIVES[] 一致)
# ═══════════════════════════════════════════════════════════════

_NARRATIVES: list[FloorNarrative] = [
    # ── 第一章: 沉睡牢狱 (F1-5) ──
    FloorNarrative(1, "沉睡牢狱", "The Sleeping Prison",
        "古老的地牢在黑暗中沉睡了千年，\n如今，它醒了。",
        "你睁开眼睛。头顶是冰冷的石壁，身下是发霉的稻草。\n你已经记不清自己在这里被关了多久。",
        "你推开铁门，身后传来沉闷的回声。",
        None,
        ["墙上的火把燃尽了最后一个世纪的记忆。",
         "水滴从天花板滴落——这是唯一的时钟。",
         "牢房的铁栏杆早已锈蚀，但门锁仍然紧紧扣着。",
         "潮湿的空气中弥漫着绝望的气味。", None],
        "drip", (70, 85, 110)),

    FloorNarrative(2, "破碎回廊", "The Broken Corridor",
        "长廊的柱子上刻满了囚徒的名字，\n有些已经被岁月磨平。",
        "回廊一直向前延伸，看不到尽头。\n两侧的牢房里偶尔传来低语。",
        None, None,
        ["柱子上刻着模糊的文字——也许是一个人的遗言。",
         "地面上散落着碎裂的骨头，踩上去发出清脆的声响。",
         "墙壁的缝隙里透出微弱的绿光。",
         "你听到有人在呼唤——也许是风，也许不是。", None],
        "wind", (60, 75, 100)),

    FloorNarrative(3, "囚徒食堂", "The Prisoners' Hall",
        "巨大的石桌上摆放着早已朽烂的木碗，\n这个房间曾经属于一群人。",
        None, None, None,
        ["石桌的边缘有一个小小的刻痕——也许是谁在记着日子。",
         "角落里散落着铁链，上面沾着暗红色的印记。",
         "炊火的残骸冰冷了不知多少年。",
         "空气中似乎还残留着腐烂食物的气味。",
         "一只老鼠匆匆穿过房间，它的眼睛里反射着火光。"],
        "chains", (55, 70, 95)),

    FloorNarrative(4, "泪水之井", "The Well of Tears",
        "一口深井坐落在房间中央，\n空气中弥漫着锈铁的味道。",
        "井口边的石板上刻着古老的符文——\n'这里囚禁着比死亡更可怕的东西。'",
        None,
        "狱卒在等你。\n他已经等你很久了。",
        ["井底传来微弱的哭声。",
         "石板上不仅有符文，还有深深的爪痕。",
         "一滴水从井边滑落——它向上飞起来了。",
         "你能听到井底有人在倒数。", None],
        "water", (65, 80, 105)),

    FloorNarrative(5, "狱卒大厅", "The Warden's Throne",
        "这曾是监狱的心脏。\n黑暗在这里最为浓烈。",
        None,
        "你击败了守护者。\n黑暗的帷幕裂开了一道缝隙。",
        None,
        ["你会记住这一刻的——即使黑暗试图让你忘记。", None],
        "silence", (40, 30, 70)),

    # ── 第二章: 腐化神殿 (F6-10) ──
    FloorNarrative(6, "苔藓洞穴", "The Moss Caves",
        "你顺着裂缝下坠，落入了一片幽绿的洞窟。\n荧光苔藓是这里唯一的光源。",
        "这里比上面更深，也更安静。\n安静得让人不安。",
        None,
        "有什么东西在你身后。\n不，是有什么东西在你身体里。",
        ["苔藓——它们似乎在随着你的呼吸闪烁。",
         "洞穴深处传来某种古老的吟唱。",
         "你发现地上有一串脚印——它们消失在了岩壁里。", None],
        "whisper", (60, 100, 70)),

    FloorNarrative(7, "腐化神殿", "The Corrupted Temple",
        "一座古老的神殿矗立在黑暗之中。\n它的柱子雕刻着已被遗忘的神明。",
        "神殿的大门敞开着。\n它在邀请——它在等待。",
        None,
        "神像的眼睛在流血。\n它已经看了你很久。",
        ["神坛上放着一本打开的经书，书页漆黑如墨。",
         "墙上的壁画描绘着一场远古的献祭。",
         "空气中充满了灰色烟雾，它们在跳动——像心跳。",
         "你在神殿的深处感到一阵眩晕。", None],
        "chant", (80, 65, 115)),

    FloorNarrative(8, "哭泣深渊", "The Weeping Chasm",
        "深渊中悬挂着无数铁链，\n每根铁链下都坠着一个生锈的囚笼。",
        None, None,
        "深渊并不是空的。\n它一直在注视你。",
        ["铁链在风中摇摆，发出刺耳的摩擦声。",
         "远处传来一阵撕裂的声音——也许是铁门，也许不是。",
         "深渊里有什么在发光。它越来越近了。", None],
        "chains", (70, 55, 100)),

    FloorNarrative(9, "朝圣者之路", "The Pilgrim's Path",
        "石壁上刻着数以千计的足迹，\n它们指向同一个方向——更深处。",
        "这条路太安静了。\n就连风也停住了。",
        None,
        "朝圣者的尽头不是神明——\n是深渊。",
        ["墙壁上刻满了祈祷文，但都被划掉了。",
         "这里的地面是温热的，像是有生命。",
         "你在一段文字的边缘看到了自己的名字。",
         "前方的通道变窄了——它一直在等你。", None],
        "footsteps", (65, 80, 100)),

    FloorNarrative(10, "熔岩王座", "The Lava Throne",
        "熔岩在裂缝中翻滚，\n红光把黑暗烧成了灰烬。",
        None,
        "火焰熄灭了。\n但真正的黑暗才刚刚开始。",
        None,
        ["这里的温度让你的眼睛开始刺痛。",
         "熔岩的表面不时浮出一张张扭曲的脸。",
         "空气中回荡着嘶哑的怒吼。", None],
        "lava", (120, 30, 25)),

    # ── 第三章: 深渊裂谷 (F11-15) ──
    FloorNarrative(11, "灰烬废墟", "The Ash Ruins",
        "这里曾是朝圣者的终站——\n如今只剩下焦黑的骨架。",
        "空气中弥漫着硫磺的味道。\n你不敢呼吸太重。",
        None,
        "你走在别人的尸骨上。\n也走在别人的脚下。",
        ["重建这座城市大概需要一千年。\n建造它只用了七天。",
         "灰烬中有一面镜子——它映出了一个你不认识的人。",
         "远处传来爆炸的回声——也许是火山，也许不是。", None],
        "rumble", (100, 40, 30)),

    FloorNarrative(12, "焦土裂谷", "The Scorched Rift",
        "大地上裂开了一道巨大的伤口，\n裂缝中流出暗红色的光。",
        None, None,
        "深渊在呼唤你。\n你也在呼唤深渊。",
        ["裂缝旁的石头上刻着整齐的符号——不像人类的手笔。",
         "热度让空气扭曲成了奇怪的形状。",
         "裂缝深处传来某种语言——不属于这个世界。",
         "地面开始在你脚下移动。", None],
        "rumble", (110, 35, 25)),

    FloorNarrative(13, "愚者朝圣", "The Pilgrimage of Fools",
        "千百具骸骨面朝深处匍匐在地，\n他们用死亡完成了朝圣。",
        "尸骨之间散落着黄金和圣物。\n他们直到最后也没有放弃信仰。",
        None,
        "最后一个朝圣者就是你。",
        ["这些尸骨的温度仍然温存。",
         "虔诚……某种意义上，也是另一种形式的疯狂。",
         "有一个小骷髅手里还握着一枚金币。",
         "你还记得自己为什么要来这里吗？", None],
        "silence", (90, 35, 30)),

    FloorNarrative(14, "起源之门", "The Gate of Origin",
        "一座宏伟的石门伫立在你面前——\n门上刻着一个被遗忘的创世神话。",
        "浮雕上描绘着光与暗的第一次分离。\n在光的那一边，是你——在暗的这一边，是它。",
        None,
        "推开这扇门后——\n你将不再是原来的你。",
        ["石门上刻着的文字在闪烁——它们在移动。",
         "门的中央有一道裂缝，从里面泻出黑光。",
         "你能感觉到门后有东西在注视你。",
         "门上刻着一双眼睛——它眨了。", None],
        "silence", (80, 30, 35)),

    FloorNarrative(15, "深渊王座", "The Throne of the Abyss",
        "这是地牢的终点。\n黑暗在这里凝聚成了实体。",
        None, None, None,
        ["当这个世界醒来的时候——它还会记得你吗？", None],
        "silence", (60, 15, 20)),
]


# ═══════════════════════════════════════════════════════════════
#  查询接口
# ═══════════════════════════════════════════════════════════════

def get_floor_config(floor: int) -> FloorConfig:
    """返回 1-based 楼层配置。"""
    if floor < 1 or floor > 15:
        return _FLOORS[0]
    return _FLOORS[floor - 1]


def get_chapter_config(chapter: int) -> ChapterConfig:
    """返回 0-based 章节配置。"""
    if chapter < 0 or chapter >= len(_CHAPTERS):
        return _CHAPTERS[0]
    return _CHAPTERS[chapter]


def get_chapter_for_floor(floor: int) -> int:
    return get_floor_config(floor).chapter


def get_floor_narrative(floor: int) -> FloorNarrative | None:
    """返回 1-based 楼层叙事。"""
    if floor < 1 or floor > 15:
        return _NARRATIVES[0]
    return _NARRATIVES[floor - 1]


def get_chapter_title(chapter: int) -> str:
    titles = {0: "第一章: 地牢入口", 1: "第二章: 幽暗深渊", 2: "第三章: 熔岩炼狱"}
    return titles.get(chapter, "???")


def get_chapter_subtitle(chapter: int) -> str:
    subtitles = {0: "Chapter I: The Dungeon Gate",
                 1: "Chapter II: The Dark Abyss",
                 2: "Chapter III: The Lava Inferno"}
    return subtitles.get(chapter, "???")


def pick_random_narration(floor: int, state: NarrativeState) -> str | None:
    """从楼层旁白池中随机选取一条。避免与上次重复。"""
    import random
    fn = get_floor_narrative(floor)
    if not fn:
        return None
    pool = [n for n in fn.narrations if n is not None]
    if not pool:
        return None
    idx = random.randint(0, len(pool) - 1)
    if len(pool) >= 2 and idx == state.last_narration_idx:
        idx = (idx + 1) % len(pool)
    state.last_narration_idx = idx
    return pool[idx]
