"""First-run setup endpoints for local LLM configuration."""

from fastapi import APIRouter

from app.infrastructure.setup_config import MODEL_OPTIONS, check_connection, current_status, write_env_config
from app.schemas.base import APIResponse
from app.schemas.setup import ModelOption, SetupConfigRequest, SetupConfigResponse, SetupStatus

router = APIRouter(prefix="/setup", tags=["Setup"])


@router.get("/status", response_model=APIResponse[SetupStatus])
async def get_setup_status() -> APIResponse[SetupStatus]:
    status = current_status()
    if status.configured:
        connected, message = await check_connection()
        status = current_status(connected, message)
    return APIResponse(data=status)


@router.post("/config", response_model=APIResponse[SetupConfigResponse])
async def save_setup_config(body: SetupConfigRequest) -> APIResponse[SetupConfigResponse]:
    write_env_config(body)
    connected, message = await check_connection()
    status = current_status(connected, message)
    return APIResponse(data=SetupConfigResponse(status=status, models=MODEL_OPTIONS))


@router.get("/models", response_model=APIResponse[list[ModelOption]])
async def list_models() -> APIResponse[list[ModelOption]]:
    return APIResponse(data=MODEL_OPTIONS)
