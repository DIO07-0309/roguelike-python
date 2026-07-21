# Roguelike — 地牢肉鸽

> 重庆大学大数据与软件学院 ·《程序设计实训》

---

## 一、游戏简介

你是一名冒险者，进入一座由程序随机生成的地牢。每局地图不同，每次死亡都是永久性的。

**目标**：击败最深处的 Boss「深渊领主」。

---

## 二、快速开始

```bash
# 安装依赖（只需一次）
pip install pygame

# 启动游戏
python main.py
```

| 环境 | 说明 |
|------|------|
| Python | 3.11+ |
| 依赖 | pygame ≥ 2.6 |
| 操作系统 | Windows / macOS / Linux |

---

## 三、操作一览

### 移动与交互

| 按键 | 功能 |
|------|------|
| **W A S D** | 上下左右移动 |
| **↑ ↓ ← →** | 切换朝向（不移动） |
| **空格** | 普攻攻击最近的怪物 |
| **E** | 拾取地面物品 / 触发特殊房间 |
| **I** | 打开 / 关闭背包 |
| **R** | 打开 / 关闭圣物面板 |
| **>** | 下楼（需楼梯激活） |

### 技能释放

| 按键 | 功能 |
|------|------|
| **1** | 释放第 1 个主动技能 |
| **2** | 释放第 2 个主动技能 |
| **3** | 释放第 3 个主动技能 |
| **4** | 释放第 4 个主动技能 |

### 系统操作

| 按键 | 功能 |
|------|------|
| **Enter** | 开始新游戏 / 死亡后返回标题 |
| **T** | 进入新手教程 |
| **Esc** | 退出游戏 / 返回标题 |

---

## 四、背包操作

按 **I** 打开背包后：

| 按键 | 功能 |
|------|------|
| **↑ / ↓** | 移动光标选择物品 |
| **X** | 装备选中物品（武器/护甲自动替换旧装备） |
| **U** | 使用选中物品（药水回血） |
| **D** | 丢弃选中物品 |
| **I / Esc** | 关闭背包 |

---

## 五、新手教程

标题画面按 **T** 进入教程，逐步学习所有操作：

| 步骤 | 内容 | 过关条件 |
|------|------|----------|
| 1 | **WASD 移动** | 走 4 格以上 |
| 2 | **空格攻击** | 打木桩 1 次 |
| 3 | **E 拾取** | 捡起地面药水 |
| 4 | **I 背包 + U 使用** | 开背包用掉药水回血 |
| 5 | **X 装备武器** | 在背包内装备短剑 |
| 6 | **1 释放技能** | 使用斩击技能 |

教程中木桩不会攻击你，放心练习！

---

## 六、游戏系统介绍

### 6.1 战斗

- **普攻**：空格键攻击，基础伤害 = ATK − DEF×0.5，有 ±20% 随机浮动
- **冷却**：普攻 0.5 秒冷却，怪物 1.5 秒冷却
- **死亡**：HP 归零 → 死亡画面 → 按 Enter 重新开始

### 6.2 装备系统（4 种稀有度）

| 稀有度 | 颜色 | 属性倍率 | 掉落率 |
|--------|------|----------|--------|
| **普通** | 灰色 | ×1.0 | 60% |
| **稀有** | 蓝色 | ×1.5 | 25% |
| **史诗** | 紫色 | ×2.0 | 12% |
| **传说** | 橙色 | ×3.0 | 3% |

- **武器**（W）：提升攻击力
- **护甲**（A）：提升防御力
- **药水**（P）：恢复生命值

装备后 HUD 上的 ATK/DEF 实时变化。

### 6.3 Buff 状态系统（B1~B7 完整实现）

**Buff 类型**（3 种，JSON 配置驱动）：

| Buff | 类型 | 效果 | 持续 | 最大层数 | 来源 |
|------|------|------|------|----------|------|
| **中毒** (poison) | DOT | 每层每 0.5s 跳 3 点物理伤害 | 4s | 5 | 斩击、兽人攻击 |
| **减速** (slow) | STAT_MOD | 每层移速 ×0.7 | 3s | 3 | 神罚、史莱姆攻击 |
| **攻击提升** (attack_up) | STAT_MOD | 每层攻击力 +30% | 6s | 3 | 自愈、力量药剂 |

**玩法接入**（B6）：
- **技能**：斩击 30% 上毒、神罚 25% 减速、自愈必定攻击提升
- **怪物**：史莱姆攻击 25% 减速、兽人攻击 25% 上毒
- **道具**：力量药剂使用后攻击提升 6s（20% 掉落概率）

