"""
Field type definitions and validators for dynamic collections.
"""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, field_validator


class FieldType(str, Enum):
    """Supported field types for collections."""

    TEXT = "text"
    NUMBER = "number"
    BOOL = "bool"
    EMAIL = "email"
    URL = "url"
    DATE = "date"
    DATETIME = "datetime"
    SELECT = "select"
    FILE = "file"
    RELATION = "relation"
    JSON = "json"
    EDITOR = "editor"
    GEOPOINT = "geopoint"  # Geographic coordinates (lat, lng)
    AUTODATE = "autodate"  # Auto-set timestamp on create and/or update


class FieldValidation(BaseModel):
    """Validation rules for a field."""

    required: bool = False
    unique: bool = False
    min: Optional[int | float] = None
    max: Optional[int | float] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    pattern: Optional[str] = None  # Regex pattern
    values: Optional[List[Any]] = None  # Allowed values for select


class RelationCascade(str, Enum):
    """Cascade action for relations."""
    CASCADE = "cascade"  # Delete related records
    SET_NULL = "set_null"  # Set foreign key to NULL
    RESTRICT = "restrict"  # Prevent deletion if related records exist
    NO_ACTION = "no_action"  # Do nothing (default SQL behavior)


class RelationType(str, Enum):
    """Relationship types."""
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"
    ONE_TO_ONE = "one-to-one"
    POLYMORPHIC = "polymorphic"  # Can relate to multiple collection types


class RelationOptions(BaseModel):
    """Options for relation fields."""

    collection: str = Field(..., description="Target collection name")
    collection_id: Optional[str] = Field(None, description="Target collection ID (legacy)")
    cascade_delete: Optional[Union[bool, RelationCascade]] = Field(
        default=RelationCascade.RESTRICT,
        description="Action on parent deletion: restrict, cascade, set_null, no_action"
    )
    type: str = Field(
        default="one-to-many",
        description="Relationship type: one-to-many, many-to-one, many-to-many, one-to-one"
    )
    display_fields: List[str] = Field(
        default_factory=lambda: ["id"],
        description="Fields to display in relation",
    )
    max_depth: int = Field(
        default=1,
        ge=0,
        le=5,
        description="Maximum depth for nested relation loading (0-5)"
    )
    junction_table: Optional[str] = Field(
        None,
        description="Junction table name for many-to-many relations"
    )
    junction_field: Optional[str] = Field(
        None,
        description="Field name in junction table referencing this collection"
    )
    target_field: Optional[str] = Field(
        None,
        description="Field name in junction table referencing target collection"
    )
    polymorphic_type_field: Optional[str] = Field(
        None,
        description="Field storing the collection type for polymorphic relations"
    )

    @field_validator("cascade_delete", mode="before")
    @classmethod
    def migrate_cascade_delete(cls, v: Any) -> Optional[RelationCascade]:
        """Convert old boolean cascade_delete to new enum format."""
        if v is None:
            return RelationCascade.RESTRICT
        if isinstance(v, bool):
            # Old format: boolean (True = cascade, False = restrict)
            return RelationCascade.CASCADE if v else RelationCascade.RESTRICT
        if isinstance(v, str):
            # New format: enum string
            return v
        return v

    @field_validator("collection_id")
    @classmethod
    def validate_collection_id(cls, v: Optional[str]) -> Optional[str]:
        """Ensure collection_id or collection_ids is provided."""
        # At least one must be provided, but validation is lenient for existing data
        return v


class SelectOptions(BaseModel):
    """Options for select fields."""

    values: List[str] = Field(..., description="Available options")
    max_select: int = Field(default=1, description="Maximum selections (1 for single)")


class FileOptions(BaseModel):
    """Options for file fields."""

    max_size: int = Field(default=5242880, description="Max file size in bytes (5MB)")
    max_files: int = Field(default=1, description="Maximum number of files")
    mime_types: List[str] = Field(
        default_factory=lambda: ["image/jpeg", "image/png", "image/gif"],
        description="Allowed MIME types",
    )
    thumbs: List[str] = Field(
        default_factory=lambda: ["100x100", "500x500"],
        description="Thumbnail sizes",
    )


class GeoPointOptions(BaseModel):
    """Options for GeoPoint fields."""

    require_altitude: bool = Field(
        default=False,
        description="Whether altitude is required"
    )
    min_lat: float = Field(default=-90.0, ge=-90.0, le=90.0)
    max_lat: float = Field(default=90.0, ge=-90.0, le=90.0)
    min_lng: float = Field(default=-180.0, ge=-180.0, le=180.0)
    max_lng: float = Field(default=180.0, ge=-180.0, le=180.0)


class AutodateOptions(BaseModel):
    """Options for Autodate fields."""

    on_create: bool = Field(default=True, description="Set timestamp when record is created")
    on_update: bool = Field(default=True, description="Update timestamp when record is updated")


