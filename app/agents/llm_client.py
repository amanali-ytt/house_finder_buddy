"""
NVIDIA LLM Client - Uses OpenAI SDK pointed at NVIDIA's API.
Supports DeepSeek V3.2 with reasoning/thinking mode.

Uses the OpenAI Python library with NVIDIA's base URL:
https://integrate.api.nvidia.com/v1
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any, Type, List
from pydantic import BaseModel
from openai import OpenAI

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NvidiaLLMClient:
    """
    LLM client using OpenAI SDK with NVIDIA's API endpoint.
    Supports DeepSeek V3.2 with reasoning/thinking mode and streaming.
    """

    def __init__(self):
        self.api_key = settings.nvidia_api_key
        self.model = settings.nvidia_model
        self.base_url = "https://integrate.api.nvidia.com/v1"

        if not self.api_key:
            logger.warning(
                "⚠️  NVIDIA_API_KEY not set! LLM calls will fail. "
                "Set it in your .env file."
            )

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

    def _is_deepseek(self, model: Optional[str] = None) -> bool:
        """Check if the model is a DeepSeek model (supports reasoning)."""
        use_model = model or self.model
        return "deepseek" in use_model.lower()

    def _call_api(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = True,
        enable_thinking: bool = False,
    ) -> str:
        """
        Make an API call via the OpenAI SDK.
        
        For DeepSeek models, supports reasoning/thinking mode which provides
        chain-of-thought reasoning before the final answer.
        """
        use_model = model or self.model
        is_deepseek = "deepseek" in use_model.lower()

        logger.info(f"🤖 Calling NVIDIA API (model={use_model}, stream={stream}, thinking={enable_thinking})")

        # Build extra parameters for DeepSeek thinking mode
        extra_kwargs = {}
        if is_deepseek and enable_thinking:
            extra_kwargs["extra_body"] = {
                "chat_template_kwargs": {"thinking": True}
            }

        try:
            if stream:
                completion = self.client.chat.completions.create(
                    model=use_model,
                    messages=messages,
                    temperature=temperature,
                    top_p=0.95,
                    max_tokens=max_tokens,
                    stream=True,
                    **extra_kwargs,
                )

                full_content = ""
                reasoning_content = ""

                for chunk in completion:
                    if not getattr(chunk, "choices", None):
                        continue

                    # Capture reasoning (thinking) content separately
                    reasoning = getattr(chunk.choices[0].delta, "reasoning_content", None)
                    if reasoning:
                        reasoning_content += reasoning

                    # Capture actual response content
                    if chunk.choices and chunk.choices[0].delta.content is not None:
                        full_content += chunk.choices[0].delta.content

                if reasoning_content:
                    logger.debug(f"🧠 Reasoning: {reasoning_content[:200]}...")

                return full_content
            else:
                completion = self.client.chat.completions.create(
                    model=use_model,
                    messages=messages,
                    temperature=temperature,
                    top_p=0.95,
                    max_tokens=max_tokens,
                    stream=False,
                    **extra_kwargs,
                )

                if completion.choices:
                    return completion.choices[0].message.content or ""
                return ""

        except Exception as e:
            logger.error(f"❌ NVIDIA API error: {e}")
            raise

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
        enable_thinking: bool = False,
    ) -> str:
        """
        Get a completion from the NVIDIA API.

        Args:
            system_prompt: System instruction for the model
            user_message: User's message/query
            model: Model override (defaults to config)
            temperature: Sampling temperature
            max_tokens: Max tokens in response
            response_format: Optional format spec (e.g. {"type": "json_object"})
            enable_thinking: Enable DeepSeek reasoning/thinking mode

        Returns:
            The model's response text (reasoning is logged but not returned)
        """
        # If JSON output is requested, reinforce it in the system prompt
        sys_content = system_prompt
        if response_format and response_format.get("type") == "json_object":
            sys_content += "\n\nYou MUST respond with valid JSON only. No markdown code fences, no explanation, just the raw JSON object."

        messages = [
            {"role": "system", "content": sys_content},
            {"role": "user", "content": user_message},
        ]

        return await asyncio.to_thread(
            self._call_api,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            enable_thinking=enable_thinking,
        )

    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        enable_thinking: bool = False,
    ) -> str:
        """
        Get completion with conversation history.

        Args:
            system_prompt: System instruction
            messages: List of {"role": ..., "content": ...} dicts
            model: Model override
            temperature: Sampling temperature
            max_tokens: Max tokens
            enable_thinking: Enable DeepSeek reasoning/thinking mode

        Returns:
            The model's response text
        """
        full_messages = [{"role": "system", "content": system_prompt}] + messages

        return await asyncio.to_thread(
            self._call_api,
            messages=full_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            enable_thinking=enable_thinking,
        )

    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> BaseModel:
        """
        Get structured response validated against a Pydantic model.

        Args:
            system_prompt: System instruction
            user_message: User's message
            response_model: Pydantic model class for validation
            model: Model override
            temperature: Sampling temperature

        Returns:
            Validated Pydantic model instance
        """
        response = await self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        # Clean up response — strip markdown fences if present
        text = response.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            json_lines = []
            for line in lines[1:]:
                if line.strip() == "```":
                    break
                json_lines.append(line)
            text = "\n".join(json_lines)

        data = json.loads(text)
        return response_model(**data)

    def get_provider_info(self) -> Dict[str, str]:
        """Get provider information."""
        return {
            "provider": "nvidia",
            "model": self.model,
            "status": "ready" if self.api_key else "no_api_key",
            "api_url": self.base_url,
            "thinking_support": str(self._is_deepseek()),
        }


# Singleton instance
llm_client = NvidiaLLMClient()
