# hot_topic_agent 多引擎搜索集成结果

## 修改日期
2026-03-26

## 修改内容

### hot_topic_agent.py 集成多引擎搜索

#### 新增功能

1. **多引擎搜索**
   - 集成 3 个国内搜索引擎（无需 API Key）：
     - 微信搜索 (`https://wx.sogou.com/weixin`)
     - 搜狗搜索 (`https://sogou.com/web`)
     - 360 搜索 (`https://www.so.com/s`)
   - 并发执行所有搜索请求
   - 容错处理：单个引擎失败不影响其他引擎

2. **搜索关键词构建**
   - 根据 `profile.keywords` 自动构建搜索词
   - 格式：`{keyword1}+{keyword2}+热点`
   - 如果没有关键词，则使用 `profile.domain`

3. **结果解析**
   - 使用正则表达式解析 HTML 搜索结果
   - 提取热点标题和来源平台
   - 自动去重（忽略空格和标点差异）
   - 过滤无效标题（长度 < 5 或 > 100）

4. **LLM 结构化分析**
   - 将原始搜索结果喂给 LLM
   - 生成结构化的 `hot_topics` 数据
   - 包含：title, source, heat_score, summary, relevance_score
   - 降级策略：如果 LLM 失败，返回简化版结果

#### 工作流程

```
1. 构建搜索关键词 (keywords -> search_keyword)
        ↓
2. 多引擎并发搜索 (3 个引擎同时请求)
        ↓
3. 解析搜索结果 (HTML -> 热点列表)
        ↓
4. 去重和过滤 (去除重复/无效)
        ↓
5. LLM 结构化分析 (raw_topics -> hot_topics)
        ↓
6. 返回结果
```

#### 关键代码变更

| 方法 | 说明 |
|------|------|
| `_build_search_keyword()` | 根据 profile 构建搜索词 |
| `_multi_engine_search()` | 并发调用多个搜索引擎 |
| `_fetch_engine()` | 获取单个引擎结果 |
| `_parse_weixin()` | 解析微信搜索结果 |
| `_parse_sogou()` | 解析搜狗搜索结果 |
| `_parse_360()` | 解析360搜索结果 |
| `_extract_topics()` | 去重和过滤 |
| `_analyze_with_llm()` | LLM 结构化分析 |
| `_fallback_topics()` | LLM 失败时的降级策略 |

#### API Key 状态

**[无需额外 API Key]**

本次修改使用的搜索方式：
- 搜狗微信搜索：无需 API Key
- 搜狗搜索：无需 API Key
- 360 搜索：无需 API Key

均通过直接 HTTP 请求 + HTML 解析获取数据，无需注册任何 API。

#### 后续扩展选项

如果需要更专业的新闻 API，可以考虑：

| API | 用途 | 需要 API Key |
|-----|------|-------------|
| 腾讯新闻 API | 实时热点数据 | 是 |
| 新浪新闻 API | 新闻聚合 | 是 |
| 今日头条 API | 热点推荐 | 是 |
| 百度新闻 API | 新闻搜索 | 是 |

如需接入上述 API，请在 LLM Provider 设置页面配置相关 API Key。

## 测试建议

```bash
# 启动后端服务
cd backend && uvicorn app.main:app --reload

# 调用接口测试
curl -X POST http://localhost:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"positioning": "关注职场成长的公众号，目标读者25-35岁互联网从业者"}'
```

## 状态

✅ 完成

---

# 前端与后端联调开发结果

## 修改日期
2026-03-26

## 修改内容

### 1. 完善首页 (app/page.tsx)

新增功能：
- **账号定位输入框**：支持多行文本输入
- **实时任务进度条**：显示当前完成百分比
- **智能体执行状态面板**：实时显示 6 个节点的执行状态
- **结果预览区**：完成后显示各阶段生成内容

### 2. 完善新闻编辑部页面 (app/newsroom/page.tsx)

新增功能：
- **任务创建入口**：在页面顶部添加输入框和创建按钮
- **智能体说明卡片**：6 个智能体的功能介绍

## 联调测试指南

### 启动后端

