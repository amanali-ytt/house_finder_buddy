from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import Settings
from bot import handlers
from bot.states import ConversationState


class DummyMessage:
    def __init__(self, text="", document=None):
        self.text = text
        self.document = document
        self.reply_text = AsyncMock()


class DummyFile:
    async def download_as_bytearray(self):
        return bytearray(b"fake-file")


class DummyBot:
    async def get_file(self, _file_id):
        return DummyFile()


def build_update(*, text="", document=None):
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=123, first_name="Tester", username="tester"),
        message=DummyMessage(text=text, document=document),
    )


def build_context():
    return SimpleNamespace(user_data={}, bot=DummyBot())


def test_settings_default_to_provider_model():
    settings = Settings(
        _env_file=None,
        nvidia_model="deepseek-ai/deepseek-v3.2",
        openai_model_regular="gpt-4o-mini",
        openai_model_advanced="gpt-4o",
    )

    assert settings.regular_llm_model == "deepseek-ai/deepseek-v3.2"
    assert settings.advanced_llm_model == "deepseek-ai/deepseek-v3.2"


@pytest.mark.asyncio
async def test_onboarding_duplicate_check_awaits_database(monkeypatch):
    update = build_update(document=SimpleNamespace(file_name="props.pdf", file_id="file-1"))
    context = build_context()
    properties = [
        {"title": "Fresh listing", "city": "Chennai", "price": 10000, "property_type": "apartment"},
        {"title": "Duplicate listing", "city": "Chennai", "price": 11000, "property_type": "apartment"},
    ]

    process_uploaded_file = AsyncMock(return_value={"success": True, "properties": properties, "validation": {}})
    find_duplicates = AsyncMock(side_effect=[[], [{"id": "existing"}]])

    monkeypatch.setattr(handlers.llm_helpers, "process_uploaded_file", process_uploaded_file)
    monkeypatch.setattr(handlers.db, "find_duplicates", find_duplicates)

    result = await handlers.onboarding_receive_document(update, context)

    assert result == ConversationState.ONBOARDING_CONFIRMING.value
    assert context.user_data["pending_properties"] == [properties[0]]
    assert find_duplicates.await_count == 2


@pytest.mark.asyncio
async def test_direct_search_passes_full_query_plan(monkeypatch):
    update = build_update(text="2bhk apartment in chennai")
    context = build_context()
    query_plan = {
        "intent": "rent",
        "filters": [{"field": "city", "operator": "like", "value": "Chennai"}],
        "sort_by": "price",
        "sort_order": "asc",
        "limit": 10,
    }

    is_user_verified = AsyncMock(return_value=True)
    plan_search_query = AsyncMock(return_value=query_plan)
    search_properties = AsyncMock(return_value=[])

    monkeypatch.setattr(handlers.db, "is_user_verified", is_user_verified)
    monkeypatch.setattr(handlers.llm_helpers, "plan_search_query", plan_search_query)
    monkeypatch.setattr(handlers.db, "search_properties", search_properties)

    await handlers.handle_menu_text(update, context)

    search_properties.assert_awaited_once_with(query_plan)
