"""
Conversation Agent - Guides users through property listing flow.
Collects missing fields and validates input through natural conversation.
"""

import json
from typing import Optional, List, Dict, Any

from app.agents.llm_client import llm_client
from app.agents.prompts import CONVERSATION_AGENT_SYSTEM
from app.schemas import ConversationAgentOutput
from app.config import get_settings

settings = get_settings()


class ConversationAgent:
    """
    Agent that manages multi-turn conversations for property listing.
    Maintains context and collects required fields progressively.
    """
    
    REQUIRED_FIELDS = ["listing_type", "property_type", "price", "city", "bedrooms"]
    
    def __init__(self):
        self.system_prompt = CONVERSATION_AGENT_SYSTEM
    
    async def process_message(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
        collected_data: Dict[str, Any] = None,
    ) -> ConversationAgentOutput:
        """
        Process a user message and return next action.
        
        Args:
            user_message: User's current message
            conversation_history: Previous messages in conversation
            collected_data: Previously collected field values
            
        Returns:
            ConversationAgentOutput with response and next action
        """
        conversation_history = conversation_history or []
        collected_data = collected_data or {}
        
        # Build context for LLM
        context = self._build_context(collected_data)
        
        # Add history and new message
        messages = conversation_history.copy()
        messages.append({
            "role": "user",
            "content": f"{context}\n\nUser message: {user_message}"
        })
        
        # Get response from LLM
        response = await llm_client.complete_with_history(
            system_prompt=self.system_prompt,
            messages=messages,
            model=settings.regular_llm_model,
            temperature=0.7,
        )
        
        # Parse response
        try:
            data = json.loads(response)
            output = ConversationAgentOutput(**data)
            
            # Merge newly collected fields with existing
            if output.collected_fields:
                collected_data.update(output.collected_fields)
            
            # Recalculate missing fields
            output.missing_required_fields = self._get_missing_fields(collected_data)
            output.is_complete = len(output.missing_required_fields) == 0
            
            return output
            
        except (json.JSONDecodeError, Exception) as e:
            # Fallback response on parse error
            return ConversationAgentOutput(
                message_to_user="I'm sorry, I had trouble understanding. Could you please rephrase that?",
                collected_fields={},
                next_action="ask_field",
                missing_required_fields=self._get_missing_fields(collected_data),
                is_complete=False
            )
    
    def _build_context(self, collected_data: Dict[str, Any]) -> str:
        """Build context string from collected data."""
        if not collected_data:
            return "No data collected yet."
        
        parts = ["Already collected:"]
        for key, value in collected_data.items():
            parts.append(f"- {key}: {value}")
        
        return "\n".join(parts)
    
    def _get_missing_fields(self, collected_data: Dict[str, Any]) -> List[str]:
        """Get list of required fields not yet collected."""
        return [f for f in self.REQUIRED_FIELDS if f not in collected_data]
    
    async def start_conversation(self) -> ConversationAgentOutput:
        """Start a new property listing conversation."""
        return ConversationAgentOutput(
            message_to_user=(
                "🏠 Welcome! I'll help you list your property.\n\n"
                "First, are you looking to put your property up for **RENT** or **SALE**?"
            ),
            collected_fields={},
            next_action="ask_field",
            missing_required_fields=self.REQUIRED_FIELDS.copy(),
            is_complete=False
        )
    
    async def handle_file_upload(
        self,
        extracted_text: str,
        collected_data: Dict[str, Any] = None,
    ) -> ConversationAgentOutput:
        """Handle file upload by noting it and asking for confirmation."""
        collected_data = collected_data or {}
        
        return ConversationAgentOutput(
            message_to_user=(
                "📄 I've received your file and extracted the property details.\n\n"
                "I'll now process this information. Please give me a moment..."
            ),
            collected_fields=collected_data,
            next_action="confirm",
            missing_required_fields=self._get_missing_fields(collected_data),
            is_complete=False
        )


# Singleton instance
conversation_agent = ConversationAgent()