**Buff HUD**（B3）：
- 玩家 HUD：技能栏下方显示"显示名 ×层数 剩余时间"
- 怪物头上：简写标签（毒×2 / 慢×1 / 攻×1）

**配置化**（B4）：`resources/buffs.json` 驱动显示名/简写/颜色

**存档**（B5）：`active_buffs` 完整存档恢复，老存档兼容

### 6.4 技能系统

**主动技能**（按键 1-4 释放，有冷却）：

| 技能 | 冷却 | 效果 |
|------|------|------|
| **斩击** | 2s | 前方扇形范围伤害（ATK×1.5） |
| **火球** | 5s | 远程单体高伤害（ATK×2.5） |
| **自愈** | 8s | 恢复 HP（MaxHP×20%） |

**被动技能**（习得后常驻生效）：

| 技能 | 效果 |
|------|------|
| **铁壁** | 永久提升防御力 |
| **狂暴** | 永久提升攻击力 |

技能可升级（Lv1 → Lv5），每级伤害/效果 +30%，冷却 −10%。

击杀怪物有 15% 概率习得新技能。

### 6.5 怪物 AI

怪物有三种行为状态：

```
巡逻（IDLE）── 发现你 ──→ 追击（CHASE）── 贴近你 ──→ 攻击（ATTACK）
    ↑                                                    │
    └──────────── 脱离视野 ───────────────────────────────┘
```

### 6.6 Boss — 深渊领主

| 属性 | 值 |
|------|-----|
| HP | 200 |
| ATK / DEF | 15 / 8 |
| 特征 | 红色光晕 + 金色边框 + 体型更大 |

**Boss 技能**：

| 技能 | 冷却 | 效果 |
|------|------|------|
| 暗影冲击 | 5s | 前方锥形范围伤害 |
| 地裂 | 7s | 自身周围圆形 AOE |
| 召唤兽人 | 15s | 在身边召唤 2 只兽人 |

**狂暴**：HP ≤ 40% 时进入狂暴，移速 ×1.6，技能冷却 ×0.7。

**击杀奖励**：
- 必掉：**传说武器「魔渊之刃」**
- 必掉：**传说药水「神谕药剂」**
- 自动学习：**随机新技能**

### 6.7 楼层与等级

- **15 层关卡**，每 5 层一个 Boss（5层/10层/15层）
- Boss 关进入时展示完整介绍画面（名称/属性/技能/背景故事），确认后 1 秒特写
- **难度递增**：每层怪物 HP 和 ATK 逐步增长（×1.0 → ×3.3）
- **Boss**：暗影骑士→地狱火魔→深渊之主·终焉
- **等级获技能**：每升一级自动习得一个不重复技能（最多 4 个主动）
- **经验公式**：升级需 Level² × 20 XP

### 6.8 特殊房间系统（B8/B9/B10 + D8 扩展）

每层地牢中随机分布 2~3 个特殊房间（9 种类型）。

**三种特殊房间**：

| 房间 | 图标 | 效果 | 复用系统 |
|------|------|------|----------|
| **祭坛** (ALTAR) | `+` 琥珀色地板 | 4 结果池随机（25%）：攻击赐福 / 治愈赐福 / 代价换力量 / 净化负面 | Buff / Heal |
| **宝箱** (TREASURE) | `$` 深蓝色地板 | 品质分层（60% 普通 / 30% 丰厚 2 件 / 10% 祝福 +attack_up） | 物品生成 / Inventory |
| **泉水** (FOUNTAIN) | `~` 深绿色地板 | 回满 HP + 净化 poison/slow | Heal / Buff |

**交互规则**：
- 首次走入房间 → 弹出发现提示（2.5 秒淡出，如"你发现了一座古老祭坛。"）
- 站在房间内按 **E** → 触发奖励（优先于拾取）
- 每个房间每层只能触发一次，触发后地板灰化
- 发现状态（`discovered`）和触发状态（`triggered`）独立存档

**Seed 驱动地图恢复**：
- 每层生成时记录 `dungeon_seed`
- 存档保存 `seed` + `special_triggered` + `special_discovered`
- 读档用同 seed 确定性重建地图 → 恢复所有房间状态

### 6.9 圣物系统（B11/B12 + D8 扩展至 30 个）

Relic 是挂在 Player 身上的局内常驻被动构筑物。通过 JSON 配置驱动。

