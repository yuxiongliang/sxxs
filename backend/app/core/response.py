from typing import Any


def ok(data: Any = None, message: str = "操作成功") -> dict[str, Any]:
    return {"code": 200, "message": message, "data": data}


def page_data(items: list[Any], total: int, current: int, page_size: int) -> dict[str, Any]:
    return {
        "list": items,
        "total": total,
        "current": current,
        "pageSize": page_size,
    }
