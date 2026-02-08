"""
Secure Query Builder Service.
Converts LLM-generated JSON filters into safe, parameterized SQL queries.
This is the critical security layer - LLM never touches SQL directly.
"""

from typing import Any, List, Tuple, Optional
from decimal import Decimal
from sqlalchemy import select, and_, or_, desc, asc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models import Property, PropertyFeature, PropertyTransport
from app.schemas import QueryFilter, QueryFilterOperator, QueryPlannerOutput
from app.config import get_settings

settings = get_settings()


# =============================================================================
# FIELD WHITELIST - Only these fields can be queried
# =============================================================================

ALLOWED_FIELDS = {
    # Property main fields
    "listing_type": {"column": "listing_type", "type": "enum"},
    "property_type": {"column": "property_type", "type": "enum"},
    "price": {"column": "price", "type": "numeric"},
    "city": {"column": "city", "type": "string"},
    "locality": {"column": "locality", "type": "string"},
    "pincode": {"column": "pincode", "type": "string"},
    "bedrooms": {"column": "bedrooms", "type": "integer"},
    "bathrooms": {"column": "bathrooms", "type": "integer"},
    "balconies": {"column": "balconies", "type": "integer"},
    "carpet_area": {"column": "carpet_area", "type": "numeric"},
    "built_up_area": {"column": "built_up_area", "type": "numeric"},
    "super_built_up_area": {"column": "super_built_up_area", "type": "numeric"},
    "floor_number": {"column": "floor_number", "type": "integer"},
    "total_floors": {"column": "total_floors", "type": "integer"},
    "facing": {"column": "facing", "type": "string"},
    "age_of_property": {"column": "age_of_property", "type": "integer"},
    "furnishing": {"column": "furnishing", "type": "enum"},
    "status": {"column": "status", "type": "enum"},
    "preferred_tenant": {"column": "preferred_tenant", "type": "string"},
    "pets_allowed": {"column": "pets_allowed", "type": "boolean"},
    "security_deposit": {"column": "security_deposit", "type": "numeric"},
    "maintenance_monthly": {"column": "maintenance_monthly", "type": "numeric"},
}

# Feature fields (require join)
FEATURE_FIELDS = {
    "has_parking": "boolean",
    "has_lift": "boolean",
    "has_power_backup": "boolean",
    "has_gym": "boolean",
    "has_swimming_pool": "boolean",
    "has_ac": "boolean",
    "has_wifi": "boolean",
    "has_modular_kitchen": "boolean",
    "has_security": "boolean",
}

# Allowed operators per type
ALLOWED_OPERATORS = {
    "string": [QueryFilterOperator.EQ, QueryFilterOperator.NE, QueryFilterOperator.LIKE, QueryFilterOperator.IN],
    "integer": [QueryFilterOperator.EQ, QueryFilterOperator.NE, QueryFilterOperator.GT, 
                QueryFilterOperator.GTE, QueryFilterOperator.LT, QueryFilterOperator.LTE, QueryFilterOperator.IN],
    "numeric": [QueryFilterOperator.EQ, QueryFilterOperator.NE, QueryFilterOperator.GT, 
                QueryFilterOperator.GTE, QueryFilterOperator.LT, QueryFilterOperator.LTE],
    "boolean": [QueryFilterOperator.EQ],
    "enum": [QueryFilterOperator.EQ, QueryFilterOperator.NE, QueryFilterOperator.IN],
}


class QueryBuilderError(Exception):
    """Raised when query building fails due to invalid input."""
    pass


