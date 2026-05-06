"""LLM Provider 配置 API 路由。

提供 LLM API 配置的 CRUD 操作，支持用户自定义配置各种 LLM Provider。
"""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.tables import LLMProviderModel
from app.core.logger import get_logger

router = APIRouter(prefix="/api/v1/llm-providers", tags=["LLM Provider"])
logger = get_logger(__name__)


# =============================================================================
# Schema 定义
# =============================================================================

class LLMProviderBase(BaseModel):
    """LLM Provider 基础字段"""
    provider_id: str = Field(..., description="Provider ID: openai, dashscope, deepseek, zhipu, ollama, custom")
    name: str = Field(..., description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    api_key: Optional[str] = Field(None, description="API Key")
    base_url: Optional[str] = Field(None, description="API Base URL")
    default_model: Optional[str] = Field(None, description="默认模型")
    supported_models: Optional[list[str]] = Field(None, description="支持的模型列表")
    is_enabled: bool = Field(False, description="是否启用")
    is_default: bool = Field(False, description="是否为默认 Provider")
    timeout: int = Field(60, description="超时时间（秒）", ge=5, le=300)
    extra_config: Optional[dict] = Field(None, description="额外配置")


class LLMProviderCreate(LLMProviderBase):
    """创建 LLM Provider"""
    pass


class LLMProviderUpdate(BaseModel):
    """更新 LLM Provider"""
    name: Optional[str] = Field(None, description="显示名称")
    description: Optional[str] = Field(None, description="描述")
    api_key: Optional[str] = Field(None, description="API Key")
    base_url: Optional[str] = Field(None, description="API Base URL")
    default_model: Optional[str] = Field(None, description="默认模型")
    supported_models: Optional[list[str]] = Field(None, description="支持的模型列表")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    is_default: Optional[bool] = Field(None, description="是否为默认 Provider")
    timeout: Optional[int] = Field(None, description="超时时间（秒）", ge=5, le=300)
    extra_config: Optional[dict] = Field(None, description="额外配置")
    status: Optional[str] = Field(None, description="状态: active, inactive")


class LLMProviderResponse(LLMProviderBase):
    """LLM Provider 响应"""
    status: str
    test_status: Optional[str] = None
    test_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LLMProviderTestRequest(BaseModel):
    """测试请求"""
    provider_id: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None


class LLMProviderTestResponse(BaseModel):
    """测试响应"""
    success: bool
    latency_ms: Optional[float] = None
    response_preview: Optional[str] = None
    error_message: Optional[str] = None


# =============================================================================
# 路由实现
# =============================================================================

@router.get("", response_model=list[LLMProviderResponse])
async def list_providers(db: AsyncSession = Depends(get_db)):
    """获取所有 LLM Provider 配置"""
    result = await db.execute(select(LLMProviderModel).order_by(LLMProviderModel.is_default.desc()))
    providers = result.scalars().all()
    return providers


@router.get("/{provider_id}", response_model=LLMProviderResponse)
async def get_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    """获取单个 Provider 配置"""
    result = await db.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")
    return provider


@router.post("", response_model=LLMProviderResponse, status_code=status.HTTP_201_CREATED)
async def create_provider(data: LLMProviderCreate, db: AsyncSession = Depends(get_db)):
    """创建新的 LLM Provider 配置"""

    # 检查是否已存在
    result = await db.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == data.provider_id))
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"Provider '{data.provider_id}' already exists")

    # 如果设为默认，先取消其他默认
    if data.is_default:
        await db.execute(
            update(LLMProviderModel).where(LLMProviderModel.is_default == True).values(is_default=False)
        )

    provider = LLMProviderModel(**data.model_dump())
    db.add(provider)
    await db.commit()
    await db.refresh(provider)

    logger.info("llm_provider_created", provider_id=data.provider_id, name=data.name)
    return provider


