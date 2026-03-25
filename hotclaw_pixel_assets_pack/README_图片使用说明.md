# HotClaw Pixel Asset Pack

这是首版前端原型素材包，目标是让大模型先把页面结构、交互和占位图搭起来。
这些图片不是最终商用美术，而是“前端可运行原型 + 提示词参考图”。

## 文件说明

- 00_hotclaw_homepage_mockup.png  
  完整首页参考图。用于告诉大模型整体布局、房间分区、下方面板结构。

- 01_hotclaw_editorial_room_background.png  
  上半部分主场景背景图。可作为 room background 或 map background。

- 02_hotclaw_agent_idle.png  
  智能体待命状态像素小人。

- 03_hotclaw_agent_work.png  
  智能体工作状态像素小人。

- 04_hotclaw_agent_sync.png  
  智能体同步状态像素小人。

- 05_hotclaw_agent_alert.png  
  智能体报警状态像素小人。

- 06_hotclaw_fx_exclamation.png  
  右键角色后的感叹号反馈图标。建议叠加在角色头顶，0.8~1.2 秒淡出。

- 07_hotclaw_ui_settings_gear.png  
  右键快捷菜单里的设置图标。

- 08_hotclaw_context_menu.png  
  右键角色后的像素风快捷菜单参考图。

- 09_hotclaw_settings_panel_mock.png  
  智能体设置抽屉 / 弹窗的视觉参考图。

## 给大模型的图片使用方式

把这些图片和下面这段提示一起发给大模型：

“请基于我上传的图片实现一个 HotClaw 像素风首页前端。
以 00_hotclaw_homepage_mockup.png 作为整体布局参考，
以 01_hotclaw_editorial_room_background.png 作为主场景背景参考，
以 02~05 四张角色图作为 agent 的不同状态 sprite 占位图，
以 06 作为右键角色时的感叹号反馈，
以 07 和 08 作为右键上下文菜单参考，
以 09 作为智能体详细配置抽屉/弹窗参考。

要求：
1. 页面上半部分是可交互像素编辑部房间，下半部分是日志、状态、访客三个面板；
2. agent 在房间中可移动、可点击、可右击；
3. 右击 agent 时，头顶出现 06 的感叹号反馈，并在角色附近弹出参考 08 的快捷菜单；
4. 点击菜单中的设置按钮后，打开参考 09 的智能体配置面板；
5. 所有图片先作为占位素材使用，组件命名和状态管理要清晰，后续方便替换正式美术；
6. 请优先输出 React 组件结构、数据结构、状态字段设计和首版可运行代码。”

## 推荐前端引用命名

```ts
const assets = {
  homepageMock: "/assets/00_hotclaw_homepage_mockup.png",
  roomBg: "/assets/01_hotclaw_editorial_room_background.png",
  agentIdle: "/assets/02_hotclaw_agent_idle.png",
  agentWork: "/assets/03_hotclaw_agent_work.png",
  agentSync: "/assets/04_hotclaw_agent_sync.png",
  agentAlert: "/assets/05_hotclaw_agent_alert.png",
  fxExclamation: "/assets/06_hotclaw_fx_exclamation.png",
  uiGear: "/assets/07_hotclaw_ui_settings_gear.png",
  contextMenu: "/assets/08_hotclaw_context_menu.png",
  settingsPanelRef: "/assets/09_hotclaw_settings_panel_mock.png",
}
```

## 建议状态字段

```ts
type AgentStatus = "idle" | "work" | "sync" | "alert"

type UIState = {
  selectedAgentId: string | null
  isContextMenuOpen: boolean
  contextMenuPosition: { x: number; y: number } | null
  isSettingsPanelOpen: boolean
  reactionEffect: "exclamation" | null
}
```

## 诚实说明

- 这批图是“像素风原型素材”，适合先跑通产品页面。
- 真正要上线，建议后续再补统一角色动作帧、地面遮挡层、物体碰撞层和正式 UI 规范。