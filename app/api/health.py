from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    data = request.app.state.data
    if any(not item["exists"] for item in data.values()):
        status = "data_missing"
    elif any("error" in item for item in data.values()):
        status = "data_error"
    else:
        status = "ok"
    return {"status": status, "data": data}
