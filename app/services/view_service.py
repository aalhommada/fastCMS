"""
Service for view collection query execution.
View collections are virtual collections that compute data from other collections.
"""

from typing import Any, Dict, List, Optional, Tuple
from app.utils.timeutils import utcnow
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestException, NotFoundException
from app.core.logging import get_logger
from app.db.repositories.collection import CollectionRepository
from app.schemas.view import ViewOptions, ViewQuery, ViewJoin, ViewSelect, ViewAggregation

logger = get_logger(__name__)


class ViewQueryExecutor:
    """Executes queries for view collections."""

    def __init__(self, db: AsyncSession):
        """
        Initialize the executor.

        Args:
            db: Database session
        """
        self.db = db
        self.collection_repo = CollectionRepository(db)

    async def execute(
        self,
        view_name: str,
        query: ViewQuery,
        page: int = 1,
        per_page: int = 30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Execute a view query.

        Args:
            view_name: Name of the view collection
            query: Query definition
            page: Page number
            per_page: Items per page
            filters: Additional filters

        Returns:
            Tuple of (results, total_count)
        """
        # Validate source collection exists
        source_collection = await self.collection_repo.get_by_name(query.source)
        if not source_collection:
            raise NotFoundException(f"Source collection '{query.source}' not found")

        # Build SQL query
        sql_query = await self._build_sql(query, filters)
        count_query = await self._build_count_sql(query, filters)

        # Execute count query
        count_result = await self.db.execute(text(count_query))
        total = count_result.scalar() or 0

        # Add pagination
        offset = (page - 1) * per_page
        sql_query += f" LIMIT {per_page} OFFSET {offset}"

        # Execute main query
        logger.debug(f"Executing view query: {sql_query}")
        result = await self.db.execute(text(sql_query))
        rows = result.fetchall()

        # Convert rows to dictionaries
        results = []
        if rows:
            columns = result.keys()
            for row in rows:
                results.append(dict(zip(columns, row)))

        return results, total

    async def _build_sql(
        self,
        query: ViewQuery,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build SQL query from view definition.

        Args:
            query: View query definition
            filters: Additional filters

        Returns:
            SQL query string
        """
        # Build SELECT clause
        select_parts = []
        for field in query.select:
            if isinstance(field, str):
                select_parts.append(field)
            elif isinstance(field, ViewSelect):
                if field.aggregation:
                    # Aggregation function
                    func = field.aggregation.function
                    agg_field = field.aggregation.field
                    alias = field.aggregation.alias
                    select_parts.append(f"{func}({agg_field}) as {alias}")
                else:
                    # Regular field with optional alias
                    if field.alias:
                        select_parts.append(f"{field.field} as {field.alias}")
                    else:
                        select_parts.append(field.field)

        if not select_parts:
            select_parts.append("*")

        select_clause = ", ".join(select_parts)

        # Build FROM clause
        from_clause = query.source

        # Build JOIN clauses
        join_clauses = []
        for join in query.joins:
            join_type = join.type
            join_collection = join.collection
            join_alias = f" as {join.alias}" if join.alias else ""
            join_condition = join.on
            join_clauses.append(
                f"{join_type} JOIN {join_collection}{join_alias} ON {join_condition}"
            )

        # Build WHERE clause
        where_conditions = []
        if query.where:
            where_conditions.append(f"({query.where})")

        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    where_conditions.append(f"{key} = '{value}'")
                elif isinstance(value, bool):
                    where_conditions.append(f"{key} = {int(value)}")
                elif value is None:
                    where_conditions.append(f"{key} IS NULL")
                else:
                    where_conditions.append(f"{key} = {value}")

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # Build GROUP BY clause
        group_by_clause = ""
        if query.group_by:
            group_by_clause = "GROUP BY " + ", ".join(query.group_by)

        # Build ORDER BY clause
        order_by_clause = ""
        if query.order_by:
            order_parts = []
            for field in query.order_by:
                if field.startswith("-"):
                    order_parts.append(f"{field[1:]} DESC")
                else:
                    order_parts.append(f"{field} ASC")
            order_by_clause = "ORDER BY " + ", ".join(order_parts)

        # Combine all parts
        sql_parts = [f"SELECT {select_clause}", f"FROM {from_clause}"]

        if join_clauses:
            sql_parts.extend(join_clauses)

        if where_clause:
            sql_parts.append(where_clause)

        if group_by_clause:
            sql_parts.append(group_by_clause)

        if order_by_clause:
            sql_parts.append(order_by_clause)

        sql = " ".join(sql_parts)
        return sql

    async def _build_count_sql(
        self,
        query: ViewQuery,
        filters: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Build COUNT query for pagination.

        Args:
            query: View query definition
            filters: Additional filters

        Returns:
            COUNT SQL query string
        """
        # Build FROM clause
        from_clause = query.source

        # Build JOIN clauses
        join_clauses = []
        for join in query.joins:
            join_type = join.type
            join_collection = join.collection
            join_alias = f" as {join.alias}" if join.alias else ""
            join_condition = join.on
            join_clauses.append(
                f"{join_type} JOIN {join_collection}{join_alias} ON {join_condition}"
            )

        # Build WHERE clause
        where_conditions = []
        if query.where:
            where_conditions.append(f"({query.where})")

        if filters:
            for key, value in filters.items():
                if isinstance(value, str):
                    where_conditions.append(f"{key} = '{value}'")
                elif isinstance(value, bool):
                    where_conditions.append(f"{key} = {int(value)}")
                elif value is None:
                    where_conditions.append(f"{key} IS NULL")
                else:
                    where_conditions.append(f"{key} = {value}")

        where_clause = ""
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)

        # For grouped queries, use subquery to count groups
        if query.group_by:
            # Build subquery with the full query including GROUP BY
            group_by_clause = "GROUP BY " + ", ".join(query.group_by)
            subquery_parts = ["SELECT 1", f"FROM {from_clause}"]

            if join_clauses:
                subquery_parts.extend(join_clauses)

            if where_clause:
                subquery_parts.append(where_clause)

            subquery_parts.append(group_by_clause)

            subquery = " ".join(subquery_parts)
            select_clause = f"COUNT(*) FROM ({subquery})"
            # Clear parts for the outer query
            from_clause = ""
            join_clauses = []
            where_clause = ""
        else:
            select_clause = "COUNT(*)"

        # Combine parts
        sql_parts = [f"SELECT {select_clause}"]

        if from_clause:  # Only add FROM if not using subquery
            sql_parts.append(f"FROM {from_clause}")

        if join_clauses:
            sql_parts.extend(join_clauses)

        if where_clause:
            sql_parts.append(where_clause)

        sql = " ".join(sql_parts)
        return sql


class ViewCache:
    """Simple in-memory cache for view results."""

    def __init__(self):
        """Initialize cache."""
        self._cache: Dict[str, Tuple[List[Dict[str, Any]], int, datetime]] = {}

    def get(
        self,
        cache_key: str,
        ttl: int
    ) -> Optional[Tuple[List[Dict[str, Any]], int]]:
        """
        Get cached result if not expired.

        Args:
            cache_key: Cache key
            ttl: Time-to-live in seconds

        Returns:
            Cached result or None
        """
        if cache_key not in self._cache:
            return None

        results, total, timestamp = self._cache[cache_key]

        # Check if expired
        if ttl > 0 and (utcnow() - timestamp).total_seconds() > ttl:
            del self._cache[cache_key]
            return None

        return results, total

    def set(
        self,
        cache_key: str,
        results: List[Dict[str, Any]],
        total: int
    ) -> None:
        """
        Store result in cache.

        Args:
            cache_key: Cache key
            results: Query results
            total: Total count
        """
        self._cache[cache_key] = (results, total, utcnow())

    def invalidate(self, cache_key: str) -> None:
        """
        Invalidate cached result.

        Args:
            cache_key: Cache key
        """
        if cache_key in self._cache:
            del self._cache[cache_key]

    def clear(self) -> None:
        """Clear all cached results."""
        self._cache.clear()


# Global cache instance
_view_cache = ViewCache()


class ViewService:
    """Service for managing view collections."""

    def __init__(self, db: AsyncSession):
        """
        Initialize service.

        Args:
            db: Database session
        """
        self.db = db
        self.executor = ViewQueryExecutor(db)
        self.collection_repo = CollectionRepository(db)

    async def execute_view(
        self,
        view_name: str,
        page: int = 1,
        per_page: int = 30,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Execute a view and return results.

        Args:
            view_name: Name of the view collection
            page: Page number
            per_page: Items per page
            filters: Additional filters

        Returns:
            Tuple of (results, total_count)
        """
        # Get view collection
        collection = await self.collection_repo.get_by_name(view_name)
        if not collection:
            raise NotFoundException(f"View collection '{view_name}' not found")

        if collection.type != "view":
            raise BadRequestException(f"Collection '{view_name}' is not a view collection")

        # Parse view options
        options_data = collection.options or {}
        if "query" not in options_data:
            raise BadRequestException(f"View collection '{view_name}' has no query defined")

        query = ViewQuery(**options_data["query"])
        cache_ttl = options_data.get("cache_ttl", 300)

        # Check cache
        cache_key = f"{view_name}:{page}:{per_page}:{str(filters)}"
        cached = _view_cache.get(cache_key, cache_ttl)
        if cached:
            logger.debug(f"Returning cached results for view '{view_name}'")
            return cached

        # Execute query
        results, total = await self.executor.execute(
            view_name=view_name,
            query=query,
            page=page,
            per_page=per_page,
            filters=filters,
        )

        # Cache results if TTL > 0
        if cache_ttl > 0:
            _view_cache.set(cache_key, results, total)

        return results, total

    async def invalidate_view_cache(self, view_name: str) -> None:
        """
        Invalidate all cached results for a view.

        Args:
            view_name: Name of the view collection
        """
        # Simple approach: clear entire cache
        # In production, you'd want more granular invalidation
        _view_cache.clear()
        logger.debug(f"Cache invalidated for view '{view_name}'")
