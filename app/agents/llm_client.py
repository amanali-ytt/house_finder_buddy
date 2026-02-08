"""
Free LLM Client - Uses Groq (free tier) or Ollama (local) for testing.
No OpenAI API key required!

Options:
1. Groq: Free tier with llama-3.1-70b-versatile (get key at console.groq.com)
2. Ollama: Completely free, runs locally (install from ollama.ai)
"""

import json
import os
from typing import Optional, Dict, Any, Type
from pydantic import BaseModel
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class FreeLLMClient:
    """
    LLM client that supports free providers:
    - Groq: Fast inference with free tier (needs GROQ_API_KEY)
    - Ollama: Local execution (needs Ollama running)
    """
    
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
        # Determine which provider to use
        if self.groq_api_key:
            self.provider = "groq"
            self.model = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")
        else:
            self.provider = "ollama"
            self.model = os.getenv("OLLAMA_MODEL", "llama3.1")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        response_format: Optional[Dict] = None,
    ) -> str:
        """
        Send a completion request to the free LLM provider.
        """
        model = model or self.model
        
        if self.provider == "groq":
            return await self._groq_complete(
                system_prompt, user_message, model, temperature, max_tokens, response_format
            )
        else:
            return await self._ollama_complete(
                system_prompt, user_message, model, temperature, max_tokens, response_format
            )
    
    async def _groq_complete(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict],
    ) -> str:
        """Call Groq API."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Add JSON instruction if needed
            if response_format:
                user_message = f"{user_message}\n\nRespond with valid JSON only."
            
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.groq_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
            )
            
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def _ollama_complete(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        temperature: float,
        max_tokens: int,
        response_format: Optional[Dict],
    ) -> str:
        """Call Ollama local API."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Add JSON instruction if needed
            if response_format:
                user_message = f"{user_message}\n\nRespond with valid JSON only."
            
            response = await client.post(
                f"{self.ollama_base_url}/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message}
                    ],
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_predict": max_tokens,
                    }
                }
            )
            
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
    
    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send a completion request with conversation history."""
        model = model or self.model
        
        # Combine last message for simple implementation
        last_message = messages[-1]["content"] if messages else ""
        
        # Add JSON instruction
        last_message = f"{last_message}\n\nRespond with valid JSON only."
        
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
        """Get a structured response that validates against a Pydantic model."""
        response = await self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        
        # Extract JSON from response (handle markdown code blocks)
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])
        
        data = json.loads(response)
        return response_model(**data)
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get info about current provider."""
        return {
            "provider": self.provider,
            "model": self.model,
            "status": "ready" if (self.groq_api_key or self.provider == "ollama") else "no_key"
        }


# Singleton instance
llm_client = FreeLLMClient()
