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

### 6.8 特殊房间系统（B8/B9/B10 完整实现）

每层地牢中随机分布 2~3 个特殊房间，房间类型通过 `SpecialRoomType` 强类型枚举管理。

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

### 6.9 圣物系统（B11/B12 完整实现）

Relic 是挂在 Player 身上的局内常驻被动构筑物，不占技能栏、非消耗品，一旦获得就在本局后续楼层持续生效。

**11 个圣物**：

| 圣物 | 稀有度 | 效果 | 接入点 |
|------|--------|------|--------|
| **血纹护符** | 普通 | 最大生命 +20 | get_effective_max_hp |
| **毒牙** | 普通 | 怪物身上 poison 每跳 +1 | tick_buffs |
| **金色骰子** | 稀有 | 宝箱额外多给 1 件物品 | _exec_treasure |
| **猎人之眼** | 普通 | 移速 +10% | get_effective_speed |
| **吸血之刃** | 普通 | 击杀怪物 20% 回 5 HP | _on_monster_killed |
| **战鼓** | 普通 | 攻击力 +15% | get_effective_attack |
| **战斗图腾** | 普通 | 击杀 15% 获 attack_up | _on_monster_killed |
| **铁之心** | 普通 | 最大生命 +10 | get_effective_max_hp |
| **贤者之叶** | 稀有 | 祭坛/泉水治疗 +10 | _altar_heal / _exec_fountain |
| **商人硬币** | 稀有 | relic 掉率 +15% + 额外 1 件物品 | _exec_treasure |
| **瘟疫面具** | 史诗 | 玩家中毒每跳 -1 | tick_buffs(Player) |

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
│   │   └── scene.py      # Scene 基类（enter/exit/update/render）
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
│   │   ├── build_score.py       # BuildScore + BuildType 六流派判定
│   │   ├── event_system.py      # EventType (10种) + DungeonEvent
│   │   ├── world_state.py       # WorldState + WorldFlag 标志位
│   │   ├── growth_curve.py      # GrowthCurve 15层难度曲线
│   │   ├── boss_narrative.py    # BossDialogue 自适应对话
│   │   ├── meta_progression.py  # MetaProgression + RunSummary
│   │   └── ending_director.py   # EndingDirector 五结局判定
│   ├── directors/        # D0-D6: Director 编排层
│   │   ├── boss_system_director.py
│   │   ├── gameplay_system_director.py
│   │   ├── presentation_system_director.py
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
│   ├── sfx_engine.py     # 8SFX (程序合成 + jojo_timestop.mp3)
│   └── tutorial.py       # 教程引导逻辑
├── resources/            # JSON 资源配置
│   ├── buffs.json        # Buff 配置 (5种)
│   └── relics.json       # Relic 配置 (11种 + rarity)
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
| M18 | 圣物内容扩展（11 relic + rarity + 宝箱权重掉落 + R 面板） | ✅ |
| M19 | UI 引导 + 字体覆盖稳定化（操作说明 / 快捷键提示 / 首次 relic 提示） | ✅ |
| M20 | RelicArchive 跨局收集（收集率/熟练度星标）+ 标题操作说明按键修正 | ✅ |
| D0  | Director 架构预铺（Boss/Gameplay/Presentation/Flow 四层骨架） | ✅ |
| D1  | FloorConfig 统一配置 + 15层叙事数据 + 楼层/章节入场演出 + 随机旁白 | ✅ |
| D2  | BuildTag 构筑标签 + BuildScore 流派识别 + GrowthCurve 难度曲线 | ✅ |
| D3  | BuildType 六大流派判定 + PresentationDirector 消息系统 | ✅ |
| D4  | WorldState 世界标志位 + EventSystem 事件 + BossNarrative 叙事对话 | ✅ |
| D5  | BossSystemDirector 生命周期 + Phase2/LastStand/Death 通知 | ✅ |
| D6  | MetaProgression 局外成长 + EndingDirector 五结局 + RunSummary 统计 | ✅ |