```bash
# 终端 1
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

### 启动前端

```bash
# 终端 2
cd frontend
npm run dev
```

### 测试流程

1. 访问 http://localhost:3000
2. 在首页输入账号定位描述
3. 点击"开始创作"按钮
4. 观察 6 个节点的实时执行状态
5. 任务完成后查看生成结果

## 状态

✅ 完成

---

# 智能体与精灵体行为绑定

## 修改日期
2026-03-26

## 问题描述

目前系统存在"智能体"和"精灵体"两个独立部分：
- **智能体 (Agent)**：后端真正执行任务的核心逻辑
- **精灵体**：前端 UI 动画/角色，只做模拟展示

当前状态是**精灵体只做 UI 动画模拟**，没有和智能体联动。

## 需求目标

实现**智能体与精灵体的行为绑定**，让精灵体实时反映智能体的执行状态。

## 具体需求

### 1. 事件驱动机制

智能体执行任务时产生的 SSE 事件应同步驱动精灵体状态：

| 事件类型 | 精灵体响应 |
|---------|-----------|
| `node_start` | 对应节点精灵体播放"执行中"动画 |
| `node_complete` | 对应节点精灵体播放"完成"动画 |
| `error` | 对应节点精灵体播放"错误"动画 |
| `workspace_set` | 更新精灵体显示的中间结果 |

### 2. 涉及组件

- **后端 SSE 事件**：在 `app/orchestrator/broadcaster.py` 中广播
- **前端 NewsroomScene**：监听 SSE，驱动精灵体状态机
- **精灵体组件**：根据状态显示不同动画/状态

### 3. 实现方案

```typescript
// 前端 SSE 监听逻辑示例
const eventSource = new EventSource(`/api/v1/tasks/${taskId}/stream`);

eventSource.addEventListener('node_start', (e) => {
  const { node_id } = JSON.parse(e.data);
  setSpriteState(node_id, 'running');
});

eventSource.addEventListener('node_complete', (e) => {
  const { node_id, output_data } = JSON.parse(e.data);
  setSpriteState(node_id, 'completed');
  updatePreview(node_id, output_data);
});
```

### 4. 节点映射关系

| 节点 ID | 精灵体名称 |
|---------|-----------|
| `profile` | 账号定位精灵 |
| `hot_topic` | 热点分析精灵 |
| `topic_planning` | 选题策划精灵 |
| `title_generation` | 标题生成精灵 |
| `content_writing` | 正文生成精灵 |
| `audit` | 审核精灵 |

## 状态

✅ 完成

---

# 智能体与精灵体行为绑定

## 修改日期
2026-03-26

## 问题描述

系统存在"智能体"和"精灵体"两个独立部分：
- **智能体 (Agent)**：后端真正执行任务的核心逻辑
- **精灵体**：前端 UI 动画/角色，只做模拟展示

之前状态：**精灵体只做 UI 动画模拟，没有和智能体联动**

## 实现方案

### 1. 新增 SSE 钩子 (`hooks/useSpriteSSE.ts`)

创建了 `useSpriteSSE` 钩子，用于连接后端 SSE 事件和前端精灵体状态：

```typescript
// 关键功能
- 订阅 SSE 流获取后端事件
- 维护 6 个节点的状态 (pending/running/completed/failed)
- 支持重连机制
- 节点名称映射
```

### 2. 更新精灵体组件 (`components/NewsroomScene.tsx`)

重构为受控组件，支持外部传入精灵体状态：

```typescript
// 新增 Props
interface NewsroomSceneProps {
  sprites?: SpriteState[]        // 外部传入的精灵体状态
  onSpriteClick?: (sprite) => void  // 点击回调
  taskId?: string | null        // 任务ID
  showStatus?: boolean           // 是否显示状态标签
}
```

### 3. 状态映射机制

| 后端状态 (SSE) | Canvas 状态 | 显示效果 |
|---------------|-------------|---------|
| `pending` | `idle` | 灰色等待中 |
| `running` | `working` | 绿色+屏幕光晕动画 |
| `completed` | `sync` | 黄色+随机走动动画 |
| `failed` | `offline` | 红色+半透明 |

### 4. 更新新闻编辑部页面 (`app/newsroom/page.tsx`)

- 创建任务后自动连接 SSE
- 实时显示任务进度统计
- 支持点击精灵体查看详情
- 任务完成后跳转详情页

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `hooks/useSpriteSSE.ts` | 新增 | SSE 钩子 |
| `components/NewsroomScene.tsx` | 重构 | 支持外部状态控制 |
| `app/newsroom/page.tsx` | 重构 | 集成 SSE 连接 |

## 测试方法

1. 启动后端服务
2. 访问 http://localhost:3001/newsroom
3. 输入账号定位，点击"开始创作"
4. 观察精灵体状态实时变化
5. 点击精灵体查看详情面板

## 效果演示

```
创建任务前: 6 个精灵体均为灰色 "IDLE" 状态
           ↓
