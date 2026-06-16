"""
Query parser for advanced filtering and sorting.
Supports filter syntax with AND (&&) and OR (||) operators.

Supported Operators:
  =    Equal
  !=   Not equal
  >    Greater than
  <    Less than
  >=   Greater than or equal
  <=   Less than or equal
  ~    Like (contains)
  !~   Not like (does not contain)
  ?=   Any equal (for arrays)
  ?!=  Any not equal (for arrays)
  ?>   Any greater than (for arrays)
  ?>=  Any greater than or equal (for arrays)
  ?<   Any less than (for arrays)
  ?<=  Any less than or equal (for arrays)
  ?~   Any like (for arrays)
  ?!~  Any not like (for arrays)

Special Functions:
  geoDistance(field, lat, lng) <= distance   Filter by distance from point (km)
  geoDistance(field, lat, lng, "mi") <= distance   Filter by distance in miles

DateTime Macros:
  @now          Current datetime
  @today        Start of current day (00:00:00)
  @yesterday    Start of yesterday
  @tomorrow     Start of tomorrow
  @todayStart   Same as @today
  @todayEnd     End of current day (23:59:59)
  @monthStart   Start of current month
  @monthEnd     End of current month
  @yearStart    Start of current year
  @yearEnd      End of current year

Relative DateTime Offsets (can be positive or negative):
  @second+N / @second-N   Add/subtract N seconds
  @minute+N / @minute-N   Add/subtract N minutes
  @hour+N / @hour-N       Add/subtract N hours
  @day+N / @day-N         Add/subtract N days
  @week+N / @week-N       Add/subtract N weeks
  @month+N / @month-N     Add/subtract N months
  @year+N / @year-N       Add/subtract N years

Field Modifiers:
  :isset       Check if value is set (not null/empty)
  :length      Get length of string/array
  :lower       Convert to lowercase
  :upper       Convert to uppercase
  :excerpt(N)  Truncate to N characters with ellipsis
"""

import re
from app.utils.timeutils import utcnow
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from dateutil.relativedelta import relativedelta

from app.schemas.record import RecordFilter


class GeoDistanceFilter:
    """
    Represents a geoDistance filter for filtering by distance from a point.

    Usage: geoDistance(field, lat, lng) <= distance
           geoDistance(field, lat, lng, "mi") <= distance
    """

    def __init__(
        self,
        field: str,
        lat: float,
        lng: float,
        operator: str,
        distance: float,
        unit: str = "km"
    ):
        self.field = field
        self.lat = lat
        self.lng = lng
        self.operator = operator  # "lte", "lt", "gte", "gt", "eq"
        self.distance = distance
        self.unit = unit  # "km" or "mi"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "geo_distance",
            "field": self.field,
            "lat": self.lat,
            "lng": self.lng,
            "operator": self.operator,
            "distance": self.distance,
            "unit": self.unit,
        }


class NestedRelationFilter:
    """
    Represents a filter on a nested relation field.

    Usage: author.name = "John"  (filter by related record's field)
           posts.title ~ "Python"
           company.employees.name = "John"  (multi-level nesting)

    This filter requires a JOIN to the related collection to filter
    by the related record's field value.
    """

    def __init__(
        self,
        relation_path: List[str],  # e.g., ["author"] or ["company", "employees"]
        target_field: str,  # e.g., "name"
        operator: str,
        value: Any,
        modifiers: Optional[List[str]] = None,
    ):
        self.relation_path = relation_path  # Path through relations
        self.target_field = target_field  # Field on the target record
        self.operator = operator
        self.value = value
        self.modifiers = modifiers or []

    @property
    def relation_field(self) -> str:
        """Get the immediate relation field name."""
        return self.relation_path[0] if self.relation_path else ""

    @property
    def full_field_path(self) -> str:
        """Get the full dotted field path."""
        return ".".join(self.relation_path + [self.target_field])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "nested_relation",
            "relation_path": self.relation_path,
            "target_field": self.target_field,
            "operator": self.operator,
            "value": self.value,
            "modifiers": self.modifiers,
        }


class FilterGroup:
    """Represents a group of filters with logical operators."""

    def __init__(self, operator: str = "AND"):
        """
        Initialize filter group.

        Args:
            operator: Logical operator ('AND' or 'OR')
        """
        self.operator = operator  # 'AND' or 'OR'
        self.filters: List[Union[RecordFilter, "FilterGroup", GeoDistanceFilter, NestedRelationFilter]] = []

    def add_filter(self, filter_obj: Union[RecordFilter, "FilterGroup", GeoDistanceFilter, NestedRelationFilter]):
        """Add a filter or subgroup to this group."""
        self.filters.append(filter_obj)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "operator": self.operator,
            "filters": [
                f.to_dict() if hasattr(f, 'to_dict') else f.model_dump()
                for f in self.filters
            ],
        }


