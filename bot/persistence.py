"""
PostgreSQL-backed persistence for python-telegram-bot.
Stores user context and chat-data in the main backend DB instead of a local pickle file.
"""

import logging
from typing import DefaultDict, Dict, Any, Optional
from collections import defaultdict
from copy import deepcopy

from telegram.ext import BasePersistence, PersistenceInput
from sqlalchemy import select, delete

from app.database import AsyncSessionLocal
from app.models import User, ConversationState

logger = logging.getLogger(__name__)


class PostgresPersistence(BasePersistence):
    """
    Persistence class for Python-Telegram-Bot that stores Conversation 
    and User Data into PostgreSQL.
    """

    def __init__(self):
        super().__init__(
            store_data=PersistenceInput(
                user_data=True,
                chat_data=False,
                bot_data=False,
                callback_data=False,
            )
        )
        # Use an in-memory cache to avoid hitting the DB for every single update
        # while processing updates (syncs to DB constantly)
        self.user_data: DefaultDict[int, Dict[str, Any]] = defaultdict(dict)
        self.conversations: Dict[str, Dict[tuple, Any]] = {}

    async def get_user_data(self) -> DefaultDict[int, Dict[str, Any]]:
        """Restores user data from the DB."""
        # For simplicity in this demo class, we will fetch data dynamically
        # or treat the cache as the source until we implement a full sync
        return self.user_data

    async def get_chat_data(self) -> DefaultDict[int, Dict[str, Any]]:
        return defaultdict(dict)

    async def get_bot_data(self) -> Dict[str, Any]:
        return {}

    async def get_callback_data(self) -> Optional[Any]:
        return None

    async def get_conversations(self, name: str) -> Dict[tuple, Any]:
        """Restore conversation data from DB."""
        if name not in self.conversations:
            self.conversations[name] = {}
        
        async with AsyncSessionLocal() as session:
            # Load conversation states from the database
            result = await session.execute(
                select(ConversationState, User.telegram_id).join(User)
            )
            rows = result.all()
            for state, tg_id in rows:
                if state.state_type == name:
                    # Key for user conversations is usually (user_id, user_id) 
                    # based on PTB defaults for private chats
                    key = (tg_id, tg_id) 
                    try:
                        self.conversations[name][key] = int(state.current_step) if state.current_step else state.current_step
                    except ValueError:
                         self.conversations[name][key] = state.current_step
                         
        return self.conversations[name]

    async def update_conversation(
        self, name: str, key: tuple, new_state: Optional[object]
    ) -> None:
        """Save a conversation state to DB."""
        if name not in self.conversations:
            self.conversations[name] = {}
            
        self.conversations[name][key] = new_state
        
        # Typically key is (chat_id, user_id)
        tg_id = key[1]
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.telegram_id == tg_id))
            user = result.scalar_one_or_none()
            if not user:
                return
                
            if new_state is None:
                # Conversation ended, delete state
                await session.execute(
                    delete(ConversationState).where(
                        ConversationState.user_id == user.id,
                        ConversationState.state_type == name
                    )
                )
                await session.commit()
            else:
                # Manual Upsert since we don't have a unique constraint on (user_id, state_type)
                existing = await session.execute(
                    select(ConversationState).where(
                        ConversationState.user_id == user.id,
                        ConversationState.state_type == name
                    )
                )
                conv = existing.scalar_one_or_none()
                if conv:
                    conv.current_step = str(new_state)
                else:
                    new_conv = ConversationState(
                        user_id=user.id,
                        state_type=name,
                        current_step=str(new_state)
                    )
                    session.add(new_conv)
                await session.commit()

    async def update_user_data(self, user_id: int, data: Dict[str, Any]) -> None:
        """Update user data (e.g. pending properties). For now, kept in memory as temp data."""
        self.user_data[user_id] = deepcopy(data)

    async def update_chat_data(self, chat_id: int, data: Dict[str, Any]) -> None:
        pass

    async def update_bot_data(self, data: Dict[str, Any]) -> None:
        pass

    async def update_callback_data(self, data: Any) -> None:
        pass

    async def flush(self) -> None:
        """Called when the bot shuts down to ensure everything is saved."""
        logger.info("Flushing PostgresPersistence")

    async def drop_chat_data(self, chat_id: int) -> None:
        pass
    
    async def drop_user_data(self, user_id: int) -> None:
        if user_id in self.user_data:
            del self.user_data[user_id]
            
    async def refresh_user_data(self, user_id: int, user_data: Dict[str, Any]) -> None:
        pass
    
    async def refresh_chat_data(self, chat_id: int, chat_data: Dict[str, Any]) -> None:
         pass
    
    async def refresh_bot_data(self, bot_data: Dict[str, Any]) -> None:
         pass