@router.put("/{provider_id}", response_model=LLMProviderResponse)
async def update_provider(
    provider_id: str,
    data: LLMProviderUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新 LLM Provider 配置"""

    result = await db.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    # 如果设为默认，先取消其他默认
    if data.is_default:
        await db.execute(
            update(LLMProviderModel).where(LLMProviderModel.is_default == True).values(is_default=False)
        )

    # 更新字段
    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)

    await db.commit()
    await db.refresh(provider)

    logger.info("llm_provider_updated", provider_id=provider_id)
    return provider


@router.delete("/{provider_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    """删除 LLM Provider 配置"""

    result = await db.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    await db.execute(delete(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id))
    await db.commit()

    logger.info("llm_provider_deleted", provider_id=provider_id)


@router.post("/test", response_model=LLMProviderTestResponse)
async def test_provider(data: LLMProviderTestRequest, db: AsyncSession = Depends(get_db)):
    """测试 LLM Provider 连接"""

    # 获取 Provider 配置
    result = await db.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == data.provider_id))
    provider = result.scalar_one_or_none()

    if not provider:
        # 尝试用请求中的数据测试
        test_config = {
            "api_key": data.api_key or "",
            "base_url": data.base_url or "",
        }
    else:
        test_config = {
            "api_key": data.api_key or provider.api_key or "",
            "base_url": data.base_url or provider.base_url or "",
        }

    if not test_config["api_key"]:
        return LLMProviderTestResponse(
            success=False,
            error_message="API Key is required",
        )

    import time
    start_time = time.perf_counter()

    try:
        # 根据 provider_id 导入对应的 Provider
        from app.llm.providers.dashscope import DashScopeProvider
        from app.llm.providers.openai import OpenAIProvider
        from app.llm.providers.compatible import OpenAICompatibleProvider
        from app.llm.base import LLMCallOptions, LLMCallMeta

        model = data.model or "gpt-4o-mini" if data.provider_id == "openai" else "qwen-turbo"

        if data.provider_id == "dashscope":
            test_provider = DashScopeProvider(
                api_key=test_config["api_key"],
                base_url=test_config["base_url"] or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                timeout=30,
            )
        elif data.provider_id == "openai":
            test_provider = OpenAIProvider(
                api_key=test_config["api_key"],
                base_url=test_config["base_url"] or "https://api.openai.com/v1",
                timeout=30,
            )
        else:
            # 通用兼容模式
            test_provider = OpenAICompatibleProvider(
                api_key=test_config["api_key"],
                base_url=test_config["base_url"] or "http://localhost:8000/v1",
                timeout=30,
            )

        meta = LLMCallMeta(agent_id="test_provider", trace_id="test")

        response = await test_provider.complete(
            prompt="Reply: OK",
            options=LLMCallOptions(
                system_prompt="You are a helpful assistant.",
                temperature=0.1,
                max_tokens=10,
                model=model,
            ),
            meta=meta,
        )

        latency_ms = (time.perf_counter() - start_time) * 1000

        # 更新测试状态
        if provider:
            provider.test_status = "success"
            provider.test_message = None
            await db.commit()

        return LLMProviderTestResponse(
            success=True,
            latency_ms=round(latency_ms, 2),
            response_preview=response.content[:100] if response.content else None,
        )

    except Exception as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        error_msg = str(e)

        # 更新测试状态
        if provider:
            provider.test_status = "failed"
            provider.test_message = error_msg[:500]
            await db.commit()

        logger.error("llm_provider_test_failed", provider_id=data.provider_id, error=error_msg)

        return LLMProviderTestResponse(
            success=False,
            latency_ms=round(latency_ms, 2),
            error_message=error_msg[:500],
        )


@router.get("/active/default")
async def get_default_provider(db: AsyncSession = Depends(get_db)):
    """获取当前默认的 LLM Provider"""
    result = await db.execute(
        select(LLMProviderModel).where(
            LLMProviderModel.is_default == True,
            LLMProviderModel.is_enabled == True
        )
    )
    provider = result.scalar_one_or_none()
    if not provider:
        return {"provider_id": None, "message": "No default provider configured"}
    return {
        "provider_id": provider.provider_id,
        "name": provider.name,
        "default_model": provider.default_model,
    }


@router.post("/active/default/{provider_id}")
async def set_default_provider(provider_id: str, db: AsyncSession = Depends(get_db)):
    """设置默认 LLM Provider"""
    result = await db.execute(select(LLMProviderModel).where(LLMProviderModel.provider_id == provider_id))
    provider = result.scalar_one_or_none()
    if not provider:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_id}' not found")

    # 取消其他默认
    await db.execute(
        update(LLMProviderModel).where(LLMProviderModel.is_default == True).values(is_default=False)
    )

    # 设置新的默认
    provider.is_default = True
    provider.is_enabled = True
    await db.commit()

    logger.info("llm_default_provider_changed", provider_id=provider_id)
    return {"provider_id": provider_id, "message": "Set as default provider"}
