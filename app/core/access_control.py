"""
Access control engine for evaluating permission rules.

Rules syntax:
- null/empty: Public access
- "@request.auth.id != ''": Authenticated users only
- "@request.auth.id = @record.user_id": Owner only
- "@request.auth.role = 'admin'": Admin only
- Complex: "(@request.auth.id = @record.user_id || @request.auth.role = 'admin')"

Extended @request variables:
- @request.auth.id: Current user ID
- @request.auth.role: Current user role
- @request.auth.verified: Whether user is authenticated
- @request.data.*: Request body data
- @request.headers.*: Request headers (lowercase)
- @request.query.*: Query parameters
- @request.method: HTTP method (GET, POST, etc.)
- @request.context: Request context type (default, oauth2, realtime, expand, batch, protectedFile)

Context types:
- "default": Regular API request
- "oauth2": OAuth2 authentication flow
- "realtime": SSE/WebSocket subscription
- "expand": Expand relation fetch
- "batch": Batch operation
- "protectedFile": Protected file access
"""

import re
from typing import Any, Dict, Optional

from app.core.exceptions import ForbiddenException


class RequestContextType:
    """Request context type constants."""
    DEFAULT = "default"        # Regular API request
    OAUTH2 = "oauth2"          # OAuth2 authentication flow
    REALTIME = "realtime"      # SSE/WebSocket subscription
    EXPAND = "expand"          # Expand relation fetch
    BATCH = "batch"            # Batch operation
    PROTECTED_FILE = "protectedFile"  # Protected file access


