# HotClaw 账号接入操作手册 V1

适用范围：
当前本地运行环境下，通过 `http://localhost:3000/accounts/new` 完成公众号账号接入，并在 onboarding 内完成 AppID / AppSecret 连接测试。

## 目标

用最短路径完成以下动作：

1. 选择账号接入路径
2. 填写基础账号画像
3. 在 onboarding 内完成公众号真实接入
4. 运行连接测试
5. 进入账号工作台后继续配置和运营

## 当前环境前提

- 前端入口：`http://localhost:3000/accounts/new`
- 当前前端运行时注入：`window.__HOTCLAW_API_ORIGIN__ = "http://localhost:8000"`
- 当前后端健康检查：`http://localhost:8000/api/v1/health`
- 当前页面内置公众号测试接口：
  - `POST /api/v1/wechat/test-connection`

## 保留的现场快照

本轮操作快照已保存在：

- [01-choose-account-path.yml](/D:/project/hotclaw/output/playwright/onboarding-manual-v1/01-choose-account-path.yml)
- [02-new-account-basics.yml](/D:/project/hotclaw/output/playwright/onboarding-manual-v1/02-new-account-basics.yml)
- [03-wechat-connect-form.yml](/D:/project/hotclaw/output/playwright/onboarding-manual-v1/03-wechat-connect-form.yml)
- [04-wechat-test-success.yml](/D:/project/hotclaw/output/playwright/onboarding-manual-v1/04-wechat-test-success.yml)
- [console.log](/D:/project/hotclaw/output/playwright/onboarding-manual-v1/console.log)

这些文件用于回看页面结构、控件名称和当前联调结果。

## 标准操作流程

### 1. 打开接入页

访问：

- `http://localhost:3000/accounts/new`

确认页面标题为 `Connect an Official Account`。

### 2. 选择接入路径

如果是新号，点击：

- `Start New Account Setup`

如果是老号，点击：

- `Analyze Existing Account`

本手册当前记录的是新号路径。

### 3. 填基础账号信息

新号路径下需要填写：

- `Account Name`
- `Content Lane / Positioning`
- `Target Audience`
- `Preferred Tone`
- `Initial Operating Mode`

建议首发采用保守模式：

- `manual`

不要默认开启自动运行或自动发布。

### 4. 进入公众号接入步骤

点击：

- `Continue to WeChat Connection`

在 WeChat 步骤中，优先选择：

- `Connect Real Official Account`

不要把真实公众号接入拖到后置设置页。

### 5. 填写公众号接入字段

本步骤支持：

- `AppID`
- `AppSecret`
- `Default Author`
- `Default Thumb Media ID`
- `Enable Comments`
- `Only Fans Can Comment`

最小可用接入通常至少需要：

- `AppID`
- `AppSecret`
- `Default Author`

### 6. 运行连接测试

点击：

- `Test Connection`

当前联调结果中，页面在测试成功后会在表单旁显示：

- `ok`

并且浏览器网络中会出现：

- `POST http://localhost:8000/api/v1/wechat/test-connection => 200 OK`

### 7. 创建账号

连接测试通过后，点击：

- `Create Account`

预期链路：

1. 创建账号
2. 写入账号级 wechat config
3. 执行账号级连接测试
4. 跳转到账号工作台

## 成功判定

满足以下几点即可认为 onboarding 内公众号接入已跑通：

1. 页面运行时 API origin 指向 `http://localhost:8000`
2. `Test Connection` 返回成功
3. 浏览器 network 中能看到 `/api/v1/wechat/test-connection` 的 `200 OK`
4. 后续创建账号成功
5. 账号详情页或工作台显示已接入真实公众号，而不是仅内容模式

## 常见排障顺序

### 情况 1：页面能打开，但 API 不通

先检查：

- `window.__HOTCLAW_API_ORIGIN__`
- `http://localhost:3000/api/v1/health`
- `http://localhost:8000/api/v1/health`

### 情况 2：3000 页面能开，但后端连不上

先恢复 `8000`，不要先改 onboarding 业务代码。

### 情况 3：Test Connection 失败

优先检查：

- AppID / AppSecret 是否填写正确
- 当前后端是否真的可达
- 浏览器 network 里请求是否命中 `8000`

### 情况 4：账号创建成功但仍显示内容模式

重点核查：

- wechat config 是否写入成功
- account-scoped test 是否成功
- 工作台/账号详情页是否正确读取公众号连接状态

## 当前这轮已确认的联调信号

- 页面注入 origin 已正确指向 `http://localhost:8000`
- 页面内 `Test Connection` 已返回成功态 `ok`
- 浏览器 network 已记录：
  - `POST http://localhost:8000/api/v1/wechat/test-connection => 200 OK`

## 下一步建议

基于这份手册继续执行时，优先完成：

1. 用真实公众号资料跑完整个 `Create Account`
2. 创建完成后打开账号详情页
3. 验证 wechat config 已写入
4. 验证工作台显示已接入真实公众号
