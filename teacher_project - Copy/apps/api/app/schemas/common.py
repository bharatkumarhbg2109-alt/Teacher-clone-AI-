from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    per_page: int
    has_more: bool


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: dict | None = None


class SuccessResponse(BaseModel):
    success: bool = True
    message: str = "ok"