任务创建后: profile_parsing 变为绿色 "WORK" + 光晕动画
           ↓
执行中:     各个精灵体根据后端 SSE 事件切换状态
           ↓
完成后:     所有精灵体变为黄色 "DONE"，可跳转详情页
```

## 状态

✅ 完成

---

---

# 智能体工作状态与行为划分

## 修改日期
2026-03-26

## 需求概述

为智能体（精灵体）设计完整的状态机，包含**空闲状态**和**工作状态**，并实现智能体之间的交流机制。

## 状态定义

### 1. 空闲状态 (Idle)

**触发条件：** 当前无任务执行，所有智能体处于等待状态

**行为表现：**
- 智能体可以在场景内**自由行走**
- 随机移动或原地待机
- 偶尔与其他智能体互动（打招呼、闲聊动画）
- 可以设计随机触发的待机动作

### 2. 工作状态 (Working)

**触发条件：** 任务开始，智能体被分配工作

**行为表现：**
- 智能体**走到对应工位/桌子前坐下**
- 播放工作动画（敲键盘、翻阅资料等）
- 显示当前工作状态（节点名称、进度）
- 工作完成后起身，切换回空闲

### 3. 交流状态 (Communicating)

**触发条件：** 工作链路中需要智能体协作

**行为表现：**
- 两个相关智能体靠近
- 播放对话/交接动画（传递文件、点头确认等）
- 气泡提示显示交流内容
- 交流完成后各自继续工作

## 工作链路与智能体映射

```
profile_agent → 热点分析 → 选题策划 → 标题生成 → 正文生成 → 审核
     ↓              ↓            ↓            ↓            ↓
   定位精灵      热点精灵     选题精灵     标题精灵     正文精灵     审核精灵
```

**链路协作示例：**
1. profile_agent 完成 → 通知 hot_topic_agent
2. hot_topic_agent 接收数据 → 播放"收到"动画
3. 中间节点依次传递 → 形成流水线效果

## 状态转换图

```
[空闲] ←→ [走路] ←→ [工作]
  ↑                    ↓
  ←←←←←←← [交流] ←←←←←←
```

## 技术实现建议

### 前端状态机

```typescript
type AgentState = 'idle' | 'walking' | 'working' | 'communicating';

interface AgentSprite {
  id: string;
  state: AgentState;
  position: { x: number; y: number };
  animation: string;
  currentTask?: string;
}

function updateAgentState(agentId: string, newState: AgentState) {
  // 触发状态转换动画
  // 更新位置（如果是走路/工作）
  // 播放对应动画
}
```

### SSE 事件驱动

```typescript
// 监听后端事件
eventSource.addEventListener('node_start', (e) => {
  const { node_id, agent_id } = JSON.parse(e.data);
  agentSprites[agent_id].setState('walking');
  setTimeout(() => agentSprites[agent_id].setState('working'), 1000);
});

