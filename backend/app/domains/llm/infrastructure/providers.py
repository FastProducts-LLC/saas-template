"""Text LLM gateway — implements the LlmGateway port.

One dispatching gateway routes each provider to the right SDK. SDKs are
imported lazily inside each method so the app boots without any API key, and
`check_configured` raises `LlmProviderNotConfigured` *before* credits are held
when the relevant key is missing. Models resolve from settings at call time.
"""

from app.core.config import settings
from app.domains.llm.domain.entities import LlmProvider, LlmResult
from app.domains.llm.domain.errors import LlmCallFailed, LlmProviderNotConfigured


class DispatchingLlmGateway:
    """LlmGateway port: route each provider to its SDK."""

    def _models(self) -> dict[LlmProvider, str]:
        # Resolved at call time (not import time) so settings overrides apply.
        return {
            LlmProvider.GEMINI: settings.llm_gemini_model,
            LlmProvider.OPENAI: settings.llm_openai_model,
            LlmProvider.ANTHROPIC: settings.llm_anthropic_model,
        }

    def check_configured(self, provider: LlmProvider) -> None:
        if provider == LlmProvider.GEMINI and not settings.gemini_api_key:
            raise LlmProviderNotConfigured("Gemini is not configured (GEMINI_API_KEY).")
        if provider == LlmProvider.OPENAI and not settings.openai_api_key:
            raise LlmProviderNotConfigured("OpenAI is not configured (OPENAI_API_KEY).")
        if provider == LlmProvider.ANTHROPIC and not settings.anthropic_api_key:
            raise LlmProviderNotConfigured("Anthropic is not configured (ANTHROPIC_API_KEY).")

    def model_for(self, provider: LlmProvider) -> str:
        return self._models()[provider]

    async def complete(self, provider: LlmProvider, prompt: str, max_tokens: int) -> LlmResult:
        if provider == LlmProvider.ANTHROPIC:
            return await self._complete_anthropic(prompt, max_tokens)
        if provider == LlmProvider.OPENAI:
            return await self._complete_openai(prompt, max_tokens)
        if provider == LlmProvider.GEMINI:
            return await self._complete_gemini(prompt, max_tokens)
        raise LlmCallFailed(f"Unsupported provider '{provider}'.")

    async def _complete_anthropic(self, prompt: str, max_tokens: int) -> LlmResult:
        from anthropic import AsyncAnthropic  # imported lazily so the app boots without the key

        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        resp = await client.messages.create(
            model=self.model_for(LlmProvider.ANTHROPIC),
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        if not text:
            raise LlmCallFailed("provider returned no text")
        return LlmResult(
            text=text,
            tokens_in=resp.usage.input_tokens,
            tokens_out=resp.usage.output_tokens,
        )

    async def _complete_openai(self, prompt: str, max_tokens: int) -> LlmResult:
        from openai import AsyncOpenAI  # imported lazily so the app boots without the key

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model=self.model_for(LlmProvider.OPENAI),
            max_completion_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.choices[0].message.content or ""
        if not text:
            raise LlmCallFailed("provider returned no text")
        usage = resp.usage
        return LlmResult(
            text=text,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )

    async def _complete_gemini(self, prompt: str, max_tokens: int) -> LlmResult:
        from google import genai  # imported lazily so the app boots without the key

        client = genai.Client(api_key=settings.gemini_api_key)
        resp = await client.aio.models.generate_content(
            model=self.model_for(LlmProvider.GEMINI),
            contents=prompt,
            config={"max_output_tokens": max_tokens},
        )
        text = resp.text or ""
        if not text:
            raise LlmCallFailed("provider returned no text")
        usage = resp.usage_metadata
        return LlmResult(
            text=text,
            tokens_in=(usage.prompt_token_count or 0) if usage else 0,
            tokens_out=(usage.candidates_token_count or 0) if usage else 0,
        )
