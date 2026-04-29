"""Runtime image generation helpers for draft preview assets."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx


SUPPORTED_IMAGE_GENERATION_PROVIDERS = {"openai", "custom", "volcengine", "dashscope", "wan", "alibaba"}


@dataclass
class ImageGenerationResult:
    success: bool
    asset_url: str | None = None
    provider: str | None = None
    model: str | None = None
    error_message: str | None = None
    raw: dict[str, Any] | None = None


class ImageGenerationService:
    """Call configured image generation providers without persisting secrets."""

    async def generate(
        self,
        *,
        config: dict[str, Any] | None,
        prompt: str,
        size: str = "1024x1024",
    ) -> ImageGenerationResult:
        runtime = self._normalize_config(config)
        if not runtime["enabled"]:
            return ImageGenerationResult(
                success=False,
                provider=runtime["provider"],
                model=runtime["model"],
                error_message="image_generation_not_configured",
            )

        provider = runtime["provider"]
        try:
            if provider in {"openai", "custom", "volcengine"}:
                return await self._generate_openai_compatible(runtime, prompt=prompt, size=size)
            if provider in {"dashscope", "wan", "alibaba"}:
                return await self._generate_dashscope(runtime, prompt=prompt, size=size)
            if provider not in SUPPORTED_IMAGE_GENERATION_PROVIDERS:
                return ImageGenerationResult(
                    success=False,
                    provider=provider,
                    model=runtime["model"],
                    error_message=f"{provider}_generation_not_wired_yet",
                )
            return await self._generate_openai_compatible(runtime, prompt=prompt, size=size)
        except httpx.TimeoutException:
            return ImageGenerationResult(
                success=False,
                provider=provider,
                model=runtime["model"],
                error_message="image_generation_timeout",
            )
        except httpx.HTTPError as exc:
            return ImageGenerationResult(
                success=False,
                provider=provider,
                model=runtime["model"],
                error_message=f"image_generation_http_error: {exc}",
            )
        except Exception as exc:  # Defensive: post-process must never block draft preview.
            return ImageGenerationResult(
                success=False,
                provider=provider,
                model=runtime["model"],
                error_message=f"image_generation_error: {exc}",
            )

    def _normalize_config(self, config: dict[str, Any] | None) -> dict[str, Any]:
        data = config or {}
        provider = str(data.get("provider") or "dashscope").strip().lower()
        model = str(data.get("model") or "wan2.7-image").strip()
        api_key = str(data.get("api_key") or "").strip()
        base_url = str(data.get("base_url") or "").strip()
        if not base_url:
            if provider in {"openai", "custom"}:
                base_url = "https://api.openai.com/v1/images/generations"
            elif provider == "volcengine":
                base_url = "https://ark.cn-beijing.volces.com/api/v3/images/generations"
            else:
                base_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation"
        enabled = self._as_bool(data.get("enabled"))
        return {
            "provider": provider,
            "model": model,
            "api_key": api_key,
            "base_url": base_url,
            "enabled": enabled and bool(model) and bool(api_key),
        }

    def _as_bool(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    async def _generate_openai_compatible(
        self,
        runtime: dict[str, Any],
        *,
        prompt: str,
        size: str,
    ) -> ImageGenerationResult:
        headers = {"Authorization": f"Bearer {runtime['api_key']}"}
        payload = {
            "model": runtime["model"],
            "prompt": prompt,
            "size": size,
            "n": 1,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(90.0, connect=12.0), follow_redirects=True) as client:
            response = await client.post(runtime["base_url"], headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            asset_url = await self._materialize_remote_asset(client, self._extract_asset_url(data))
        if asset_url:
            return ImageGenerationResult(
                success=True,
                asset_url=asset_url,
                provider=runtime["provider"],
                model=runtime["model"],
                raw=self._safe_raw(data),
            )
        return ImageGenerationResult(
            success=False,
            provider=runtime["provider"],
            model=runtime["model"],
            error_message="image_generation_empty_response",
            raw=self._safe_raw(data),
        )

    async def _generate_dashscope(
        self,
        runtime: dict[str, Any],
        *,
        prompt: str,
        size: str,
    ) -> ImageGenerationResult:
        dashscope_size = self._dashscope_size(runtime["model"], size)
        headers = {
            "Authorization": f"Bearer {runtime['api_key']}",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": runtime["model"],
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ]
            },
            "parameters": {"size": dashscope_size, "n": 1, "watermark": False},
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=12.0), follow_redirects=True) as client:
            response = await client.post(runtime["base_url"], headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            asset_url = await self._materialize_remote_asset(client, self._extract_asset_url(data))
            if asset_url:
                return ImageGenerationResult(
                    success=True,
                    asset_url=asset_url,
                    provider=runtime["provider"],
                    model=runtime["model"],
                    raw=self._safe_raw(data),
                )

            task_id = self._extract_task_id(data)
            if task_id:
                task_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
                for _ in range(18):
                    await self._sleep(2.0)
                    poll = await client.get(task_url, headers={"Authorization": f"Bearer {runtime['api_key']}"})
                    poll.raise_for_status()
                    poll_data = poll.json()
                    asset_url = await self._materialize_remote_asset(client, self._extract_asset_url(poll_data))
                    if asset_url:
                        return ImageGenerationResult(
                            success=True,
                            asset_url=asset_url,
                            provider=runtime["provider"],
                            model=runtime["model"],
                            raw=self._safe_raw(poll_data),
                        )
                    status = str((poll_data.get("output") or {}).get("task_status") or "").upper()
                    if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                        output = poll_data.get("output") if isinstance(poll_data.get("output"), dict) else {}
                        detail = self._join_error_parts(output.get("code"), output.get("message"), status)
                        return ImageGenerationResult(
                            success=False,
                            provider=runtime["provider"],
                            model=runtime["model"],
                            error_message=detail,
                            raw=self._safe_raw(poll_data),
                        )
                return ImageGenerationResult(
                    success=False,
                    provider=runtime["provider"],
                    model=runtime["model"],
                    error_message="dashscope_task_timeout",
                    raw=self._safe_raw(data),
                )

        return ImageGenerationResult(
            success=False,
            provider=runtime["provider"],
            model=runtime["model"],
            error_message=self._join_error_parts(data.get("code"), data.get("message"), "image_generation_empty_response"),
            raw=self._safe_raw(data),
        )

    def _dashscope_size(self, model: str, size: str) -> str:
        if str(model or "").startswith("wan2.7-image"):
            return "1K"
        return size.replace("x", "*")

    def _join_error_parts(self, code: Any, message: Any, fallback: str) -> str:
        parts = [str(item).strip() for item in (code, message) if str(item or "").strip()]
        return ": ".join(parts) if parts else fallback

    async def _sleep(self, seconds: float) -> None:
        import asyncio

        await asyncio.sleep(seconds)

    def _extract_task_id(self, data: dict[str, Any]) -> str | None:
        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        value = output.get("task_id") or data.get("task_id")
        return str(value).strip() if value else None

    def _extract_asset_url(self, data: dict[str, Any]) -> str | None:
        for item in data.get("data") or []:
            if not isinstance(item, dict):
                continue
            if item.get("b64_json"):
                return f"data:image/png;base64,{item['b64_json']}"
            if item.get("url"):
                return str(item["url"])

        output = data.get("output") if isinstance(data.get("output"), dict) else {}
        choices = output.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
                content = message.get("content")
                if not isinstance(content, list):
                    continue
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    value = item.get("image") or item.get("url") or item.get("image_url")
                    if value:
                        return str(value)
        for collection_key in ("results", "result", "images"):
            collection = output.get(collection_key)
            if isinstance(collection, dict):
                collection = [collection]
            if not isinstance(collection, list):
                continue
            for item in collection:
                if not isinstance(item, dict):
                    continue
                value = item.get("url") or item.get("image_url") or item.get("resource_url")
                if value:
                    return str(value)
                b64_value = item.get("b64_json") or item.get("base64")
                if b64_value:
                    return f"data:image/png;base64,{b64_value}"

        value = output.get("url") or output.get("image_url") or data.get("url")
        if value:
            return str(value)
        b64_value = output.get("b64_json") or output.get("base64") or data.get("b64_json")
        if b64_value:
            return f"data:image/png;base64,{b64_value}"
        image_bytes = output.get("image")
        if isinstance(image_bytes, str) and len(image_bytes) > 80:
            try:
                base64.b64decode(image_bytes, validate=True)
                return f"data:image/png;base64,{image_bytes}"
            except Exception:
                return None
        return None

    async def _materialize_remote_asset(self, client: httpx.AsyncClient, asset_url: str | None) -> str | None:
        if not asset_url or asset_url.startswith("data:image/"):
            return asset_url
        if not asset_url.startswith(("http://", "https://")):
            return asset_url
        response = await client.get(asset_url)
        response.raise_for_status()
        content_type = str(response.headers.get("content-type") or "image/png").split(";")[0].strip().lower()
        if not content_type.startswith("image/"):
            return asset_url
        content = response.content
        if len(content) > 8 * 1024 * 1024:
            return asset_url
        encoded = base64.b64encode(content).decode("ascii")
        return f"data:{content_type};base64,{encoded}"

    def _safe_raw(self, data: dict[str, Any]) -> dict[str, Any]:
        safe = dict(data)
        if "request_id" in safe:
            return {"request_id": safe.get("request_id"), "output": safe.get("output")}
        return {"keys": sorted(str(key) for key in safe.keys())}


image_generation_service = ImageGenerationService()