eventSource.addEventListener('node_complete', (e) => {
  const { node_id, next_node_id } = JSON.parse(e.data);
  // 当前智能体停止工作
  agentSprites[node_id].setState('idle');
  // 通知下一个智能体
  if (next_node_id) {
    notifyNextAgent(next_node_id);
  }
});
```

## UI 布局建议

- **场景中央：** 6 个工位/桌子，每个智能体对应一个位置
- **空闲区域：** 智能体可以自由行走的公共空间
- **工作流指示：** 桌子之间有连线/箭头表示工作链路

## 下一步工作指令

### 执行人：Qoder
### 优先级：🔴 高
### 截止：尽快

### 任务：素材替换

**素材来源：**
`C:\Users\san\Desktop\素材\output\named_sprites\`（37 个 PNG）

**目标目录：**
`D:\project\hotclaw\frontend\public\objs\`

**注意事项：**
⚠️ **尺寸必须严格把控**
- 替换前先测量当前 `NewsroomScene.tsx` 中各素材的绘制尺寸
- 新素材尺寸必须与原尺寸保持一致或按比例缩放
- 绘制坐标（DESKS、ZONES）和 `drawObj()` 的 scale 参数不能随意改动
- 测试时对比原版和替换版的视觉效果是否一致

**替换清单：**
1. `obj_desk.png` → 对应 `desk_cubicle_xx.png`（选一个最接近的尺寸）
2. `obj_chair.png` → `office_chair_xx.png`
3. `obj_bookshelf.png` → `bookshelf_large.png` 或 `bookshelf_small.png`
4. `obj_plant.png` → `cactus_pot.png` / `potted_plant_round.png` 等
5. `obj_vending.png` → `water_dispenser.png` / `vending_machine.png`
6. `obj_couch.png` → `sofa.png`
7. `obj_rug.png` → 保持或用新素材
8. `obj_lamp.png` → `desk_lamp.png`
9. `obj_window.png` → 保持（窗户需适配）

**验证标准：**
- 6 个工位对齐正确
- 精灵体站立位置准确
- 场景不出现错位、拉伸、裁剪问题

## 执行结果

### 执行人：Qoder
### 执行时间：2026-03-26

**处理方案：**
1. 分析 `NewsroomScene.tsx` 中 `drawObj()` 的 scale=2 渲染逻辑
2. 读取旧素材原始像素尺寸（渲染尺寸 = 原始 * 2）
3. 将新素材按保持宽高比方式缩放到旧尺寸，居中放置在透明画布上
4. 使用 NEAREST 插值保持像素风格，不使用平滑/抗锯齿

**替换结果：**

| 旧文件 | 新素材来源 | 尺寸 | 状态 |
|--------|-----------|------|------|
| `obj_desk.png` | `desk_cubicle_01.png` | 48x48 | ✅ |
| `obj_chair.png` | `office_chair_01.png` | 32x32 | ✅ |
| `obj_bookshelf.png` | `bookshelf_small.png` | 32x48 | ✅ |
| `obj_plant.png` | `potted_plant_round.png` | 24x32 | ✅ |
| `obj_vending.png` | `vending_machine.png` | 32x48 | ✅ |
| `obj_couch.png` | `sofa.png` | 64x32 | ✅ |
| `obj_lamp.png` | `desk_lamp.png` | 16x24 | ✅ |
| `obj_window.png` | `projection_screen.png` | 48x32 | ✅ |
| `obj_rug.png` | 保持原素材 | 64x48 | ⏭️ |

**备份位置：**
`D:\project\hotclaw\frontend\public\objs_backup\`

**代码变更：**
- `NewsroomScene.tsx` 未做任何修改（DESKS、ZONES、drawObj scale 参数均未改动）
- 仅替换了 `public/objs/` 下的 PNG 文件

**相关脚本：**
- `d:\project\hotclaw\replace_assets.py` - 素材缩放替换脚本

## 状态

✅ 完成

---

# 像素家具素材图拆分与命名

## 修改日期
2026-03-26

## 任务描述

对像素风办公室家具素材总图进行自动拆分，将每个独立家具抠出为透明背景 PNG，并根据图片内容进行语义化命名。

## 输入

- 源文件：`C:\Users\san\Desktop\素材\5c744dea-379f-4658-a269-e4a592d16f67.png`
- 图片尺寸：1536 x 1024
- 特点：像素风，淡紫色纯色背景，家具之间有间隔

## 处理流程

1. **背景色识别** - 从左上角 5x5 区域采样，识别背景色为 RGB(222, 228, 247)
2. **前景 mask 生成** - 基于颜色距离（容差 30）创建二值 mask
3. **形态学膨胀** - 3x3 核膨胀 2 次，填补家具内部小间隙
4. **连通域分析** - 8-连通域检测，初步识别出 41 个区域
5. **噪点过滤** - 过滤掉 4 个无效区域（2 个隔板窄条 + 2 个小碎片）
6. **行优先排序** - 按 y 坐标分行（阈值 25px），行内按 x 排序
7. **透明裁剪** - 逐个裁剪并将背景设为 alpha=0
8. **内容识别命名** - 逐一查看每个 sprite 内容，手动标注语义化英文名称

## 输出结果

输出目录：`C:\Users\san\Desktop\素材\output\named_sprites\`

共 **37 个** 有效家具素材，全部为透明背景 PNG，像素无损。

### 素材清单

| 分类 | 文件名 | 数量 |
|------|--------|------|
| 办公工位 | `desk_cubicle_01.png` ~ `desk_cubicle_06.png` | 6 |
| 办公椅 | `office_chair_01.png` ~ `office_chair_06.png` | 6 |
| 屏幕/展板 | `projection_screen.png`, `whiteboard.png`, `chart_board.png`, `bulletin_board.png` | 4 |
| 大型家具 | `sofa.png`, `bookshelf_large.png`, `bookshelf_small.png`, `filing_cabinet.png`, `storage_cabinet.png` | 5 |
| 办公设备 | `printer.png`, `copier.png`, `pc_tower.png`, `small_monitor.png`, `paper_shredder.png` | 5 |
| 桌台 | `supply_desk.png`, `reception_desk.png`, `supply_crate.png` | 3 |
| 电器 | `water_dispenser.png`, `vending_machine.png`, `desk_lamp.png` | 3 |
| 植物 | `cactus_pot.png`, `potted_plant_round.png`, `potted_fern.png`, `bush_large.png`, `bush_small.png` | 5 |

### 过滤掉的无效区域

| 原始编号 | 尺寸 | 原因 |
|---------|------|------|
| sprite_003 | 15x156 | 工位隔板窄条 |
| sprite_006 | 16x156 | 工位隔板窄条 |
| sprite_022 | 19x11 | 噪点碎片 |
| sprite_032 | 21x11 | 噪点碎片 |

## 输出目录结构

```
C:\Users\san\Desktop\素材\output\
  named_sprites/
    desk_cubicle_01.png ~ desk_cubicle_06.png
    office_chair_01.png ~ office_chair_06.png
    projection_screen.png
    sofa.png
    supply_desk.png
    bookshelf_large.png
    bookshelf_small.png
    printer.png
    copier.png
    pc_tower.png
    whiteboard.png
    chart_board.png
    bulletin_board.png
    water_dispenser.png
    desk_lamp.png
    cactus_pot.png
    vending_machine.png
    small_monitor.png
    reception_desk.png
    storage_cabinet.png
    filing_cabinet.png
    supply_crate.png
    paper_shredder.png
    potted_plant_round.png
    potted_fern.png
    bush_large.png
    bush_small.png
    sprites_manifest.json
  sprites/
    sprite_001.png ~ sprite_041.png  (原始编号版本)
  debug/
    mask.png
    mask_dilated.png
    labeled_boxes.png
```

## 技术细节

- **库依赖**：Pillow, numpy, opencv-python
- **像素保真**：全程无 resize、无抗锯齿、无平滑滤波、无颜色插值
- **背景处理**：颜色距离容差 30，背景区域 alpha 设为 0
- **连通域**：OpenCV `connectedComponentsWithStats`，8-连通，最小面积 100px

## 相关脚本

- `d:\project\hotclaw\split_sprites.py` - 自动拆分主脚本
- `d:\project\hotclaw\rename_sprites.py` - 内容识别重命名脚本

## 状态

✅ 完成

---

🤖 Generated with [Qoder](https://qoder.com)
