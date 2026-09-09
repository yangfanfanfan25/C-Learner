"""Schemas for first-run LLM setup and connection checks."""

from pydantic import BaseModel, Field


class ModelOption(BaseModel):
    id: str
    label: str
    base_url: str
    provider: str = "openai"


class SetupStatus(BaseModel):
    configured: bool
    connected: bool
    model_name: str
    base_url: str
    api_key_configured: bool
    message: str


class SetupConfigRequest(BaseModel):
    api_key: str = Field(min_length=1, max_length=512)
    model_name: str = Field(default="deepseek-chat", min_length=1, max_length=200)
    base_url: str = Field(default="https://api.deepseek.com/v1", min_length=1, max_length=500)
    provider: str = Field(default="openai", min_length=1, max_length=100)


class SetupConfigResponse(BaseModel):
    status: SetupStatus
    models: list[ModelOption]
