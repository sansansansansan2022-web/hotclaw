"""Common response schemas used across all API endpoints."""

from typing import Any
from pydantic import BaseModel


class ApiResponse(BaseModel):
    """Unified API response wrapper per NOTICE.md section 8.1."""
    code: int = 0
    message: str = "ok"
    data: Any = None


class ApiErrorResponse(BaseModel):
    """Unified API error response."""
    code: int
    message: str
    data: None = None
    details: dict | None = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int
    page_size: int
    total: int
