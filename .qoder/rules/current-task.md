# 当前任务

## 任务目标

**前端与后端联动开发 - 让 HotClaw 完整可用**

## 当前状态

### 后端 ✅ 已完成
- 6 个 Agent 全链路打通
- API 接口就绪：
  - `POST /api/v1/tasks` - 创建任务
  - `GET /api/v1/tasks/{id}` - 任务详情
  - `GET /api/v1/tasks/{id}/stream` - SSE 实时推送
  - `GET /api/v1/tasks` - 任务列表
- SSE 事件：`node_start`, `node_complete`, `node_error`, `task_complete`, `task_error`

### 前端 ⚠️ 骨架状态
- Next.js 项目结构已建立
- API 客户端 (`@/lib/api.ts`) 已完成
- SSE Hook (`hooks/useTaskSSE.ts`) 已完成
- 任务详情页 (`app/task/[id]/page.tsx`) 已完成
- 首页 (`app/page.tsx`) - 占位页面，需要完善
- 新闻编辑部 (`app/newsroom/`) - 需要检查

## 重要提醒

⚠️ **这是联合开发，不是重构！**

- 前端代码**已经存在**，是之前开发好的
- 不要重写，不要大改现有页面
- 只需要：检查现有功能是否正常 → 修复发现的问题 → 完善缺失部分
- 保持现有代码风格和结构

## 前端待完善清单

### 1. 首页改造 (app/page.tsx)
- 输入框：账号定位描述
- 开始任务按钮
- 实时显示 6 个节点执行状态（SSE）
- 完成后显示结果预览

### 2. 新闻编辑部页面 (app/newsroom/page.tsx)
检查并完善新闻编辑部页面：
- 应该是主要的操作界面
- 需要与后端 API 联动

### 3. 验证前后端连通性
启动前后端，测试完整流程：
```bash
# 终端 1: 启动后端
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# 终端 2: 启动前端
cd frontend
npm run dev
```

### 4. 修复发现的问题
- CORS 配置是否正确
- API 请求是否正常
- SSE 连接是否工作

## 参考文件

### 前端
- `frontend/app/page.tsx` - 首页
- `frontend/app/newsroom/page.tsx` - 新闻编辑部
- `frontend/app/task/[id]/page.tsx` - 任务详情
- `frontend/app/history/page.tsx` - 历史任务
- `frontend/hooks/useTaskSSE.ts` - SSE Hook
- `frontend/lib/api.ts` - API 客户端

### 后端
- `backend/app/api/task_routes.py` - 任务 API
- `backend/app/api/stream_routes.py` - SSE 流
- `backend/app/main.py` - 入口

## 输出要求

1. 检查并完善首页
2. 检查新闻编辑部页面
3. 启动前后端进行联调测试
4. 记录发现的问题并修复
5. 在 RESULT.md 中记录修改内容

## 注意事项

- 前端使用 Next.js App Router
- API 路径前缀 `/api/v1`
- SSE 连接路径 `/api/v1/tasks/{id}/stream`
- 需要处理 CORS 问题
