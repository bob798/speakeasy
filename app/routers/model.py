"""运行时模型热切换 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import runtime_model

router = APIRouter(prefix="/model", tags=["model"])


class SwitchRequest(BaseModel):
    model_config = {"protected_namespaces": ()}
    model_name: str


@router.get("")
def get_model_status():
    """查询当前模型状态"""
    return runtime_model.status()


@router.post("/switch")
def switch_model(req: SwitchRequest):
    """热切换活跃模型（无需重启）"""
    try:
        new_model = runtime_model.switch(req.model_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"switched_to": new_model, **runtime_model.status()}
