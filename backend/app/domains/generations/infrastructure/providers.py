"""AI provider gateways — implement the ProviderGateway port.

Each gateway returns raw result bytes + mime type; the application layer
owns the credit lifecycle and persistence. Gateways raise
`ProviderNotConfigured` *before* any credits are held when the relevant
API key is missing.
"""

import asyncio

from app.core.config import settings
from app.domains.credits.domain import CreditAction
from app.domains.generations.domain import (
    GeneratedAsset,
    GenerationFailed,
    ProviderNotConfigured,
)

PROVIDER_MODELS: dict[CreditAction, str] = {
    CreditAction.IMAGE_NANO_BANANA: "gemini-2.5-flash-image",
    CreditAction.IMAGE_GPT: "gpt-image-1",
    CreditAction.VIDEO_VEO: "veo-3.1-generate-preview",
}


class GeminiGateway:
    """Gemini nano-banana images and VEO video via the google-genai SDK."""

    def __init__(self) -> None:
        if not settings.gemini_api_key:
            raise ProviderNotConfigured("Gemini is not configured (GEMINI_API_KEY).")
        from google import genai  # imported lazily so the app boots without the key

        self._client = genai.Client(api_key=settings.gemini_api_key)

    async def generate_image(self, prompt: str) -> GeneratedAsset:
        response = await self._client.aio.models.generate_content(
            model=PROVIDER_MODELS[CreditAction.IMAGE_NANO_BANANA], contents=prompt
        )
        for candidate in response.candidates or []:
            for part in candidate.content.parts or []:
                if part.inline_data and part.inline_data.data:
                    return GeneratedAsset(
                        data=part.inline_data.data,
                        mime_type=part.inline_data.mime_type or "image/png",
                    )
        raise GenerationFailed("Gemini returned no image data.")

    async def generate_video(self, prompt: str, poll_seconds: float = 10.0) -> GeneratedAsset:
        """VEO is a long-running operation: poll until done, then download."""
        from google.genai import types

        # The bare `prompt=` argument is deprecated in google-genai and slated
        # for removal; `source` is the supported input shape.
        operation = await self._client.aio.models.generate_videos(
            model=PROVIDER_MODELS[CreditAction.VIDEO_VEO],
            source=types.GenerateVideosSource(prompt=prompt),
        )
        while not operation.done:
            await asyncio.sleep(poll_seconds)
            operation = await self._client.aio.operations.get(operation)
        if operation.error:
            raise GenerationFailed(f"VEO generation failed: {operation.error}")
        videos = operation.response.generated_videos if operation.response else None
        if not videos:
            raise GenerationFailed("VEO returned no video.")
        video = videos[0].video
        data = await self._client.aio.files.download(file=video)
        data = data or video.video_bytes
        if not data:
            raise GenerationFailed("VEO video could not be downloaded.")
        return GeneratedAsset(data=data, mime_type=video.mime_type or "video/mp4")


class OpenAIImageGateway:
    """GPT image generation via the OpenAI SDK."""

    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ProviderNotConfigured("OpenAI is not configured (OPENAI_API_KEY).")
        from openai import AsyncOpenAI  # imported lazily so the app boots without the key

        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_image(self, prompt: str) -> GeneratedAsset:
        import base64

        result = await self._client.images.generate(
            model=PROVIDER_MODELS[CreditAction.IMAGE_GPT], prompt=prompt, size="1024x1024"
        )
        if not result.data or not result.data[0].b64_json:
            raise GenerationFailed("OpenAI returned no image data.")
        return GeneratedAsset(data=base64.b64decode(result.data[0].b64_json), mime_type="image/png")


class DispatchingProviderGateway:
    """ProviderGateway port: route each kind to the right provider."""

    def check_configured(self, kind: CreditAction) -> None:
        if kind in (CreditAction.IMAGE_NANO_BANANA, CreditAction.VIDEO_VEO):
            if not settings.gemini_api_key:
                raise ProviderNotConfigured("Gemini is not configured (GEMINI_API_KEY).")
        elif kind == CreditAction.IMAGE_GPT:
            if not settings.openai_api_key:
                raise ProviderNotConfigured("OpenAI is not configured (OPENAI_API_KEY).")

    def model_for(self, kind: CreditAction) -> str:
        return PROVIDER_MODELS[kind]

    async def run(self, kind: CreditAction, prompt: str) -> GeneratedAsset:
        """Dispatch to the right provider. Instantiating a gateway raises
        `ProviderNotConfigured` if its API key is missing."""
        if kind == CreditAction.IMAGE_NANO_BANANA:
            return await GeminiGateway().generate_image(prompt)
        if kind == CreditAction.VIDEO_VEO:
            return await GeminiGateway().generate_video(prompt)
        if kind == CreditAction.IMAGE_GPT:
            return await OpenAIImageGateway().generate_image(prompt)
        raise GenerationFailed(f"Unsupported generation kind '{kind}'.")
