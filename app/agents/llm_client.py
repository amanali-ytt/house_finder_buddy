"""
Free LLM Client using Hugging Face Hub InferenceClient.
Uses the official huggingface_hub library for inference.

Free tier: 300 requests/hour (registered), 1/hour (unregistered)
For better access, get a free token at huggingface.co/settings/tokens
"""

import json
import os
import re
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel
from huggingface_hub import InferenceClient
from tenacity import retry, stop_after_attempt, wait_exponential


class HuggingFaceLLMClient:
    """
    Free LLM client using Hugging Face InferenceClient.
    
    Free models available:
    - Qwen/Qwen2.5-Coder-32B-Instruct
    - meta-llama/Llama-3.2-3B-Instruct
    - microsoft/Phi-3.5-mini-instruct
    """
    
    FREE_MODELS = [
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "meta-llama/Llama-3.2-3B-Instruct",
        "microsoft/Phi-3.5-mini-instruct",
    ]
    
    def __init__(self):
        # HF token is optional but recommended for higher limits
        self.hf_token = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", None))
        self.model = os.getenv("HF_MODEL", "Qwen/Qwen2.5-Coder-32B-Instruct")
        
        # Initialize client
        self.client = InferenceClient(token=self.hf_token if self.hf_token else None)
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from response text."""
        text = text.strip()
        # Remove markdown code blocks
        if "```json" in text:
            match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return match.group(1)
        if "```" in text:
            match = re.search(r'```\s*(.*?)\s*```', text, re.DOTALL)
            if match:
                return match.group(1)
        # Try to find JSON object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return match.group(0)
        return text
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Send a completion request to Hugging Face."""
        model = model or self.model
        json_mode = response_format is not None
        
        if json_mode:
            user_message = f"{user_message}\n\nIMPORTANT: Respond with valid JSON only. No markdown, no explanation."
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Use synchronous API (will be wrapped)
        import asyncio
        loop = asyncio.get_event_loop()
        
        def _sync_call():
            return self.client.chat_completion(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        
        response = await loop.run_in_executor(None, _sync_call)
        
        result = response.choices[0].message.content
        
        if json_mode:
            result = self._extract_json(result)
        
        return result
    
    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send request with conversation history."""
        last_message = messages[-1]["content"] if messages else ""
        return await self.complete(
            system_prompt=system_prompt,
            user_message=last_message,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
    
    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> BaseModel:
        """Get structured response validated against Pydantic model."""
        response = await self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        data = json.loads(response)
        return response_model(**data)
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get provider info."""
        return {
            "provider": "huggingface",
            "model": self.model,
            "status": "ready",
            "has_token": bool(self.hf_token),
            "free": True
        }


# Singleton instance
llm_client = HuggingFaceLLMClient()