class QueryParser:
    """Parse query strings for filtering and sorting."""

    # Map query operators to internal filter operators
    # Order matters: longer operators must come first in regex pattern
    OPERATOR_MAP = {
        # Standard operators
        ">=": "gte",
        "<=": "lte",
        "!=": "ne",
        "!~": "not_like",
        "=": "eq",
        ">": "gt",
        "<": "lt",
        "~": "like",
        # Array/Any operators (for multi-value fields)
        "?>=": "any_gte",
        "?<=": "any_lte",
        "?!=": "any_ne",
        "?!~": "any_not_like",
        "?=": "any_eq",
        "?>": "any_gt",
        "?<": "any_lt",
        "?~": "any_like",
    }

    # DateTime macro patterns
    DATETIME_MACROS = {
        "@now": lambda: utcnow(),
        "@today": lambda: utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
        "@yesterday": lambda: utcnow().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=1),
        "@tomorrow": lambda: utcnow().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1),
        "@todayStart": lambda: utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
        "@todayEnd": lambda: utcnow().replace(hour=23, minute=59, second=59, microsecond=999999),
        "@monthStart": lambda: utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0),
        "@monthEnd": lambda: (utcnow().replace(day=1, hour=23, minute=59, second=59, microsecond=999999) + relativedelta(months=1) - timedelta(days=1)),
        "@yearStart": lambda: utcnow().replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0),
        "@yearEnd": lambda: utcnow().replace(month=12, day=31, hour=23, minute=59, second=59, microsecond=999999),
    }

    # Relative offset patterns (e.g., @day+7, @hour-2)
    RELATIVE_OFFSET_UNITS = {
        "@second": lambda n: timedelta(seconds=n),
        "@minute": lambda n: timedelta(minutes=n),
        "@hour": lambda n: timedelta(hours=n),
        "@day": lambda n: timedelta(days=n),
        "@week": lambda n: timedelta(weeks=n),
        "@month": lambda n: relativedelta(months=n),
        "@year": lambda n: relativedelta(years=n),
    }

    @classmethod
    def parse_filter(cls, filter_string: str) -> Union[List[RecordFilter], FilterGroup]:
        """
        Parse filter string into RecordFilter objects or FilterGroup.

        Supported formats:
        - field=value
        - field>value
        - field<value
        - field>=value
        - field<=value
        - field!=value
        - field~value (LIKE)
        - Multiple filters with &&: age>=18&&status=active (AND)
        - Multiple filters with ||: age>=18||status=active (OR)
        - Mixed: (age>=18&&status=active)||(age<10) (grouped)

        Args:
            filter_string: Filter expression

        Returns:
            List of RecordFilter objects (simple case) or FilterGroup (complex case)
        """
        if not filter_string or not filter_string.strip():
            return []

        # Check if expression contains OR operator
        if "||" in filter_string:
            return cls._parse_complex_filter(filter_string)

        # Simple case: only AND operators
        return cls._parse_simple_and_filter(filter_string)

    @classmethod
    def _parse_simple_and_filter(cls, filter_string: str) -> List[RecordFilter]:
        """Parse simple AND-only filter expressions."""
        filters: List[RecordFilter] = []

        # Split by && (AND operator)
        parts = filter_string.split("&&")

        for part in parts:
            part = part.strip()
            if not part:
                continue

            filter_obj = cls._parse_single_filter(part)
            if filter_obj:
                filters.append(filter_obj)

        return filters

    @classmethod
    def _parse_complex_filter(cls, filter_string: str) -> FilterGroup:
        """
        Parse complex filter expressions with OR operators.

        This handles expressions like:
        - age>=18||status=active (simple OR)
        - (age>=18&&status=active)||(age<10) (grouped OR with AND)
        """
        # First split by || to get OR groups
        or_parts = filter_string.split("||")

        if len(or_parts) == 1:
            # No OR, just return AND group
            root_group = FilterGroup("AND")
            filters = cls._parse_simple_and_filter(or_parts[0])
            for f in filters:
                root_group.add_filter(f)
            return root_group

        # Multiple OR parts
        root_group = FilterGroup("OR")

        for or_part in or_parts:
            or_part = or_part.strip()
            if not or_part:
                continue

            # Check if this part has AND operators
            if "&&" in or_part:
                # Create an AND subgroup
                and_group = FilterGroup("AND")
                and_filters = cls._parse_simple_and_filter(or_part)
                for f in and_filters:
                    and_group.add_filter(f)
                root_group.add_filter(and_group)
            else:
                # Single filter in this OR part
                filter_obj = cls._parse_single_filter(or_part)
                if filter_obj:
                    root_group.add_filter(filter_obj)

        return root_group

    @classmethod
    def _parse_single_filter(cls, filter_expr: str) -> Optional[Union[RecordFilter, GeoDistanceFilter, NestedRelationFilter]]:
        """
        Parse a single filter expression.

        Args:
            filter_expr: Single filter like "age>=18" or "created>@yesterday"
                        or "geoDistance(location, 40.7128, -74.0060)<=10"
                        or "author.name=John" (nested relation filter)

        Returns:
            RecordFilter, GeoDistanceFilter, NestedRelationFilter, or None if invalid
        """
        filter_expr = filter_expr.strip()

        # Remove parentheses if present
        if filter_expr.startswith("(") and filter_expr.endswith(")"):
            filter_expr = filter_expr[1:-1].strip()

        # Check for geoDistance function
        geo_filter = cls._parse_geo_distance(filter_expr)
        if geo_filter:
            return geo_filter

        # Build regex pattern from operators (longer operators first to avoid partial matches)
        # Sort by length descending to match longer operators first
        operators_sorted = sorted(cls.OPERATOR_MAP.keys(), key=len, reverse=True)
        operators_pattern = "|".join(re.escape(op) for op in operators_sorted)

        # Match pattern: field operator value
        # Field can include dots for nested fields (e.g., user.name, @request.auth.id)
        pattern = rf"^([\w.@:]+)\s*({operators_pattern})\s*(.+)$"
        match = re.match(pattern, filter_expr)

        if not match:
            return None

        field_expr, operator, value_str = match.groups()

        # Parse field with modifiers (e.g., name:lower, tags:length)
        field, modifiers = cls.parse_field_with_modifiers(field_expr)

        # Map operator to internal format
        operator_internal = cls.OPERATOR_MAP.get(operator)
        if not operator_internal:
            return None

        # Parse value (including DateTime macros)
        value = cls._parse_value(value_str.strip())

        # Check if this is a nested relation filter (field contains dot but isn't a special field)
        # Special fields start with @ (like @request.auth.id)
        if "." in field and not field.startswith("@"):
            return cls._parse_nested_relation_filter(field, operator_internal, value, modifiers)

        return RecordFilter(field=field, operator=operator_internal, value=value, modifiers=modifiers)

    @classmethod
    def _parse_nested_relation_filter(
        cls,
        field_path: str,
        operator: str,
        value: Any,
        modifiers: Optional[List[str]] = None
    ) -> NestedRelationFilter:
        """
        Parse a nested relation filter from a dotted field path.

        Args:
            field_path: Dotted field path like "author.name" or "company.employees.name"
            operator: Filter operator
            value: Filter value
            modifiers: Field modifiers

        Returns:
            NestedRelationFilter object
        """
        parts = field_path.split(".")

        # Last part is the target field on the related record
        target_field = parts[-1]

        # All preceding parts form the relation path
        relation_path = parts[:-1]

        return NestedRelationFilter(
            relation_path=relation_path,
            target_field=target_field,
            operator=operator,
            value=value,
            modifiers=modifiers,
        )

    @classmethod
    def _parse_geo_distance(cls, filter_expr: str) -> Optional[GeoDistanceFilter]:
        """
        Parse geoDistance function filter.

        Formats:
        - geoDistance(field, lat, lng) <= distance
        - geoDistance(field, lat, lng, "mi") <= distance
        - geoDistance(field, lat, lng, "km") >= distance

        Returns:
            GeoDistanceFilter or None if not a geoDistance expression
        """
        # Pattern: geoDistance(field, lat, lng[, "unit"]) operator distance
        pattern = r'^geoDistance\s*\(\s*(\w+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)(?:\s*,\s*["\'](\w+)["\'])?\s*\)\s*(<=|<|>=|>|=)\s*([-\d.]+)$'
        match = re.match(pattern, filter_expr, re.IGNORECASE)

        if not match:
            return None

        field, lat_str, lng_str, unit, operator, distance_str = match.groups()

        try:
            lat = float(lat_str)
            lng = float(lng_str)
            distance = float(distance_str)
        except ValueError:
            return None

        # Map operator to internal format
        op_map = {"<=": "lte", "<": "lt", ">=": "gte", ">": "gt", "=": "eq"}
        operator_internal = op_map.get(operator, "lte")

        # Default unit is km
        unit = unit if unit else "km"

        return GeoDistanceFilter(
            field=field,
            lat=lat,
            lng=lng,
            operator=operator_internal,
            distance=distance,
            unit=unit
        )

    @classmethod
    def _parse_value(cls, value_str: str) -> Any:
        """
        Parse value string to appropriate type.

        Supports:
        - Quoted strings: "value" or 'value'
        - Booleans: true, false
        - Null: null, none
        - Numbers: integers and floats
        - DateTime macros: @now, @today, @yesterday, etc.
        - Relative DateTime offsets: @day+7, @hour-2, etc.
        - Arrays: [value1, value2, value3]
        """
        # Remove quotes if present
        if (value_str.startswith('"') and value_str.endswith('"')) or (
            value_str.startswith("'") and value_str.endswith("'")
        ):
            return value_str[1:-1]

        # Check for DateTime macros
        if value_str.startswith("@"):
            datetime_value = cls._parse_datetime_macro(value_str)
            if datetime_value is not None:
                # Return datetime object so SQLAlchemy binds it as a real
                # parameter. Returning .isoformat() produces 'T'-separated
                # text that mismatches SQLite's space-separated DATETIME
                # storage and breaks same-day comparisons.
                return datetime_value

        # Boolean
        if value_str.lower() == "true":
            return True
        if value_str.lower() == "false":
            return False

        # Null
        if value_str.lower() in ("null", "none"):
            return None

        # Array (comma-separated values in brackets)
        if value_str.startswith("[") and value_str.endswith("]"):
            inner = value_str[1:-1].strip()
            if not inner:
                return []
            # Split by comma and parse each value
            items = [item.strip() for item in inner.split(",")]
            return [cls._parse_value(item) for item in items if item]

        # Number
        try:
            if "." in value_str:
                return float(value_str)
            return int(value_str)
        except ValueError:
            pass

        # Default to string
        return value_str

    @classmethod
    def _parse_datetime_macro(cls, macro_str: str) -> Optional[datetime]:
        """
        Parse DateTime macro string to datetime object.

        Args:
            macro_str: DateTime macro like @now, @today, @day+7, etc.

        Returns:
            datetime object or None if not a valid macro
        """
        macro_str = macro_str.strip()

        # Check for simple macros first
        if macro_str in cls.DATETIME_MACROS:
            return cls.DATETIME_MACROS[macro_str]()

        # Check for relative offset macros (e.g., @day+7, @hour-2)
        relative_pattern = r"^(@\w+)([+-])(\d+)$"
        match = re.match(relative_pattern, macro_str)
        if match:
            unit, sign, amount_str = match.groups()
            amount = int(amount_str)
            if sign == "-":
                amount = -amount

            if unit in cls.RELATIVE_OFFSET_UNITS:
                offset = cls.RELATIVE_OFFSET_UNITS[unit](amount)
                now = utcnow()
                # Handle both timedelta and relativedelta
                return now + offset

        return None

    @classmethod
    def parse_sort(cls, sort_string: str) -> tuple[Optional[str], str]:
        """
        Parse sort string (single field).

        Formats:
        - field (ascending)
        - -field (descending)
        - +field (ascending)

        Args:
            sort_string: Sort expression

        Returns:
            Tuple of (field, order)
        """
        if not sort_string or not sort_string.strip():
            return None, "asc"

        sort_string = sort_string.strip()

        if sort_string.startswith("-"):
            return sort_string[1:], "desc"
        elif sort_string.startswith("+"):
            return sort_string[1:], "asc"
        else:
            return sort_string, "asc"

    @classmethod
    def parse_multi_sort(cls, sort_string: str) -> Optional[list[tuple[str, str]]]:
        """
        Parse multi-field sort string.

        Formats:
        - field (ascending)
        - -field (descending)
        - +field (ascending)
        - -field1,+field2,field3 (multi-field)
        - @random (random order)

        Args:
            sort_string: Sort expression (comma-separated for multi-field)

        Returns:
            List of (field, order) tuples, or [("@random", "asc")] for random sort
        """
        if not sort_string or not sort_string.strip():
            return None

        sort_string = sort_string.strip()

        # Handle @random special case
        if sort_string.lower() == "@random":
            return [("@random", "asc")]

        # Split by comma for multi-field sort
        parts = [p.strip() for p in sort_string.split(",") if p.strip()]
        if not parts:
            return None

        result = []
        for part in parts:
            if part.startswith("-"):
                result.append((part[1:], "desc"))
            elif part.startswith("+"):
                result.append((part[1:], "asc"))
            else:
                result.append((part, "asc"))

        return result if result else None

    @classmethod
    def apply_filter_modifiers(cls, value: Any, modifiers: list[str]) -> Any:
        """
        Apply filter modifiers to a value.

        Supported modifiers:
        - :isset - Check if value is set (not None/empty)
        - :length - Get length of string/array
        - :lower - Convert to lowercase
        - :upper - Convert to uppercase
        - :excerpt(N) - Truncate to N characters with ellipsis
        - :each - Apply subsequent modifiers to each element (for arrays)

        Args:
            value: The value to modify
            modifiers: List of modifiers to apply

        Returns:
            Modified value
        """
        # Check if :each modifier is present - it changes how we process
        each_index = -1
        for i, mod in enumerate(modifiers):
            if mod.lower().strip() == "each":
                each_index = i
                break

        # If :each is present and value is a list, apply remaining modifiers to each element
        if each_index >= 0 and isinstance(value, list):
            # Apply modifiers before :each to the whole value
            for modifier in modifiers[:each_index]:
                value = cls._apply_single_modifier(value, modifier)

            # Apply modifiers after :each to each element
            remaining_modifiers = modifiers[each_index + 1:]
            if remaining_modifiers:
                value = [
                    cls.apply_filter_modifiers(item, remaining_modifiers)
                    for item in value
                ]
            return value

        # Normal processing without :each
        for modifier in modifiers:
            value = cls._apply_single_modifier(value, modifier)

        return value

    @classmethod
    def _apply_single_modifier(cls, value: Any, modifier: str) -> Any:
        """Apply a single modifier to a value."""
        mod_lower = modifier.lower().strip()

        if mod_lower == "isset":
            if value is None:
                return False
            if isinstance(value, str) and value == "":
                return False
            if isinstance(value, (list, dict)) and len(value) == 0:
                return False
            return True

        elif mod_lower == "length":
            if value is None:
                return 0
            if isinstance(value, (str, list, dict)):
                return len(value)
            return 0

        elif mod_lower == "lower":
            if isinstance(value, str):
                return value.lower()
            return value

        elif mod_lower == "upper":
            if isinstance(value, str):
                return value.upper()
            return value

        elif mod_lower.startswith("excerpt"):
            # Parse excerpt(N) or excerpt(N, "...") format
            return cls._apply_excerpt_modifier(value, modifier)

        elif mod_lower == "each":
            # :each is handled specially in apply_filter_modifiers
            return value

        return value

    @classmethod
    def _apply_excerpt_modifier(cls, value: Any, modifier: str) -> Any:
        """
        Apply excerpt modifier to truncate strings.

        Formats:
        - excerpt(100) - Truncate to 100 chars with "..." suffix
        - excerpt(100, ">>") - Truncate to 100 chars with custom suffix

        Args:
            value: The value to excerpt
            modifier: The modifier string like "excerpt(100)"

        Returns:
            Truncated string or original value if not a string
        """
        if not isinstance(value, str):
            return value

        # Parse excerpt(N) or excerpt(N, "suffix")
        pattern = r'excerpt\s*\(\s*(\d+)(?:\s*,\s*["\'](.+)["\'])?\s*\)'
        match = re.match(pattern, modifier, re.IGNORECASE)

        if not match:
            return value

        max_length = int(match.group(1))
        suffix = match.group(2) if match.group(2) else "..."

        if len(value) <= max_length:
            return value

        # Truncate and add suffix
        return value[:max_length - len(suffix)] + suffix

    @classmethod
    def parse_field_with_modifiers(cls, field_expr: str) -> tuple[str, list[str]]:
        """
        Parse a field expression that may include modifiers.

        Examples:
        - "name" -> ("name", [])
        - "name:lower" -> ("name", ["lower"])
        - "tags:length" -> ("tags", ["length"])
        - "email:isset" -> ("email", ["isset"])

        Args:
            field_expr: Field expression with optional modifiers

        Returns:
            Tuple of (field_name, list_of_modifiers)
        """
        if ":" not in field_expr:
            return field_expr, []

        parts = field_expr.split(":")
        field_name = parts[0]
        modifiers = [m.strip() for m in parts[1:] if m.strip()]

        return field_name, modifiers