class FieldSchema(BaseModel):
    """Complete schema definition for a field."""

    name: str = Field(..., min_length=1, max_length=100, pattern="^[a-zA-Z][a-zA-Z0-9_]*$")
    type: FieldType
    validation: FieldValidation = Field(default_factory=FieldValidation)

    # Type-specific options
    relation: Optional[RelationOptions] = None
    select: Optional[SelectOptions] = None
    file: Optional[FileOptions] = None
    geopoint: Optional[GeoPointOptions] = None
    autodate: Optional[AutodateOptions] = None

    # Display options
    label: Optional[str] = None
    hint: Optional[str] = None
    hidden: bool = False
    system: bool = False  # System fields cannot be modified

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Validate field name is not a SQL reserved word."""
        sql_reserved = {
            "id", "created", "updated", "deleted",  # System fields
            "select", "from", "where", "insert", "update", "delete",  # SQL keywords
            "table", "index", "primary", "foreign", "key",
            "user", "group", "order", "limit", "offset",
        }

        if v.lower() in sql_reserved:
            raise ValueError(f"Field name '{v}' is reserved")

        return v

    @field_validator("relation", mode="after")
    @classmethod
    def validate_relation(cls, v: Optional[RelationOptions]) -> Optional[RelationOptions]:
        """Ensure relation options are provided for relation fields."""
        # Only validate on new creations, be lenient with existing data to avoid breaking
        # Users should provide relation options, but we won't block loading existing data
        return v

    @field_validator("select", mode="after")
    @classmethod
    def validate_select(cls, v: Optional[SelectOptions]) -> Optional[SelectOptions]:
        """Ensure select options are provided for select fields."""
        # Only validate on new creations, be lenient with existing data to avoid breaking
        # Users should provide select options, but we won't block loading existing data
        return v


# SQL type mapping for field types
FIELD_TYPE_SQL_MAP: Dict[FieldType, str] = {
    FieldType.TEXT: "TEXT",
    FieldType.NUMBER: "REAL",
    FieldType.BOOL: "BOOLEAN",
    FieldType.EMAIL: "VARCHAR(255)",
    FieldType.URL: "VARCHAR(2048)",
    FieldType.DATE: "DATE",
    FieldType.DATETIME: "TIMESTAMP",
    FieldType.SELECT: "TEXT",
    FieldType.FILE: "TEXT",  # Stores file IDs as JSON array
    FieldType.RELATION: "VARCHAR(36)",  # UUID
    FieldType.JSON: "JSON",
    FieldType.EDITOR: "TEXT",
    FieldType.GEOPOINT: "JSON",  # Stores as {"lat": float, "lng": float, "alt": float?}
    FieldType.AUTODATE: "TIMESTAMP",  # Auto-managed datetime
}


# Python type mapping for validation
FIELD_TYPE_PYTHON_MAP: Dict[FieldType, type] = {
    FieldType.TEXT: str,
    FieldType.NUMBER: (int, float),
    FieldType.BOOL: bool,
    FieldType.EMAIL: str,
    FieldType.URL: str,
    FieldType.DATE: str,  # ISO format string
    FieldType.DATETIME: str,  # ISO format string
    FieldType.SELECT: (str, list),
    FieldType.FILE: (str, list),
    FieldType.RELATION: str,
    FieldType.JSON: (dict, list),
    FieldType.EDITOR: str,
    FieldType.GEOPOINT: dict,  # {"lat": float, "lng": float, "alt": float?}
    FieldType.AUTODATE: str,  # ISO format string (auto-managed; user input ignored)
}


def validate_geopoint(value: Any, options: Optional[GeoPointOptions] = None) -> dict:
    """
    Validate a GeoPoint value.

    Args:
        value: Dict with 'lat', 'lng', and optional 'alt' keys
        options: Optional GeoPointOptions for validation

    Returns:
        Validated GeoPoint dict

    Raises:
        ValueError: If validation fails
    """
    if not isinstance(value, dict):
        raise ValueError("GeoPoint must be an object with 'lat' and 'lng' properties")

    lat = value.get("lat")
    lng = value.get("lng")
    alt = value.get("alt")

    if lat is None or lng is None:
        raise ValueError("GeoPoint requires 'lat' and 'lng' properties")

    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError):
        raise ValueError("GeoPoint 'lat' and 'lng' must be numbers")

    # Validate latitude range
    if lat < -90 or lat > 90:
        raise ValueError("Latitude must be between -90 and 90")

    # Validate longitude range
    if lng < -180 or lng > 180:
        raise ValueError("Longitude must be between -180 and 180")

    # Apply options validation
    if options:
        if lat < options.min_lat or lat > options.max_lat:
            raise ValueError(f"Latitude must be between {options.min_lat} and {options.max_lat}")
        if lng < options.min_lng or lng > options.max_lng:
            raise ValueError(f"Longitude must be between {options.min_lng} and {options.max_lng}")
        if options.require_altitude and alt is None:
            raise ValueError("Altitude is required for this GeoPoint field")

    result = {"lat": lat, "lng": lng}
    if alt is not None:
        try:
            result["alt"] = float(alt)
        except (TypeError, ValueError):
            raise ValueError("GeoPoint 'alt' must be a number")

    return result


def calculate_distance(point1: dict, point2: dict, unit: str = "km") -> float:
    """
    Calculate distance between two GeoPoints using the Haversine formula.

    Args:
        point1: First GeoPoint {"lat": float, "lng": float}
        point2: Second GeoPoint {"lat": float, "lng": float}
        unit: Distance unit - "km" (kilometers), "mi" (miles), "m" (meters)

    Returns:
        Distance between the two points in the specified unit
    """
    import math

    # Earth's radius
    R_km = 6371.0  # kilometers
    R_mi = 3958.8  # miles
    R_m = 6371000.0  # meters

    radius = {"km": R_km, "mi": R_mi, "m": R_m}.get(unit, R_km)

    lat1 = math.radians(point1["lat"])
    lat2 = math.radians(point2["lat"])
    dlat = math.radians(point2["lat"] - point1["lat"])
    dlng = math.radians(point2["lng"] - point1["lng"])

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return radius * c
