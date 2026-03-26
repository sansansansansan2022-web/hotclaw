我在 Next.js (App Router + TypeScript) 项目中，
需要实现一个像素风 AI 编辑部场景，使用真实角色精灵图素材。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【素材说明】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
共 6 张 sprite sheet，命名为 char_1.png ～ char_6.png
统一放在 /public/sprites/ 目录下，通过 /sprites/char_1.png 访问

每张图规格完全相同：
- 布局：3行 × 7列 = 21帧，背景透明
- 第 0 行（row=0）：正面朝下，7帧行走循环
- 第 1 行（row=1）：背面朝上，7帧行走循环
- 第 2 行（row=2）：侧面行走，7帧循环

帧尺寸计算（不要硬编码，必须动态读取）：
  img.onload = () => {
    frameW = img.naturalWidth / 7
    frameH = img.naturalHeight / 3
  }

Canvas 裁切方式：
  ctx.drawImage(
    img,
    frameIndex * frameW,   // sx：第几帧
    rowIndex * frameH,     // sy：第几行（方向）
    frameW, frameH,        // 源尺寸
    destX - frameW,        // dx：以角色中心为锚点
    destY - frameH,        // dy
    frameW * 2, frameH * 2 // 放大2倍显示
  )

行走方向与行的对应关系：
  moving down  → row 0
  moving up    → row 1
  moving left  → row 2（水平翻转：ctx.scale(-1,1)）
  moving right → row 2

静止时：使用当前方向的 row，frameIndex 固定为 0

动画帧率：每 150ms 切换一帧（frameIndex 0→6 循环）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【6个角色与智能体绑定】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
const AGENTS = [
  { id:1, name:"飞书写作助手",    sprite:"/sprites/char_1.png", status:"working", floor:2, deskCol:0 },
  { id:2, name:"Discord编辑专家", sprite:"/sprites/char_2.png", status:"sync",    floor:2, deskCol:1 },
  { id:3, name:"QQ校对大师",      sprite:"/sprites/char_3.png", status:"idle",    floor:2, deskCol:2 },
  { id:4, name:"微信设计专员",    sprite:"/sprites/char_4.png", status:"working", floor:3, deskCol:0 },
  { id:5, name:"Telegram调研师",  sprite:"/sprites/char_5.png", status:"offline", floor:3, deskCol:1 },
  { id:6, name:"Github开发者",    sprite:"/sprites/char_6.png", status:"sync",    floor:3, deskCol:2 },
]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【场景结构】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Canvas 尺寸：1100 × 580px
imageSmoothingEnabled = false（保持像素锐利，必须设置）

纵向分 4 层：
  [天空层]   高度 120px：蓝色渐变，白色像素云朵从右向左漂移
  [1楼大厅]  高度 140px：自动门居中 + 绿植 + 橙色沙发 + 零食机
  [2楼办公]  高度 160px：蓝色像素砖墙 + 3个工位（左中右）
  [3楼办公]  高度 160px：蓝色像素砖墙 + 3个工位（左中右）

像素砖墙画法（Canvas 手绘，不用图片）：
  - 底色：#5b8dd9
  - 砖块：16×8px，颜色 #4a7bc8，错缝排列
  - 砖缝：1px，颜色 #3a6ab8

工位格子（每个 160×120px，Canvas 手绘）：
  - 桌面：浅棕色 #c8a882
  - 显示器：深灰色外框 + 蓝色屏幕
  - 椅子：橙色像素风
  - working 状态：显示器屏幕闪绿色光晕（sin 波动透明度）
  - offline 状态：屏幕变黑，整个角色透明度 0.4

工位上方标签（Canvas fillText）：
  - 角色名：白色，像素字体（font: "bold 11px monospace"）
  - 状态标签：
      working → 绿底 #22c55e
      sync    → 黄底 #eab308
      idle    → 灰底 #6b7280
      offline → 红底 #ef4444

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【角色行为逻辑】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
每个角色维护以下状态：
  {
    x, y,           // 当前像素坐标
    targetX, targetY, // 目标坐标
    direction,      // "down"|"up"|"left"|"right"
    frameIndex,     // 0-6
    lastFrameTime,  // 上次切帧时间戳
    isMoving,       // boolean
    agentStatus,    // working/sync/idle/offline
  }

行为规则：
  working → 角色坐在工位，播放 row2 动画，不移动
  idle    → 站在工位旁，静止帧；每隔 8~15秒（随机）
              走到1楼茶水间，停留2秒，再走回来
  sync    → 在自己工位和相邻工位之间来回走动
              移动时头顶显示飞行信封图标（🖂 用 Canvas 手绘）
  offline → 透明度 0.4，完全静止，不响应任何行为

移动实现：
  使用线性插值 lerp(current, target, 0.05)
  到达目标点判定：Math.abs(x - targetX) < 2

水平翻转（向左走时）：
  ctx.save()
  ctx.translate(x + frameW, y)
  ctx.scale(-1, 1)
  ctx.drawImage(img, ...)
  ctx.restore()

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【动态效果】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- 云朵：3朵，x 坐标每帧 -0.3px，超出左边界后从右侧重置
- 时钟：右上角显示真实时间，font "bold 14px monospace"，红色 LED 风格
- 楼层分隔线：2px，颜色 #2a3f6f，带细节线条
- 任务完成特效：角色头顶出现 ★，向上飘动+淡出，持续 60帧
- FPS 计数器：左上角，绿色，"FPS: XX"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【Next.js 实现规范】
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 组件文件：components/NewsroomScene.tsx
2. 顶部必须加 'use client'
3. 用 useRef<HTMLCanvasElement> 获取 Canvas
4. 用 useEffect 启动主循环，return 时清除 cancelAnimationFrame
5. 图片预加载：
     const loadSprite = (src: string): Promise<HTMLImageElement> =>
       new Promise(resolve => {
         const img = new Image()
         img.onload = () => resolve(img)
         img.src = src
       })
     Promise.all(AGENTS.map(a => loadSprite(a.sprite)))
       .then(images => { /* 启动主循环 */ })
6. 代码分层：
     - drawBackground()   绘制天空/砖墙/家具
     - drawAgents()       绘制所有角色
     - updateAgents()     更新位置和动画帧
     - drawUI()           绘制时钟/FPS/标签
7. 不使用任何 Canvas 相关的 npm 包

素材在D:\project\hotclaw\OpenClaw-bot-review-main\public\assets\pixel-office\characters
"先实现静态场景（只画背景和角色静止帧），确认位置正确后，再加行走动画和行为逻辑。"