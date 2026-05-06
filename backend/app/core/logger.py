"""
Structured logging using structlog.

【结构化日志系统】
使用 structlog 库实现结构化日志，输出格式为 JSON，
便于 ELK/Splunk 等日志收集系统解析和检索。

面试点：
- structlog vs 标准 logging 的区别
- 链式处理器 (processors) 的作用
- JSON 格式日志的优势
"""

import logging
import structlog
from app.core.config import settings


def setup_logging() -> None:
    """
    Configure structured logging for the application.

    【日志系统初始化】
    在 FastAPI 应用启动时调用一次，配置全局日志处理器。

    structlog 处理器链（按顺序执行）：
    1. merge_contextvars: 合并上下文变量（如 trace_id）
    2. filter_by_level: 按日志级别过滤
    3. add_logger_name: 添加 logger 名称
    4. add_log_level: 添加日志级别
    5. TimeStamper: 添加 ISO 格式时间戳
    6. StackInfoRenderer: 捕获堆栈信息
    7. format_exc_info: 格式化异常信息
    8. UnicodeDecoder: 解码 Unicode 字符
    9. JSONRenderer: 输出 JSON 格式

    【面试点】处理器链的顺序很重要！
    例如 TimeStamper 必须在 JSONRenderer 之前，
    才能把时间戳注入到 JSON 对象中。
    """
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    structlog.configure(
        processors=[
            # 1. 合并上下文变量（如 trace_id 请求追踪）
            structlog.contextvars.merge_contextvars,
            # 2. 根据 logger 名称过滤日志级别
            structlog.stdlib.filter_by_level,
            # 3. 自动添加 logger 名称字段
            structlog.stdlib.add_logger_name,
            # 4. 自动添加日志级别字段（INFO/WARNING/ERROR）
            structlog.stdlib.add_log_level,
            # 5. 添加 ISO 格式时间戳
            structlog.processors.TimeStamper(fmt="iso"),
            # 6. 在异常时添加堆栈信息
            structlog.processors.StackInfoRenderer(),
            # 7. 将异常信息格式化为可读文本
            structlog.processors.format_exc_info,
            # 8. 解码 Unicode 避免乱码
            structlog.processors.UnicodeDecoder(),
            # 9. 最终输出 JSON 格式（便于日志收集系统解析）
            structlog.processors.JSONRenderer(),
        ],
        # wrapper_class: 包装后的 logger 类型
        wrapper_class=structlog.stdlib.BoundLogger,
        # context_class: 日志上下文的类型
        context_class=dict,
        # logger_factory: logger 实例工厂
        logger_factory=structlog.stdlib.LoggerFactory(),
        # cache_logger_on_first_use: 首次使用后缓存 logger 实例
        cache_logger_on_first_use=True,
    )

    # 配置标准库的 basicConfig，接收 structlog 处理器输出的消息
    logging.basicConfig(format="%(message)s", level=log_level)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    【获取日志实例】
    在任意模块中调用此函数获取 logger，无需重复配置。

    Args:
        name: logger 名称，通常传入 __name__（模块路径）

    Returns:
        结构化日志实例，支持 .info() / .warning() / .error() 等方法

    使用示例：
        logger = get_logger(__name__)
        logger.info("task_created", task_id="xxx", user_id=123)
        # 输出: {"event": "task_created", "task_id": "xxx", "user_id": 123, "level": "info", "timestamp": "..."}
    """
    return structlog.get_logger(name)