**30 个圣物**（common×14, rare×9, epic×6, legendary×3），宝箱品质分级掉落，按 R 键查看圣物图鉴。

核心 relic：血纹护符(+20HP)、毒牙(poison+1)、金色骰子(额外物品)、猎人之眼(+10%速)、吸血之刃(击杀回血)、战鼓(+15%ATK)、战斗图腾(击杀attack_up)、铁之心(+10HP)、贤者之叶(治疗+10)、商人硬币(掉率+15%+物品)、瘟疫面具(中毒-1) 等。

**稀有度与掉落**：

| 稀有度 | 颜色 | 宝箱掉落 |
|--------|------|----------|
| 普通 | 金色 | 普通10% / 丰厚20% / 祝福35% |
| 稀有 | 蓝色 | 同上（按权重分档） |
| 史诗 | 紫色 | 同上 |

- 宝箱品质越高，relic 掉率越高
- 已持有 relic 不重复发
- 按 **R** 键打开圣物图鉴

**存档**：玩家持有 relic 列表写入存档，旧存档兼容。

### 6.10 地图生成

每次进入游戏，地图通过 **BSP（二分空间划分）** 算法从头随机生成：

- 12 个房间 + L 形走廊
- 房间尺寸、位置、连接方式全部随机
- 玩家出生在第一个房间，Boss 在最远的房间

---

## 七、游戏流程

```
标题画面 → Enter 开始
    ↓
随机生成地牢 + 放置怪物 + Boss
    ↓
清空房间怪物
    ↓
金色楼梯激活 → 按 > 进入下一层
    ↓
第 5 / 10 / 15 层挑战 Boss → 通关画面
```

---

## 八、项目结构

```
roguelike/
├── main.py               # 程序入口 (字体/音频/CrashHandler)
├── game.py               # 游戏引擎（主循环 + 场景管理）
├── config.py             # 全局配置常量
├── src/
│   ├── core/             # 引擎框架
│   │   ├── scene.py      # Scene 基类（enter/exit/update/render）
│   │   ├── event_bus.py  # G6: EventBus — 30事件类型 pub/sub
│   │   ├── timeline.py   # G5.8.6: Timeline — delay/duration/callback序列
│   │   ├── replay/       # G6: ReplayRecorder + ReplayPlayer
│   │   └── sim/          # G6: SimAI + SimRunner 自动平衡测试
│   ├── entities/         # 实体模块
│   │   ├── entity.py     # 实体基类 (位置+碰撞框)
│   │   ├── components.py # CombatStats + RelicInstance
│   │   ├── player.py     # Player + Direction + 等级/XP
│   │   ├── monster.py    # Monster + spawn_monster 工厂
│   │   ├── ai.py         # MonsterAI: IDLE→CHASE→ATTACK
│   │   ├── boss.py       # BossAI + 3 BossSkill + 狂暴
│   │   ├── item.py       # 4 Rarity + Equipment/Consumable/Charm
│   │   └── skill.py      # 4 Active + 2 Passive + SkillManager
│   ├── systems/          # 游戏系统
│   │   ├── combat_system.py     # calculate_damage / find_attack_target
│   │   ├── inventory_system.py  # Inventory: add/remove/equip/use
│   │   ├── skill_system.py      # get_targets_in_cone
│   │   ├── buff_system.py       # BuffDef/Instance/Trigger + apply/tick
│   │   ├── relic_system.py      # RelicDef + try_grant_random_relic
│   │   └── relic_archive.py     # RelicArchive 跨局收集/熟练度/星标
│   ├── game/             # D1-D6: 游戏配置与子系统
│   │   ├── floor_config.py      # FloorConfig + FloorNarrative 15层数据
│   │   ├── build_tag.py         # BuildTag 标签枚举 (19种)
│   │   ├── build_score.py       # BuildScore + BuildType 12流派判定
│   │   ├── build_theme.py       # G5.8.2: BuildTheme 12预设主题色 → dmg 3-tier
│   │   ├── enemy_defs.py        # G5: EnemyDef — enemies.json 31种敌人
│   │   ├── skill_defs.py         # G5: SkillDef — skills.json 20技能定义
│   │   ├── event_system.py      # D4: EventType (10种) + DungeonEvent
│   │   ├── world_state.py       # WorldState + WorldFlag 标志位
│   │   ├── growth_curve.py      # GrowthCurve 15层难度曲线
│   │   ├── boss_narrative.py    # BossDialogue 自适应对话
│   │   ├── meta_progression.py  # MetaProgression + RunSummary
│   │   └── ending_director.py   # EndingDirector 五结局判定
│   ├── directors/        # D0-D6/G5.8: Director 编排 + Presentation 调度
│   │   ├── boss_system_director.py
│   │   ├── gameplay_system_director.py
│   │   ├── presentation_system_director.py  # G5.8.7: dispatch() 统一入口
│   │   ├── audio_director.py               # G5.8.4: crossfade/Phase2 cue/ducking
│   │   └── game_flow_director.py
│   ├── scenes/           # 场景模块
│   │   ├── title_scene.py        # 标题画面 (粒子 + 菜单 + 操作说明)
│   │   ├── game_scene.py         # 核心游戏 (~1200行)
│   │   ├── floor_select_scene.py # 15关选关网格
│   │   ├── tutorial_scene.py     # 6阶段教程
│   │   ├── death_scene.py        # 死亡画面
│   │   └── victory_scene.py      # 通关画面
│   ├── world/            # 世界模块
│   │   ├── tile.py       # TileType + Tile
│   │   ├── game_map.py   # 2D瓦片网格 / 碰撞 / 特殊房间查询
│   │   ├── dungeon_generator.py  # BSP 地牢生成 (seed 驱动)
│   │   ├── special_room.py       # 特殊房间: 3类型/交互/发现
│   │   └── tile_renderer.py      # 瓦片渲染器 (3D墙/地面纹理)
│   ├── ui_helpers.py     # draw_panel/glow_text/progress_bar/Particle
│   ├── fx_engine.py      # VFX: pulse/arc/bolt/spark/slash
│   ├── bgm_engine.py     # 4支BGM (和弦+旋律+低音+鼓轨)
│   ├── sfx_engine.py     # 13种SFX (程序合成 + jojo_timestop.mp3)
│   └── tutorial.py       # 教程引导逻辑
├── resources/            # JSON 资源配置
│   ├── vfx_recipes.json  # G5.8.5: 12 VFX recipes + 11 presets + staged delays
│   ├── buffs.json        # Buff 配置 (25种)
│   ├── relics.json       # Relic 配置 (63种)
│   ├── enemies.json      # 敌人配置 (31种)
│   ├── bosses.json       # Boss 配置 (6种)
│   ├── skills.json       # 技能配置 (20种)
│   └── ... (共11个JSON)
├── saves/                # 存档 (save.json)
│   └── save_manager.py   # JSON 序列化/反序列化
├── assets/               # 外部资源
│   └── jojo_timestop.mp3 # The World 时停音效
└── docs/                 # 设计文档
    ├── GDD-review.md     # 玩法设计审查
    └── 类图与架构说明.md  # 类图与架构
```

