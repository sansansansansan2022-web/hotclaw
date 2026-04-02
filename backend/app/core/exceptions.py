"""
Unified exception hierarchy for HotClaw.

【统一异常体系】
所有自定义异常都继承自 HotClawError 基类，
通过错误码（code）实现分类，便于前端和日志系统处理。

错误码设计原则：
- code // 1000 = HTTP 状态码（1xxx→400, 2xxx→409, 3xxx→502, 4xxx→500, 5xxx→500）
- code % 1000 = 具体错误序号

面试点：
- 自定义异常体系设计
- 错误码分类的工程价值
- 异常作为错误处理的"类型系统"
"""


class HotClawError(Exception):
    """
    Base exception for all HotClaw errors.

    【异常基类】
    所有业务异常的父类，统一存储 code、message、details 三个字段。

    Attributes:
        code: 错误码，用于分类和前端判断
        message: 面向用户的错误描述
        details: 详细错误信息（字典格式，便于结构化处理）
    """

    def __init__(self, code: int, message: str, details: dict | None = None):
        self.code = code          # 错误码，如 1001
        self.message = message    # 用户可读的错误信息
        self.details = details or {}  # 额外上下文数据
        super().__init__(message)     # 让 Exception 能正常打印 message


# ============================================================================
# 1xxx: 用户输入错误（HTTP 400 Bad Request）
# ============================================================================


class ValidationError(HotClawError):
    """
    Request parameter validation failed.

    【输入验证错误】
    当请求参数不符合验证规则时抛出。
    例如：positioning 长度不足、格式错误等。
    """

    def __init__(self, message: str = "validation error", details: dict | None = None):
        # 1001: 用户输入类错误的起始码
        super().__init__(code=1001, message=message, details=details)


class TaskNotFoundError(HotClawError):
    """
    Task does not exist.

    【任务不存在错误】
    当根据 task_id 查询任务失败时抛出。
    前端收到 404 状态码，可引导用户检查 task_id。
    """

    def __init__(self, task_id: str):
        # 1002: 特定资源的 404 错误
        super().__init__(code=1002, message=f"task not found: {task_id}")


class AgentNotFoundError(HotClawError):
    """Agent does not exist."""

    def __init__(self, agent_id: str):
        super().__init__(code=1003, message=f"agent not found: {agent_id}")


class SkillNotFoundError(HotClawError):
    """Skill does not exist."""

    def __init__(self, skill_id: str):
        super().__init__(code=1004, message=f"skill not found: {skill_id}")


# ============================================================================
# 2xxx: 冲突错误（HTTP 409 Conflict）
# ============================================================================


class TaskAlreadyRunningError(HotClawError):
    """
    Task is already running.

    【任务重复执行错误】
    防止同一个任务被多次触发。
    当前端点击"启动"按钮时，如果任务已在运行，抛出此错误。
    """

    def __init__(self, task_id: str):
        # 2001: 资源状态冲突
        super().__init__(code=2001, message=f"task already running: {task_id}")


class WorkflowNotFoundError(HotClawError):
    """Workflow definition does not exist."""

    def __init__(self, workflow_id: str):
        super().__init__(code=2002, message=f"workflow not found: {workflow_id}")


# ============================================================================
# 3xxx: 外部/执行错误（HTTP 502 Bad Gateway）
# ============================================================================


class LLMCallError(HotClawError):
    """
    LLM API call failed.

    【LLM 调用失败】
    当 LLM API 返回错误、超时或无法连接时抛出。
    常见原因：API Key 错误、余额不足、网络问题、模型不可用。
    """

    def __init__(self, message: str = "LLM call failed", details: dict | None = None):
        # 3001: 外部服务调用失败
        super().__init__(code=3001, message=message, details=details)


class ExternalAPIError(HotClawError):
    """External API call failed.

    【外部 API 调用失败】
    非 LLM 的外部服务调用失败，如搜索引擎抓取失败。
    """

    def __init__(self, message: str = "external API call failed", details: dict | None = None):
        super().__init__(code=3002, message=message, details=details)


class AgentTimeoutError(HotClawError):
    """
    Agent execution timed out.

    【智能体执行超时】
    当单个智能体执行时间超过 agent_timeout 配置时抛出。
    触发编排引擎的降级/中断策略。
    """

    def __init__(self, agent_id: str):
        # 3003: 超时错误（特殊标记，便于监控告警）
        super().__init__(code=3003, message=f"agent execution timed out: {agent_id}")


class AgentExecutionError(HotClawError):
    """
    Agent execution failed.

    【智能体执行失败】
    智能体运行过程中发生的逻辑错误，如 LLM 输出格式不符合预期。
    与 AgentTimeoutError 的区别：超时是"做不完"，这是"做错了"。
    """

    def __init__(self, agent_id: str, message: str, details: dict | None = None):
        super().__init__(code=3004, message=f"agent {agent_id} failed: {message}", details=details)


class SkillExecutionError(HotClawError):
    """Skill execution failed."""

    def __init__(self, skill_id: str, message: str, details: dict | None = None):
        super().__init__(code=3005, message=f"skill {skill_id} failed: {message}", details=details)


# ============================================================================
# 4xxx: 配置错误（HTTP 500 Internal Server Error）
# ============================================================================


class ConfigError(HotClawError):
    """
    Configuration validation failed.

    【配置错误】
    应用启动时或运行中发现配置不合法。
    如：缺少必需的 API Key、配置值超出范围。
    """

    def __init__(self, message: str = "config error", details: dict | None = None):
        # 4001: 配置类错误
        super().__init__(code=4001, message=message, details=details)


class ManifestError(HotClawError):
    """Manifest file format error.

    【清单文件格式错误】
    Manifest 是描述 Agent/Skill 配置的文件，格式错误时抛出。
    """

    def __init__(self, message: str = "manifest error", details: dict | None = None):
        super().__init__(code=4002, message=message, details=details)


# ============================================================================
# 5xxx: 系统错误（HTTP 500 Internal Server Error）
# ============================================================================


class InternalError(HotClawError):
    """
    Internal server error.

    【系统内部错误】
    捕获所有未预期的异常，作为最后一道防线。
    收到此错误说明存在代码 bug 或未处理的边界情况。
    """

    def __init__(self, message: str = "internal server error", details: dict | None = None):
        # 5000: 系统错误（直接映射 HTTP 500）
        super().__init__(code=5000, message=message, details=details)
