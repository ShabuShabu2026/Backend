from fastapi import APIRouter, HTTPException

router = APIRouter()


@router.get("/health", tags=["health"])
def health() -> dict:
    raise HTTPException(status_code=503, detail="Data is still loading.")