---

## 九、开发进度

| Milestone | 内容 | 状态 |
|-----------|------|------|
| M1 | 项目骨架 + 窗口 + 主循环 | ✅ |
| M2 | 玩家移动（WASD + 朝向） | ✅ |
| M3 | 地图系统（瓷砖 / 碰撞 / 摄像机） | ✅ |
| M4 | 战斗系统（攻击 / HP / 死亡） | ✅ |
| M5 | 怪物 AI（巡逻 / 追击 / 攻击） | ✅ |
| M6 | BSP 随机地图生成 | ✅ |
| M7 | 装备系统（稀有度 / 武器 / 防具 / 药水） | ✅ |
| M8 | 技能系统（主动 / 被动 / 冷却 / 升级） | ✅ |
| M9 | Boss（状态机 AI / 3 技能 / 狂暴 / 奖励） | ✅ |
| M10 | 15层关卡 + 3Boss + 等级获技能 + Boss介绍 | ✅ |
| M11 | 存档系统（JSON 完整序列化） | ✅ |
| M12 | 程序化音频（8SFX + 4BGM） | ✅ |
| M13 | Buff 系统（配置化/存档/HUD/玩法接入/触发统一） | ✅ |
| M14 | 特殊房间系统（祭坛/宝箱/泉水 + 发现提示 + 消息条 + Seed驱动存档恢复） | ✅ |
| M15 | 特殊房间内容深化（祭坛4结果池 / 宝箱品质分层 / 泉水净化） | ✅ |
| M16 | 特殊房间体验增强（discovered/triggered 分离 + 存档 + 屏幕消息显示） | ✅ |
| M17 | 圣物系统 MVP（5 relic / 宝箱掉落 / 局内效果 / HUD / 存档） | ✅ |
| M18 | 圣物内容扩展（30 relic + 4稀有度 + 宝箱权重掉落 + R 面板） | ✅ |
| M19 | UI 引导 + 操作说明 / 快捷键提示 / 首次 relic 提示 | ✅ |
| M20 | D8: 特殊房间扩展（3→9）+ Buff扩展（5→20）+ 数值平衡 | ✅ |
| M20 | RelicArchive 跨局收集（收集率/熟练度星标）+ 标题操作说明按键修正 | ✅ |
| D0  | Director 架构预铺（Boss/Gameplay/Presentation/Flow 四层骨架） | ✅ |
| D1  | FloorConfig 统一配置 + 15层叙事数据 + 楼层/章节入场演出 + 随机旁白 | ✅ |
| D2  | BuildTag 构筑标签 + BuildScore 流派识别 + GrowthCurve 难度曲线 | ✅ |
| D3  | BuildType 六大流派判定 + PresentationDirector 消息系统 | ✅ |
| D4  | WorldState 世界标志位 + EventSystem 事件 + BossNarrative 叙事对话 | ✅ |
| D5  | BossSystemDirector 生命周期 + Phase2/LastStand/Death 通知 | ✅ |
| D6  | MetaProgression 局外成长 + EndingDirector 五结局 + RunSummary 统计 | ✅ |
| G5  | C++同期同步: +5技能行为类 +AIArchetype +Boss Phase2(6Boss) +JSON全量 | ✅ |
| G5.8.2 | BuildTheme: 7-field struct + 12 presets + dmg_color_for() 3-tier | ✅ |
| G5.8.3 | Camera: shake/dash offset/boss landing zoom | ✅ |
| G5.8.4 | Audio Director: crossfade + boss Phase2 cue + BGM ducking | ✅ |
| G5.8.5 | VFX Recipes: vfx_recipes.json (12 recipes/11 presets) + play_recipe() | ✅ |
| G5.8.6 | Timeline: delay/duration/callback sequenced events + include() | ✅ |
| G5.8.7 | Presentation Integration: PresentationEvent + dispatch() unified pipeline | ✅ |
| G5.8.8 | Timeline Presentation: 12 recipes with staged delays | ✅ |
| G6.1 | Biome System: 3 biomes (Prison/Volcano/Abyss) + tile_palette/enemy_pool/boss + ambient particles + biome BGM | ✅ |
| G6.2 | Landmark System: 9 biome landmarks (3 per biome) + environmental storytelling + SECRET room revival + floor_config/narrative → JSON | ✅ |
| G6.3 | Biome Hazards: 6 environmental hazards on landmark rooms (slow_zone/burn_tick/confuse/deflect) | ✅ |
| G6.4 | Biome Events: 6 risk/reward events + module boundary cleanup (Presentation no longer depends on BuildScore) | ✅ |
| G6.5 | Encounter Framework: unified NPC/dialogue/trade/event model + 6 NPC encounters (2 per biome) + multi-round dialogue engine | ✅ |
| G6.6 | Exploration: secret encounters via wall_interact + SECRET room placement + conditions[] pre-emptive field | ✅ |
| G6.7 | Meta Progression: 3-layer Flags (RunFlag/MetaFlag/SaveFlag) + ConditionEvaluator DSL + Action dict+string dual format + IF→SHOW→DO pipeline | ✅ |

