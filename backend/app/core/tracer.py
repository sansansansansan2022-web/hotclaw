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


def generate_account_id() -> str:
    """Generate a new account ID. Format: acct_{nanoid(12)}"""
    return f"acct_{nanoid(size=12)}"


def generate_analysis_snapshot_id() -> str:
    """Generate a new account analysis snapshot ID. Format: ins_{nanoid(12)}"""
    return f"ins_{nanoid(size=12)}"


def generate_recommendation_id() -> str:
    """Generate a new recommendation item ID. Format: rec_{nanoid(12)}"""
    return f"rec_{nanoid(size=12)}"


def generate_selection_session_id() -> str:
    """Generate a new compose selection session ID. Format: sel_{nanoid(12)}"""
    return f"sel_{nanoid(size=12)}"


def generate_workspace_id() -> str:
    """Generate a new workspace-like correlation ID. Format: ws_{nanoid(12)}"""
    return f"ws_{nanoid(size=12)}"


def get_trace_id() -> str:
    return _trace_id_var.get()


def set_trace_id(trace_id: str) -> None:
    _trace_id_var.set(trace_id)


def get_task_id() -> str:
    return _task_id_var.get()


def set_task_id(task_id: str) -> None:
    _task_id_var.set(task_id)
