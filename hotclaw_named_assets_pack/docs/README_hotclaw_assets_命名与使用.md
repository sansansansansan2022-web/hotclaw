# HotClaw 像素资源命名与使用说明

## 1. 资源包定位
这份资源包不是最终商用美术，而是**HotClaw 像素编辑部前端的结构化原型资源**。  
已经按你的项目语义重新命名，方便直接交给大模型或前端代码使用。

## 2. 命名后的资源结构

### 场景
- `scenes/scene_hotclaw_editorial_floor_large.png`
  - 大尺寸完整场景图
  - 适合做首页主舞台、宣传图、可视化概念底图
- `scenes/scene_hotclaw_editorial_floor_base.png`
  - 小尺寸基础场景
  - 适合切图参考、碰撞区规划、前端缩放布局参考
- `scenes/tileset_hotclaw_office_props.png`
  - 办公室道具 tileset / sprite sheet
  - 用于拆出椅子、沙发、书柜、服务器、门、植物、咖啡机等独立元素

### 五个智能体
以下五个人物是我基于你当前项目目标做的工作流映射。  
如果后续你的 agent 设计变化，只需要保留文件名规范，替换图即可。

1. `agents/agent_01_dispatcher_orchestrator.png`
   - 中文建议名：调度编排智能体
   - 负责：统筹流程、分配任务、触发 agent 协作、管理状态
   - 页面位置建议：中央区域 / 总控区 / 大屏附近

2. `agents/agent_02_topic_researcher.png`
   - 中文建议名：选题检索智能体
   - 负责：热点发现、选题生成、资料检索、知识整理
   - 页面位置建议：资料区 / 白板区 / 书架附近

3. `agents/agent_03_tool_operator.png`
   - 中文建议名：工具调用智能体
   - 负责：调用 API、技能编排、执行 workflow、连接外部工具
   - 页面位置建议：服务器区 / 机柜区 / 接口区

4. `agents/agent_04_writer_editor.png`
   - 中文建议名：写作编辑智能体
   - 负责：文章草稿生成、润色、重写、结构整理
   - 页面位置建议：工位区 / 电脑桌前

5. `agents/agent_05_publish_operator.png`
   - 中文建议名：发布运营智能体
   - 负责：审核通过后的发布、账号状态同步、数据回收、运营反馈
   - 页面位置建议：门口接待区 / 发布面板 / 数据看板附近

## 3. 推荐前端使用方式

### 页面分层
推荐按 4 层来组织前端：

1. `background layer`
   - 使用 `scene_hotclaw_editorial_floor_large.png` 作为整体背景参考
   - 首版也可以直接平铺整图

2. `props layer`
   - 依据 `tileset_hotclaw_office_props.png` 拆出道具
   - 后续可单独做可点击区域：
     - 服务器区
     - 沙发讨论区
     - 书架资料区
     - 工位写作区
     - 门口访客区

3. `agents layer`
   - 使用 `agents/` 下的五个人物作为五个默认 agent
   - 每个 agent 绑定一个状态字段：
     - `idle`
     - `working`
     - `syncing`
     - `alert`

4. `ui layer`
   - 覆盖业务面板：
     - 系统日志
     - agent 状态
     - 访客/任务列表
     - 智能体设置抽屉

## 4. 右键交互怎么绑定
你前面说的需求可以这样落到资源上：

- 右键某个角色
  - 角色头顶出现感叹号反馈（后续可单独补一个 `fx_exclamation.png`）
  - 在角色旁弹出上下文菜单
  - 菜单中显示设置按钮
  - 点击后打开该 agent 的详细配置抽屉

### 角色与业务绑定建议
- `agent_01_dispatcher_orchestrator`  
  右键后打开：全局编排、流程开关、审批模式

- `agent_02_topic_researcher`  
  右键后打开：热点源、检索源、知识库配置

- `agent_03_tool_operator`  
  右键后打开：API key、tool 列表、skill 路由、模型接口

- `agent_04_writer_editor`  
  右键后打开：prompt、风格模板、篇幅策略、重写模式

- `agent_05_publish_operator`  
  右键后打开：发布目标、账号映射、发布策略、数据回流

## 5. 给大模型的资源使用提示词
把这整个资源包上传给大模型后，可以直接配下面这段：

```text
请基于我上传的 HotClaw 像素资源包实现一个 AI 编辑部前端页面。

资源使用规则：
- scenes/scene_hotclaw_editorial_floor_large.png：整体页面主场景参考
- scenes/scene_hotclaw_editorial_floor_base.png：基础比例和房间布局参考
- scenes/tileset_hotclaw_office_props.png：拆分家具、服务器、书柜、植物、沙发、门、工位等元素
- agents/agent_01_dispatcher_orchestrator.png：调度编排智能体
- agents/agent_02_topic_researcher.png：选题检索智能体
- agents/agent_03_tool_operator.png：工具调用智能体
- agents/agent_04_writer_editor.png：写作编辑智能体
- agents/agent_05_publish_operator.png：发布运营智能体

实现要求：
1. 五个人物分别对应五个智能体；
2. 页面是俯视角像素编辑部，不是游戏战斗场景；
3. 智能体可移动、可点击、可右键；
4. 右键角色时要有感叹号反馈，并弹出快捷菜单；
5. 点击设置图标后打开该智能体的详细配置面板；
6. 配置项包括名称、职责、模型、prompt、skills、tools、输入输出、状态和审批方式；
7. 页面下方保留日志区、状态区、访客/任务区；
8. 请优先输出组件结构、状态设计、交互流和首版可运行代码。
```

## 6. 建议的代码命名
建议前端直接沿用这些 key：

- `dispatcherOrchestrator`
- `topicResearcher`
- `toolOperator`
- `writerEditor`
- `publishOperator`

## 7. 我对这份映射的判断
这是**基于你当前项目上下文的合理工程化命名**，优点是前端、产品、代码、prompt 都能统一。  
但它不是你项目唯一正确答案。  
如果你后续把 agent 改成“审核智能体 / 排版智能体 / 数据分析智能体”，只需要沿用同样目录结构替换文件即可。