---

## G6 World Expansion (2026-07-21)

### G6.1 Biome System

将 15 层地牢划分为 3 个主题区域，每个区域独立视觉/音频/敌人/Boss：

| 楼层 | Biome | BGM | 瓦片色 | 敌人 | Boss |
|:---|:---|:---|:---|:---|:---|
| 1–5 | Forgotten Prison 遗忘监牢 | `prison` (72BPM square/sparse) | 暗紫灰石墙 | skeleton_archer, bone_soldier, slime, shadow_stalker | 暗影骑士 (F5) |
| 6–10 | Ash Volcano 灰烬火山 | `volcano` (90BPM saw/standard) | 暗红暖色墙 | fire_imp, elite_orc, orc, charger | 地狱火魔 (F10) |
| 11–15 | Void Abyss 虚空深渊 | `abyss` (62BPM triangle/sparse) | 深紫黑墙 | shadow_stalker, dark_mage, shadow_assassin, void_walker | 深渊之主 (F15) |

**Ambient Layer（环境粒子）**：
| Biome | 粒子数 | 颜色 | 速度 | 效果 |
|:---|:---|:---|:---|:---|
| Prison | 6 | (140,135,150) 灰紫 | 12 | 缓慢上升的尘埃 |
| Volcano | 12 | (255,120,30) 橙红 | 20 | 快速上升的余烬 |
| Abyss | 10 | (100,60,140) 深紫 | 8 | 缓慢漂浮的虚空粒子 |

