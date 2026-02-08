"""
Natural Language Query API router.
Converts user queries to safe SQL via the Query Planner Agent.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import NaturalLanguageQuery, QueryResponse
from app.agents import query_planner_agent
from app.services.query_builder import SecureQueryBuilder, QueryBuilderError

router = APIRouter(prefix="/query", tags=["search"])


@router.post("/search", response_model=QueryResponse)
async def search_properties(
    query: NaturalLanguageQuery,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    Search properties using natural language.
    
    The query is processed by the Query Planner Agent to extract
    structured filters, which are then validated and executed safely.
    
    Example queries:
    - "2BHK flat for rent in Mumbai under 30k"
    - "Looking to buy a villa in Pune with parking"
    - "3 bedroom apartment near metro station"
    """
    try:
        # Step 1: Use Query Planner Agent to convert NL to filters
        query_plan = await query_planner_agent.plan_query(query.query)
        
        # Step 2: Use secure query builder to execute
        builder = SecureQueryBuilder(db)
        properties, total = await builder.build_and_execute(
            query_plan=query_plan,
            page=page,
            page_size=page_size
        )
        
        return QueryResponse(
            query=query.query,
            interpreted_as=query_plan,
            results=list(properties),
            total_count=total
        )
        
    except QueryBuilderError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid search query: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Search failed. Please try again."
        )


@router.post("/parse")
async def parse_query(query: NaturalLanguageQuery):
    """
    Parse a natural language query without executing.
    Useful for debugging and showing users how their query was interpreted.
    """
    try:
        query_plan = await query_planner_agent.plan_query(query.query)
        
        # Format for user display
        interpretation = query_planner_agent.format_for_user(query_plan)
        
        return {
            "query": query.query,
            "parsed": query_plan.model_dump(),
            "human_readable": interpretation
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse query"
        )
