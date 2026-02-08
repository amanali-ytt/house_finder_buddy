"""
Query Planner Agent - Converts natural language to structured filters.
Outputs JSON only - never SQL. The query builder handles SQL construction.
"""

import json
from typing import Optional

from app.agents.llm_client import llm_client
from app.agents.prompts import QUERY_PLANNER_SYSTEM
from app.schemas import QueryPlannerOutput, QueryFilter, QueryFilterOperator
from app.config import get_settings

settings = get_settings()


class QueryPlannerAgent:
    """
    Agent that converts natural language property searches into structured filters.
    CRITICAL: Outputs JSON filters only - SQL is built by the secure query builder.
    """
    
    def __init__(self):
        self.system_prompt = QUERY_PLANNER_SYSTEM
    
    async def plan_query(
        self,
        user_query: str,
        context: Optional[str] = None,
    ) -> QueryPlannerOutput:
        """
        Convert a natural language query to structured filters.
        
        Args:
            user_query: User's natural language search query
            context: Optional context (e.g., user's city preference)
            
        Returns:
            QueryPlannerOutput with intent and filters
        """
        # Build user message
        user_message = f"""User Query: {user_query}

{f'Context: {context}' if context else ''}

Convert this search query into structured filters. Return a valid JSON object with intent, filters, sort_by, sort_order, and limit."""

        # Use GPT-4O Mini for fast query planning
        response = await llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            model=settings.openai_model_regular,  # GPT-4O Mini
            temperature=0.2,  # Low for consistent parsing
            response_format={"type": "json_object"}
        )
        
        # Parse response
        try:
            data = json.loads(response)
            return self._validate_and_convert(data)
        except (json.JSONDecodeError, Exception) as e:
            # Return minimal valid output on error
            return QueryPlannerOutput(
                intent="search",
                filters=[],
                sort_by="created_at",
                sort_order="desc",
                limit=20
            )
    
    def _validate_and_convert(self, data: dict) -> QueryPlannerOutput:
        """Validate and convert raw LLM output to typed output."""
        # Validate intent
        intent = data.get("intent", "search").lower()
        if intent not in ["buy", "rent", "search"]:
            intent = "search"
        
        # Parse and validate filters
        filters = []
        raw_filters = data.get("filters", [])
        
        for f in raw_filters:
            if not isinstance(f, dict):
                continue
            
            field = f.get("field", "").lower()
            op = f.get("operator", "=")
            value = f.get("value")
            
            # Skip invalid filters
            if not field or value is None:
                continue
            
            # Normalize operator
            op_map = {
                "=": QueryFilterOperator.EQ,
                "==": QueryFilterOperator.EQ,
                "!=": QueryFilterOperator.NE,
                "<>": QueryFilterOperator.NE,
                ">": QueryFilterOperator.GT,
                ">=": QueryFilterOperator.GTE,
                "<": QueryFilterOperator.LT,
                "<=": QueryFilterOperator.LTE,
                "like": QueryFilterOperator.LIKE,
                "in": QueryFilterOperator.IN,
            }
            
            operator = op_map.get(op.lower(), QueryFilterOperator.EQ)
            
            filters.append(QueryFilter(
                field=field,
                operator=operator,
                value=value
            ))
        
        # Validate sort
        sort_by = data.get("sort_by", "created_at")
        sort_order = data.get("sort_order", "desc").lower()
        if sort_order not in ["asc", "desc"]:
            sort_order = "desc"
        
        # Validate limit
        limit = data.get("limit", 20)
        if not isinstance(limit, int) or limit < 1:
            limit = 20
        limit = min(limit, settings.max_query_results)
        
        return QueryPlannerOutput(
            intent=intent,
            filters=filters,
            sort_by=sort_by,
            sort_order=sort_order,
            limit=limit
        )
    
    def format_for_user(self, query_plan: QueryPlannerOutput) -> str:
        """Format query plan for user confirmation."""
        parts = []
        
        # Intent
        intent_map = {
            "buy": "🏠 Looking to BUY",
            "rent": "🔑 Looking to RENT",
            "search": "🔍 Searching properties"
        }
        parts.append(intent_map.get(query_plan.intent, "Searching"))
        
        # Filters
        if query_plan.filters:
            parts.append("\nFilters applied:")
            for f in query_plan.filters:
                op_display = {
                    QueryFilterOperator.EQ: "=",
                    QueryFilterOperator.NE: "≠",
                    QueryFilterOperator.GT: ">",
                    QueryFilterOperator.GTE: "≥",
                    QueryFilterOperator.LT: "<",
                    QueryFilterOperator.LTE: "≤",
                    QueryFilterOperator.LIKE: "contains",
                    QueryFilterOperator.IN: "in",
                }
                parts.append(f"  • {f.field} {op_display.get(f.operator, '=')} {f.value}")
        
        return "\n".join(parts)


# Singleton instance
query_planner_agent = QueryPlannerAgent()