**数据驱动**：`resources/biomes.json` 定义所有 Biome 参数，`src/game/biome.py` 加载/查询。
跨 Biome 边界（F5→F6, F10→F11）触发章节过渡演出 + "进入 XXX" 消息条。

### G6.2 Landmark System

每个 Biome 有 3 个地标房间，提供环境叙事（Environmental Storytelling）：
| Biome | Landmark | 图标 | 叙事 |
|:---|:---|:---|:---|
| Prison | broken_cell / torture_chamber / collapsed_tunnel | ⚒ / † / ▼ | 牢房/刑具/落石 |
| Volcano | lava_rift / forge_ruins / fire_pillar | ≈ / ⚔ / ☀ | 熔岩/锻炉/火柱 |
| Abyss | floating_altar / void_crack / ancient_gate | ◎ / ◆ / ☗ | 浮坛/虚空裂/石门 |

Landmark = `SpecialRoom(type=LANDMARK, landmark_id="...")` — 复用现有房间系统，无继承。
`resources/world/` 目录每 Biome 一个 JSON 单文件（prison/volcano/abyss），含完整 biome + landmark + hazard 数据。
`floor_config.py` 150 行硬编码 → `resources/floor_config.json` + `floor_narrative.json` 懒加载。

### G6.3 Biome Hazards

6 个环境机制挂在 landmark 房间上，每帧 tick：
| Biome | Landmark | Hazard | 效果 |
|:---|:---|:---|:---|
| Prison | broken_cell | swinging_chains | 每 2s 减速 35% |
| Prison | collapsed_tunnel | rockfall | 每 4s 3 dmg |
| Volcano | lava_rift | eruption | 每 3s 5 dmg |
| Volcano | fire_pillar | heat_wave | 每 1.5s 减速 30% |
| Abyss | void_crack | space_warp | 每 5s 方向反转 |
| Abyss | floating_altar | gravity_flux | 投射物偏转 |

### G6.4 Biome Events + Module Cleanup

6 个风险/奖励事件（25% 触发率，按 1/2 选择）：
| Biome | Event | 奖励 | 风险 |
|:---|:---|:---|:---|
| Prison | prisoner_rescue | +2 attack_up | 召唤精英兽人 |
| Prison | execution_ground | +1 relic | +2 curse |
| Volcano | forge_of_fire | rare 装备 | -15% HP |
| Abyss | void_whisper | +1 技能等级 | confuse 5s |
| Abyss | sacrificial_altar | +2 relics | -50% HP |

**模块边界收紧**：`PresentationSystemDirector.update_theme()` 不再调用 `calculate_build()` — 接收 BuildType 由 GameScene 计算传入。Timeline 删除死代码 `__import__`。

### G6.5 Encounter Framework

统一 NPC/事件/交易/对话为 `EncounterDef` 数据模型（2 per biome）：
| Biome | Encounter | 类型 | 节点 |
|:---|:---|:---|:---|
| Prison | prisoner_merchant | npc+trader | greet→shop(HP换装备)→farewell |
| Prison | old_prisoner | npc | greet→story→advice(+buff) |
| Volcano | forge_master | npc+trader | greet→forge/story→farewell |
| Volcano | lost_miner | npc(非重复) | greet→saved→reward |
| Abyss | watcher | npc | greet→identity/fight→lore→blessing |
| Abyss | void_trader | npc+trader | greet→trade(HP换圣物+传说) |

多轮对话引擎：`_encounter_state = {def, current_node}` → 每轮渲染 text + choices → next node。

### G6.6 Exploration

3 个秘密 Encounter → `trigger="wall_interact"` (面向墙按 E)：
| Biome | Secret | 奖励 | 风险 |
|:---|:---|:---|:---|
| Prison | hidden_prison_vault | 史诗装备 | 骷髅×2 |
| Volcano | volcanic_geode | 2 圣物 | -15% HP |
| Abyss | void_memory | +2 技能等级 | +1 curse |

Secret 不是新类型 — 就是 `EncounterDef(trigger="wall_interact")`。零新文件。
`SpecialRoomType.SECRET` 复用已有 enum（之前未生成），`DungeonGenerator` 30% 概率放置。