class AccessContext:
    """Context for access control evaluation."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        user_role: str = "user",
        record_data: Optional[dict[str, Any]] = None,
        request_data: Optional[dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        query_params: Optional[Dict[str, str]] = None,
        method: str = "GET",
        context: str = "default",
        collection_data: Optional[Dict[str, list]] = None,
        db_session: Optional[Any] = None,
        old_record_data: Optional[dict[str, Any]] = None,
    ):
        self.user_id = user_id
        self.user_role = user_role
        self.record_data = record_data or {}
        self.request_data = request_data or {}
        self.headers = headers or {}
        self.query_params = query_params or {}
        self.method = method.upper()
        self.context = context  # Request context type
        # Cache for @collection lookups: {"collection_name": [{"field": value, ...}]}
        self.collection_data = collection_data or {}
        # Database session for async @collection lookups
        self.db_session = db_session
        # Previous record state for :changed modifier support
        self.old_record_data: dict[str, Any] = old_record_data or {}

    @property
    def is_authenticated(self) -> bool:
        return self.user_id is not None

    @property
    def is_admin(self) -> bool:
        return self.user_role == "admin"


class AccessControlEngine:
    """Engine for evaluating access control rules."""

    def __init__(self):
        # Pattern for @request and @record tokens (with optional :changed modifier)
        self.token_pattern = re.compile(r"@(request|record)\.([a-zA-Z_][a-zA-Z0-9_.]*)(?::(\w+))?")
        # Pattern for @collection tokens: @collection.collection_name.field
        self.collection_pattern = re.compile(r"@collection\.([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_.]*)(?::(\w+))?")
        # Pattern for bare field:changed tokens (not prefixed with @record)
        self.changed_field_pattern = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*):changed\b")

    def evaluate(self, rule: Optional[str], context: AccessContext) -> bool:
        """
        Evaluate an access control rule.

        Args:
            rule: Access control rule expression
            context: Request and record context

        Returns:
            True if access is allowed, False otherwise
        """
        # Empty rule means public access
        if not rule or rule.strip() == "":
            return True

        # Replace tokens with actual values
        expression = self._replace_tokens(rule, context)

        # Evaluate the expression
        try:
            result = self._evaluate_expression(expression)
            return bool(result)
        except Exception:
            # If evaluation fails, deny access
            return False

    def check(self, rule: Optional[str], context: AccessContext, operation: str = "access"):
        """
        Check access and raise exception if denied.

        Args:
            rule: Access control rule
            context: Request and record context
            operation: Operation name for error message

        Raises:
            ForbiddenException: If access is denied
        """
        if not self.evaluate(rule, context):
            raise ForbiddenException(f"Access denied for {operation} operation")

    async def evaluate_async(self, rule: Optional[str], context: AccessContext) -> bool:
        """
        Async version of evaluate that supports @collection lookups.

        Use this when the rule contains @collection references that require
        database queries to resolve.

        Args:
            rule: Access control rule expression
            context: Request and record context (must include db_session for @collection)

        Returns:
            True if access is allowed, False otherwise
        """
        # Empty rule means public access
        if not rule or rule.strip() == "":
            return True

        # Check if rule contains @collection references
        if "@collection." in rule:
            # Pre-fetch collection data if db session available
            if context.db_session:
                await self._prefetch_collection_data(rule, context)

        # Replace tokens with actual values (including @collection)
        expression = self._replace_tokens_with_collection(rule, context)

        # Evaluate the expression
        try:
            result = self._evaluate_expression(expression)
            return bool(result)
        except Exception:
            # If evaluation fails, deny access
            return False

    async def check_async(
        self, rule: Optional[str], context: AccessContext, operation: str = "access"
    ):
        """
        Async check access and raise exception if denied.

        Args:
            rule: Access control rule
            context: Request and record context
            operation: Operation name for error message

        Raises:
            ForbiddenException: If access is denied
        """
        if not await self.evaluate_async(rule, context):
            raise ForbiddenException(f"Access denied for {operation} operation")

    async def _prefetch_collection_data(self, rule: str, context: AccessContext):
        """
        Pre-fetch @collection data needed for rule evaluation.

        Args:
            rule: Rule containing @collection references
            context: Access context with db_session
        """
        # Find all @collection references
        matches = self.collection_pattern.findall(rule)

        for collection_name, field_path in matches:
            # Skip if already cached
            cache_key = f"{collection_name}.{field_path}"
            if cache_key in context.collection_data:
                continue

            try:
                from app.db.repositories.record import RecordRepository

                repo = RecordRepository(context.db_session, collection_name)
                records = await repo.get_all(limit=1000)  # Reasonable limit

                # Extract the field values from all records
                base_field = field_path.split(".")[0]
                values = []
                for record in records:
                    record_dict = record.to_dict() if hasattr(record, 'to_dict') else {}
                    if base_field in record_dict:
                        values.append(record_dict[base_field])

                context.collection_data[cache_key] = values

            except Exception:
                # If collection doesn't exist or query fails, use empty list
                context.collection_data[cache_key] = []

    def _replace_tokens(self, rule: str, context: AccessContext) -> str:
        """Replace @request and @record tokens with actual values."""

        # First handle bare field:changed patterns (e.g., status:changed = true)
        def replace_changed_field(match: re.Match) -> str:
            field = match.group(1)
            old_val = context.old_record_data.get(field)
            new_val = context.record_data.get(field)
            changed = old_val != new_val
            return "True" if changed else "False"

        rule = self.changed_field_pattern.sub(replace_changed_field, rule)

        def replace_token(match: re.Match) -> str:
            scope = match.group(1)  # request or record
            path = match.group(2)  # e.g., auth.id, user_id, data.title
            modifier = match.group(3)  # optional modifier like "changed"

            if modifier == "changed":
                # :changed — compare old vs. new value
                field = path.split(".")[-1]
                old_val = context.old_record_data.get(field)
                new_val = context.record_data.get(field)
                changed = old_val != new_val
                return "True" if changed else "False"

            if scope == "request":
                return self._get_request_value(path, context)
            elif scope == "record":
                return self._get_record_value(path, context)
            return "None"

        return self.token_pattern.sub(replace_token, rule)

    def _replace_tokens_with_collection(self, rule: str, context: AccessContext) -> str:
        """Replace all tokens including @collection references."""

        # First replace @collection tokens
        def replace_collection(match: re.Match) -> str:
            collection_name = match.group(1)
            field_path = match.group(2)
            cache_key = f"{collection_name}.{field_path}"

            values = context.collection_data.get(cache_key, [])
            # Format as a Python list for evaluation
            formatted_values = [f"'{v}'" if isinstance(v, str) else str(v) for v in values]
            return f"[{', '.join(formatted_values)}]"

        rule = self.collection_pattern.sub(replace_collection, rule)

        # Then replace @request and @record tokens
        return self._replace_tokens(rule, context)

    def _get_request_value(self, path: str, context: AccessContext) -> str:
        """Get value from request context."""
        if path == "auth.id":
            return f"'{context.user_id}'" if context.user_id else "''"
        elif path == "auth.role":
            return f"'{context.user_role}'"
        elif path == "auth.verified":
            return "True" if context.user_id else "False"
        elif path.startswith("data."):
            # Access request data fields
            key = path[5:]  # remove "data."
            return self._get_value_from_dict(context.request_data, key)
        elif path.startswith("headers."):
            # Access request headers (lowercase for consistency)
            key = path[8:].lower()  # remove "headers." and lowercase
            value = context.headers.get(key)
            return f"'{value}'" if value else "''"
        elif path.startswith("query."):
            # Access query parameters
            key = path[6:]  # remove "query."
            value = context.query_params.get(key)
            return f"'{value}'" if value else "''"
        elif path == "method":
            return f"'{context.method}'"
        elif path == "context":
            # Request context type (default, oauth2, realtime, expand, batch, protectedFile)
            return f"'{context.context}'"
        return "None"

    def _get_record_value(self, path: str, context: AccessContext) -> str:
        """Get value from record data."""
        return self._get_value_from_dict(context.record_data, path)

    def _get_value_from_dict(self, data: dict, path: str) -> str:
        """Helper to extract value from nested dict and format for expression."""
        keys = path.split(".")
        value = data

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return "None"

        if value is None:
            return "None"
        elif isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, bool):
            return str(value)
        elif isinstance(value, (int, float)):
            return str(value)
        return "None"



    def _evaluate_expression(self, expression: str) -> bool:
        """
        Safely evaluate a boolean expression.

        Only allows safe operations:
        - Comparisons: =, !=, <, >, <=, >=
        - Logical: &&, ||, !
        - Parentheses
        - List membership: ?= (any equal / in)
        """
        # Convert ?= operator to Python's `in` check
        # Pattern: value ?= [list] becomes value in [list]
        expression = re.sub(r"(\S+)\s*\?\s*=\s*(\[.*?\])", r"(\1 in \2)", expression)

        # Convert SQL-style operators to Python
        expression = expression.replace("&&", " and ")
        expression = expression.replace("||", " or ")
        # Handle != before = to avoid double replacement
        expression = re.sub(r"!=", " != ", expression)
        expression = re.sub(r"(?<![!<>=])=(?!=)", " == ", expression)

        # Only allow safe characters (including brackets for lists, commas)
        if not re.match(r"^[\w\s'\"()!=<>&|.,\[\]in]+$", expression):
            return False

        # Evaluate using eval (safe because we validated the expression)
        try:
            return eval(expression, {"__builtins__": {}}, {})
        except Exception:
            return False


# Global instance
access_control = AccessControlEngine()
