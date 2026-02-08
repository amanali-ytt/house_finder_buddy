"""
Base LLM client for interacting with OpenAI GPT models.
All agents use this client to ensure consistent behavior.
"""

import json
from typing import Optional, Dict, Any, Type
from openai import AsyncOpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()


class LLMClient:
    """Async OpenAI client wrapper with retry logic."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
    
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
        Send a completion request to OpenAI.
        
        Args:
            system_prompt: System instructions for the model
            user_message: User's input message
            model: Model to use (defaults to gpt-4o-mini)
            temperature: Creativity level (0-1)
            max_tokens: Maximum response length
            response_format: Optional JSON schema for structured output
            
        Returns:
            Model's response as string
        """
        model = model or settings.openai_model_regular
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add JSON mode if specified
        if response_format:
            kwargs["response_format"] = {"type": "json_object"}
        
        response = await self.client.chat.completions.create(**kwargs)
        
        return response.choices[0].message.content
    
    async def complete_with_history(
        self,
        system_prompt: str,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """
        Send a completion request with conversation history.
        
        Args:
            system_prompt: System instructions
            messages: List of {"role": "user/assistant", "content": "..."}
            model: Model to use
            temperature: Creativity level
            max_tokens: Maximum response length
            
        Returns:
            Model's response as string
        """
        model = model or settings.openai_model_regular
        
        full_messages = [{"role": "system", "content": system_prompt}]
        full_messages.extend(messages)
        
        response = await self.client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"}
        )
        
        return response.choices[0].message.content
    
    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.3,
    ) -> BaseModel:
        """
        Get a structured response that validates against a Pydantic model.
        
        Args:
            system_prompt: System instructions
            user_message: User's input
            response_model: Pydantic model class for validation
            model: Model to use
            temperature: Creativity (lower for structured)
            
        Returns:
            Validated Pydantic model instance
        """
        response = await self.complete(
            system_prompt=system_prompt,
            user_message=user_message,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"}
        )
        
        # Parse and validate
        data = json.loads(response)
        return response_model(**data)


# Singleton instance
llm_client = LLMClient()