### G6.7 Meta Progression: IF→SHOW→DO

三层 Flag 拆分 + ConditionEvaluator DSL + Action 双格式：
```
pick_encounter_for_biome(biome, ctx=EvalContext)
  │ evaluate_conditions(["flag:500","floor>=3"], ctx)   ← IF
  ▼
EncounterDef.dialogue[n]                                 ← SHOW
  ▼
execute_action(choice.effect)                           ← DO
execute_action(choice.risk)
  │ set_meta_flag(MetaFlag.Necromancer_Unlocked)
```

| 组件 | 文件 | 说明 |
|:---|:---|:---|
| RunFlag | `world_state.py` | 本局 flag（15 个） |
| MetaFlag | `meta_state.py` + `meta_save.json` | 跨局 flag（5 个） |
| ConditionEvaluator | `condition_evaluator.py` | `"flag:X"` `"floor>=N"` `"biome:Y"` DSL |
| execute_action() | `encounter.py` | str + dict 双格式自动检测 |

---

## G5 C++同期同步 (2026-07-21)

### 新增/更新模块
| 文件 | 说明 |
|------|------|
| `src/game/enemy_defs.py` | EnemyDef loader — enemies.json 31种敌人数据驱动 |
| `src/game/skill_defs.py` | SkillDef loader — skills.json 20技能定义 |
| `resources/` | **10个JSON全部同步C++版**: buffs(25), relics(63), enemies(31), bosses(6), skills(20), items(36), quests(12), dialogues(34), endings(5), meta_nodes(10) |

### 更新的核心系统
| 系统 | 同步内容 |
|------|---------|
| `monster.py` spawn_monster() | EnemyDef优先创建, 24+类型回退预设, 颜色/触发/技能全支持 |
| `buff_system.py` BuffDef | +tags字段 + 15种buff自动标签 (electrified/frostbite/deep_wound等) |
| `build_score.py` | 6→12 BuildType (冰霜法师/雷电法师/流血剑士/暗影刺客/重装守卫/召唤领主) |
| `skill.py` | +5个行为类: IceNovaSkill, ChainLightningSkill, ShadowStrikeSkill, BloodFrenzySkill, SummonSpiritSkill (9→14主动技能) |
| `ai.py` | +AIArchetype + MonsterSkillType(12)+skill池+行为钩子 (Sniper/Controller/Ambush/Guardian) |
| `boss.py` | +WhirlwindSkill/LaserBarrageSkill + 6 Boss Phase2 + `_boss_id`驱动 |

**数据同步**: 10 JSON ↔ C++ 100%一致
**代码同步**: 技能行为/AI Archetype/Boss Phase2 完全一致

## G6 架构同步 (2026-07)

| 新增模块 | 说明 |
|----------|------|
| `src/core/event_bus.py` | EventBus — 30事件类型 pub/sub (C++ parity) |
| `src/core/replay/` | ReplayRecorder + ReplayPlayer + StateHash |
| `src/core/sim/` | SimAI + SimRunner — 自动平衡测试 |

## G5.8 Presentation同步 (2026-07-21)

### G5.8.2 BuildTheme
| 文件 | 说明 |
|------|------|
| `src/game/build_theme.py` | BuildTheme class — 7字段(primary/secondary/accent/name/particle_speed/explosion_scale/vfx_preset) + 12 BuildType预设 + dmg_color_for() 3级着色(≥50金/≥25主题色/≥10混合/其余灰) |
| `src/directors/presentation_system_director.py` | +active_theme + update_theme() + spawn_themed_damage() + get_particle_speed()/get_explosion_scale() |
| `src/scenes/game_scene.py` | BUILD COMPLETE/CHANGED → update_theme(); 伤害数字渲染接入 |

### G5.8.5 VFX Recipes
| 文件 | 说明 |
|------|------|
| `resources/vfx_recipes.json` | 12 recipes (melee_hit/skill_slash/fireball/heal/ice_nova/chain_lightning/boss_cone/circle_aoe/summon/time_stop/level_up/boss_phase2) + 11 color presets |
| `src/fx_engine.py` | +play_recipe() 按名称+预设生成特效dict列表; +get_recipe_names()/get_preset_names() |

### G5.8.3 Camera
| 文件 | 说明 |
|------|------|
| `src/directors/presentation_system_director.py` | +dash_offset_x/y + zoom_level + boss_landing_timer + trigger_boss_landing() + set_dash_offset() + get_camera_shake_offset() |
| `src/scenes/game_scene.py` | _get_camera_offset() 集成震动/冲刺偏移/缩放; Boss出生触发 landing 特效 |

