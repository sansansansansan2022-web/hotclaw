"""Trace ID generation and propagation."""

from contextvars import ContextVar
from nanoid import generate as nanoid

_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")
_task_id_var: ContextVar[str] = ContextVar("task_id", default="")


def generate_trace_id() -> str:
    """Generate a new trace ID. Format: tr_{nanoid(12)}"""
    return f"tr_{nanoid(size=12)}"


def generate_task_id() -> str:
    """Generate a new task ID. Format: task_{nanoid(12)}"""
    return f"task_{nanoid(size=12)}"


def get_trace_id() -> str:
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def get_task_id() -> str:
    return _task_id_var.get()


def set_task_id(task_id: str) -> None:
    _task_id_var.set(task_id)
