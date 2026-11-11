from pydantic import BaseModel


class ApiResponse[T](BaseModel):
    code: int = 200
    message: str = "操作成功"
    data: T | None = None


class PageData[T](BaseModel):
    list: list[T]
    total: int
    current: int
    pageSize: int