### G5.8.4 Audio Director
| 文件 | 说明 |
|------|------|
| `src/directors/audio_director.py` | AudioDirector — crossfade_to()/play_boss_phase2_cue()/duck_bgm()/restore_bgm() |
| `src/scenes/game_scene.py` | +audio实例; _check_boss_phase2() 检测狂暴→音频+VFX; enter_floor() 重置Phase2 |

### G5.8.6 Timeline Recipe
| 文件 | 说明 |
|------|------|
| `src/core/timeline.py` | Timeline + TimelineEvent — delay/duration/callback序列; include() 组合复用; register_timeline_recipe() 命名注册; 内置boss_intro/level_up配方 |

### G5.8.7 Presentation Integration
| 文件 | 说明 |
|------|------|
| `src/directors/presentation_system_director.py` | +PresentationEvent + dispatch() 统一分发; 8技能→recipe映射表 (数据驱动, 删if/elif链) |
| `src/directors/audio_director.py` | +on_presentation_event() 统一SFX入口; +BGM自动ducking |
| `src/scenes/game_scene.py` | 删除 _add_skill_effect(); -30 处直接耦合; BGM走crossfade_to() |
| `resources/vfx_recipes.json` | +sfx/hit_sfx/camera_shake 字段 (recipe自描述) |

**核心**：Gameplay→Presentation 30 处直接调用 → 1 个 `dispatch(PresentationEvent)` 入口。
BuildTheme 为所有视觉风格的唯一来源，零硬编码 preset。

### G5.8.8 Timeline Presentation
| 文件 | 说明 |
|------|------|
| `resources/vfx_recipes.json` | 12 recipe 全量 `delay` 字段 — IceNova: 0ms ring→120ms explosion→250ms shatter→350ms flash |
| `src/fx_engine.py` | +recipe_to_timeline() 延迟步骤→Timeline; _make_step_effects() 步骤→效果重构 |
| `src/directors/presentation_system_director.py` | +bind_effects_target() + _active_timelines管理 + tick()推进; dispatch()自动分离即时/延迟 |

**效果**：Boss Phase2 从瞬间全开 → 0ms freeze→80ms flash→250ms roar→400ms shockwave→700ms zoom wave


---

## C++ 版同步进展 (roguelike_cpp)

C++ 版 (Raylib 5.0 + C++17 + CMake) 在 Python 版基础上已完成 **G1~G5 五个阶段的深度重构**。

### 核心差异对比

| 维度 | Python 版 | C++ 版 |
|------|----------|--------|
| 数据驱动 | 2 JSON (buffs 5种 / relics 11种) | **10 JSON** (buff 25 / relic 63 / enemy 31 / boss 6 / skill 20 / item 36 / quest 12 / dialogue 34 / ending 5 / meta 10) |
| Build 流派 | 6 种 | **12 种** (新: 冰霜/雷电/流血/暗影/重装/召唤) |
| 技能 | 3 主动 + 2 被动 | **14 主动 + 6 被动** (含 5 个独特行为类: 冰爆/连锁闪电/暗影突刺/血怒/召唤英灵) |
| 敌人 | 基础 8 种 | **31 种 / 9 种 AI Archetype** (狙击/控制/潜伏/守卫 — 行为与外观解耦) |
| Boss | 1 种 (深渊领主) | **6 种, 各唯一 Phase2 机制** (旋风斩/激光弹幕/引力拉扯等) |
| 事件 | 10 种 | **18 种** (40% 生成率, Ch2+ 双事件) |
| 特殊房间 | 3 种 | **9 种** (商店/铁匠/图书馆/赌徒/神殿/隐藏房) |
| Mod 支持 | 无 | **完整 Provider + Namespace + Dependency + MergePatch** |
| Replay 系统 | 无 | **录制 + 回放 + 确定性 RNG + Hash 验证** |
| 自动化模拟 | 无 | **SimAI + --sim N CLI + 平衡报告** |
| 存档 | save.json | **Save v3** (atl/rul/qst/end 字段, 3 版本向后兼容) |
| EventBus | 无 | **30 种事件类型**, Manager-Director-Presentation 解耦 |
| CLI | 无 | `--record` / `--replay` / `--sim N` |

### Git: [github.com/DIO07-0309/roguelike-cpp](https://github.com/DIO07-0309/roguelike-cpp) | v0.8.5 (G5.7 Final)