class SecureQueryBuilder:
    """
    Builds safe, parameterized SQL queries from validated filters.
    Never trusts LLM output directly - all fields and operators are validated.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.errors: List[str] = []
    
    def validate_filter(self, filter: QueryFilter) -> bool:
        """Validate a single filter against whitelist."""
        field = filter.field.lower()
        
        # Check if field is allowed
        if field not in ALLOWED_FIELDS and field not in FEATURE_FIELDS:
            self.errors.append(f"Field '{field}' is not allowed for querying")
            return False
        
        # Get field type
        if field in ALLOWED_FIELDS:
            field_type = ALLOWED_FIELDS[field]["type"]
        else:
            field_type = FEATURE_FIELDS[field]
        
        # Check if operator is allowed for this field type
        if filter.operator not in ALLOWED_OPERATORS.get(field_type, []):
            self.errors.append(f"Operator '{filter.operator}' not allowed for field '{field}'")
            return False
        
        return True
    
    def validate_filters(self, filters: List[QueryFilter]) -> bool:
        """Validate all filters."""
        self.errors = []
        
        # Check filter count limit
        if len(filters) > settings.max_filters_per_query:
            self.errors.append(f"Too many filters. Maximum allowed: {settings.max_filters_per_query}")
            return False
        
        # Validate each filter
        for f in filters:
            self.validate_filter(f)
        
        return len(self.errors) == 0
    
    def _apply_filter(self, query: Select, filter: QueryFilter) -> Select:
        """Apply a single filter to the query."""
        field = filter.field.lower()
        op = filter.operator
        value = filter.value
        
        # Get column reference
        if field in ALLOWED_FIELDS:
            column = getattr(Property, ALLOWED_FIELDS[field]["column"])
        else:
            # Feature field - will be handled with join
            column = getattr(PropertyFeature, field)
        
        # Apply operator
        if op == QueryFilterOperator.EQ:
            query = query.where(column == value)
        elif op == QueryFilterOperator.NE:
            query = query.where(column != value)
        elif op == QueryFilterOperator.GT:
            query = query.where(column > value)
        elif op == QueryFilterOperator.GTE:
            query = query.where(column >= value)
        elif op == QueryFilterOperator.LT:
            query = query.where(column < value)
        elif op == QueryFilterOperator.LTE:
            query = query.where(column <= value)
        elif op == QueryFilterOperator.LIKE:
            # Sanitize LIKE pattern
            safe_value = str(value).replace("%", "\\%").replace("_", "\\_")
            query = query.where(column.ilike(f"%{safe_value}%"))
        elif op == QueryFilterOperator.IN:
            if isinstance(value, list):
                query = query.where(column.in_(value))
            else:
                query = query.where(column == value)
        
        return query
    
    def _needs_feature_join(self, filters: List[QueryFilter]) -> bool:
        """Check if any filter requires feature table join."""
        return any(f.field.lower() in FEATURE_FIELDS for f in filters)
    
    async def build_and_execute(
        self,
        query_plan: QueryPlannerOutput,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20
    ) -> Tuple[List[Property], int]:
        """
        Build and execute the query from a validated query plan.
        Returns (results, total_count).
        """
        # Validate all filters
        if not self.validate_filters(query_plan.filters):
            raise QueryBuilderError(f"Invalid filters: {'; '.join(self.errors)}")
        
        # Limit page size
        page_size = min(page_size, settings.max_query_results)
        
        # Build base query
        query = select(Property).where(Property.status == "available")
        count_query = select(Property).where(Property.status == "available")
        
        # Add feature join if needed
        if self._needs_feature_join(query_plan.filters):
            query = query.join(PropertyFeature, Property.id == PropertyFeature.property_id, isouter=True)
            count_query = count_query.join(PropertyFeature, Property.id == PropertyFeature.property_id, isouter=True)
        
        # Apply intent-based filter (buy/rent)
        if query_plan.intent == "rent":
            query = query.where(Property.listing_type == "rent")
            count_query = count_query.where(Property.listing_type == "rent")
        elif query_plan.intent == "buy":
            query = query.where(Property.listing_type == "sell")
            count_query = count_query.where(Property.listing_type == "sell")
        
        # Apply all filters
        for filter in query_plan.filters:
            query = self._apply_filter(query, filter)
            count_query = self._apply_filter(count_query, filter)
        
        # Apply sorting
        if query_plan.sort_by and query_plan.sort_by in ALLOWED_FIELDS:
            sort_column = getattr(Property, ALLOWED_FIELDS[query_plan.sort_by]["column"])
            if query_plan.sort_order == "desc":
                query = query.order_by(desc(sort_column))
            else:
                query = query.order_by(asc(sort_column))
        else:
            # Default: newest first
            query = query.order_by(desc(Property.created_at))
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)
        
        # Execute queries
        result = await self.db.execute(query)
        properties = result.scalars().all()
        
        # Get total count
        from sqlalchemy import func
        count_result = await self.db.execute(
            select(func.count()).select_from(count_query.subquery())
        )
        total = count_result.scalar() or 0
        
        return list(properties), total


def sanitize_string(value: str) -> str:
    """Sanitize string input to prevent injection."""
    # Remove potentially dangerous characters
    dangerous_chars = [";", "--", "/*", "*/", "xp_", "sp_", "exec", "execute"]
    result = value
    for char in dangerous_chars:
        result = result.replace(char, "")
    return result[:500]  # Limit length
