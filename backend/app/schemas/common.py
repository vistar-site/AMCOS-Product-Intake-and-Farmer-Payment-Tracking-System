from pydantic import BaseModel


class Page[T](BaseModel):
    """Standard paginated response: every list endpoint returns this shape."""

    items: list[T]
    total: int
    page: int
    page_size: int
