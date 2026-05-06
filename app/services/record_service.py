"""Service for record CRUD operations with validation."""
import math
from typing import Any, Dict, List, Optional, Union
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from app.db.repositories.record import RecordRepository
from app.db.repositories.collection import CollectionRepository
from app.schemas.record import (
    RecordCreate,
    RecordUpdate,
    RecordResponse,
    RecordListResponse,
    RecordFilter,
)
from app.utils.field_types import FieldSchema, FieldType, validate_geopoint
from app.core.exceptions import (
    NotFoundException,
    ValidationException,
    BadRequestException,
)
from app.core.events import event_manager, Event, EventType
from app.core.access_control import access_control, AccessContext
from app.core.dependencies import UserContext


class RecordService:
    """Service for managing records in dynamic collections."""

    def __init__(
        self, db: AsyncSession, collection_name: str, user_context: Optional[UserContext] = None
    ):
        self.db = db
        self.collection_name = collection_name
        self.user_context = user_context
        self.repo = RecordRepository(db, collection_name)
        self.collection_repo = CollectionRepository(db)

    async def create_record(self, data: RecordCreate) -> RecordResponse:
        """Create a new record with validation."""
        # Get collection schema
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if not collection:
            raise NotFoundException(f"Collection '{self.collection_name}' not found")

        # View collections are read-only
        if collection.type == "view":
            raise BadRequestException(f"Cannot create records in view collection '{self.collection_name}'")

        # Check create permission
        context = self._create_access_context(request_data=data.data)
        access_control.check(collection.create_rule, context, "create")

        # Extract fields from schema
        fields = collection.schema.get("fields", [])
        field_schemas = [FieldSchema(**field) for field in fields]

        # Validate data against schema
        validated_data = self._validate_fields(data.data, field_schemas, is_create=True)

        # Auto-set autodate fields for create
        from datetime import datetime, timezone as _tz
        for fs in field_schemas:
            if fs.type == FieldType.AUTODATE:
                opts = fs.autodate
                if opts is None or opts.on_create:
                    validated_data[fs.name] = datetime.now(_tz.utc)

        # Create record
        record = await self.repo.create(validated_data)
        await self.db.commit()

        # Broadcast event
        response = self._to_response(record)
        await event_manager.broadcast(
            Event(
                type=EventType.RECORD_CREATED,
                collection_name=self.collection_name,
                record_id=record.id,
                data=response.data,
            )
        )

        return response

    async def get_record(
        self, record_id: str, expand: Optional[List[str]] = None
    ) -> RecordResponse:
        """Get a record by ID with optional relation expansion."""
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise NotFoundException(f"Record '{record_id}' not found")

        # Check view permission
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if collection:
            record_data = self._record_to_dict(record)
            context = self._create_access_context(record_data)
            access_control.check(collection.view_rule, context, "view")

        response = self._to_response(record)

        # Expand relations if requested
        if expand and collection:
            response = await self._expand_relations(response, collection, expand)

        return response

    async def list_records(
        self,
        page: int = 1,
        per_page: int = 20,
        filters: Optional[List[RecordFilter]] = None,
        sort: Optional[str] = None,
        order: str = "asc",
        expand: Optional[List[str]] = None,
        search: Optional[str] = None,
        sort_fields: Optional[List[tuple]] = None,
        fields: Optional[List[str]] = None,
        skip_total: bool = False,
    ) -> RecordListResponse:
        """
        List records with pagination, filtering, sorting, search, and relation expansion.

        Args:
            page: Page number (1-indexed)
            per_page: Number of records per page
            filters: List of RecordFilter or FilterGroup
            sort: Single sort field (deprecated, use sort_fields)
            order: Sort order for single field (deprecated, use sort_fields)
            expand: List of relation fields to expand (supports nested: author.company)
            search: Full-text search term
            sort_fields: List of (field, order) tuples for multi-field sorting
            fields: List of fields to return (field selection)
            skip_total: Skip total count for faster queries
        """
        # Validate collection exists
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if not collection:
            raise NotFoundException(f"Collection '{self.collection_name}' not found")

        # Check list permission
        context = self._create_access_context()
        access_control.check(collection.list_rule, context, "list")

        skip = (page - 1) * per_page

        # Identify searchable fields (text and editor types)
        search_fields = None
        if search:
            schema_fields = collection.schema.get("fields", [])
            search_fields = [
                f["name"] for f in schema_fields
                if f.get("type") in ["text", "editor", "email", "url"]
            ]

        # Handle backwards compatibility: convert sort/order to sort_fields
        if sort_fields is None and sort is not None:
            sort_fields = [(sort, order)]

        # Get records
        records = await self.repo.get_all(
            skip=skip,
            limit=per_page,
            filters=filters,
            sort_fields=sort_fields,
            search=search,
            search_fields=search_fields,
        )

        # Get total count (skip if requested for performance)
        if skip_total:
            total = None
            total_pages = None
        else:
            total = await self.repo.count(
                filters=filters,
                search=search,
                search_fields=search_fields,
            )
            total_pages = math.ceil(total / per_page) if total > 0 else 0

        items = [self._to_response(record, fields) for record in records]

        # Expand relations if requested
        if expand:
            items = await self._expand_relations(items, collection, expand)

        return RecordListResponse(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )

    async def update_record(self, record_id: str, data: RecordUpdate) -> RecordResponse:
        """
        Update a record with validation.

        Supports increment/decrement modifiers:
        - "field+": value  -> Increment field by value
        - "field-": value  -> Decrement field by value

        Example:
            {"views+": 1, "likes-": 2}  -> Increment views by 1, decrement likes by 2
        """
        # Check if record exists
        existing = await self.repo.get_by_id(record_id)
        if not existing:
            raise NotFoundException(f"Record '{record_id}' not found")

        # Get collection schema
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if not collection:
            raise NotFoundException(f"Collection '{self.collection_name}' not found")

        # View collections are read-only
        if collection.type == "view":
            raise BadRequestException(f"Cannot update records in view collection '{self.collection_name}'")

        # Check update permission — pass old record data for :changed modifier support
        record_data = self._record_to_dict(existing)
        context = self._create_access_context(
            record_data=record_data,
            request_data=data.data,
            old_record_data=dict(record_data),  # snapshot before update
        )
        access_control.check(collection.update_rule, context, "update")

        # Extract fields from schema
        fields = collection.schema.get("fields", [])
        field_schemas = [FieldSchema(**field) for field in fields]

        # Process increment/decrement modifiers (e.g., views+: 1, likes-: 2)
        processed_data = self._process_increment_modifiers(data.data, record_data, field_schemas)

        # Validate data against schema
        validated_data = self._validate_fields(processed_data, field_schemas, is_create=False)

        # Auto-update autodate fields configured for updates
        from datetime import datetime, timezone as _tz
        for fs in field_schemas:
            if fs.type == FieldType.AUTODATE:
                opts = fs.autodate
                if opts is None or opts.on_update:
                    validated_data[fs.name] = datetime.now(_tz.utc)

        # Update record
        updated_record = await self.repo.update(record_id, validated_data)
        await self.db.commit()

        # Broadcast event
        response = self._to_response(updated_record)
        await event_manager.broadcast(
            Event(
                type=EventType.RECORD_UPDATED,
                collection_name=self.collection_name,
                record_id=updated_record.id,
                data=response.data,
            )
        )

        return response

    async def delete_record(self, record_id: str) -> None:
        """Delete a record."""
        # Get record before deleting
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise NotFoundException(f"Record '{record_id}' not found")

        # Get collection and check delete permission
        collection = await self.collection_repo.get_by_name(self.collection_name)
        if collection:
            # View collections are read-only
            if collection.type == "view":
                raise BadRequestException(f"Cannot delete records in view collection '{self.collection_name}'")

            record_data = self._record_to_dict(record)
            context = self._create_access_context(record_data)
            access_control.check(collection.delete_rule, context, "delete")

        # Delete record
        success = await self.repo.delete(record_id)
        if not success:
            raise NotFoundException(f"Record '{record_id}' not found")

        await self.db.commit()

        # Broadcast event
        await event_manager.broadcast(
            Event(
                type=EventType.RECORD_DELETED,
                collection_name=self.collection_name,
                record_id=record_id,
                data={"id": record_id},
            )
        )

    def _process_increment_modifiers(
        self,
        data: Dict[str, Any],
        current_data: Dict[str, Any],
        field_schemas: List[FieldSchema],
    ) -> Dict[str, Any]:
        """
        Process increment/decrement modifiers.

        Transforms field names ending with + or - into actual field updates:
        - "field+": value  -> field = current_value + value
        - "field-": value  -> field = current_value - value

        Args:
            data: Input data with potential modifiers
            current_data: Current record data (for reading current values)
            field_schemas: Field schemas for type checking

        Returns:
            Processed data with modifiers resolved to actual values
        """
        # Build field type map for validation
        number_fields = {
            f.name for f in field_schemas if f.type == FieldType.NUMBER
        }

        processed = {}
        for key, value in data.items():
            # Check for increment modifier (field+)
            if key.endswith("+"):
                field_name = key[:-1]
                if field_name in number_fields:
                    current_value = current_data.get(field_name, 0) or 0
                    try:
                        increment = float(value)
                        processed[field_name] = current_value + increment
                    except (TypeError, ValueError):
                        raise ValidationException(
                            f"Increment value for '{field_name}' must be a number",
                            details={"field": field_name, "value": value}
                        )
                else:
                    raise ValidationException(
                        f"Increment modifier (+) can only be used on number fields",
                        details={"field": key}
                    )
            # Check for decrement modifier (field-)
            elif key.endswith("-") and not key.startswith("-"):
                field_name = key[:-1]
                if field_name in number_fields:
                    current_value = current_data.get(field_name, 0) or 0
                    try:
                        decrement = float(value)
                        processed[field_name] = current_value - decrement
                    except (TypeError, ValueError):
                        raise ValidationException(
                            f"Decrement value for '{field_name}' must be a number",
                            details={"field": field_name, "value": value}
                        )
                else:
                    raise ValidationException(
                        f"Decrement modifier (-) can only be used on number fields",
                        details={"field": key}
                    )
            else:
                # Normal field, pass through
                processed[key] = value

        return processed

    def _validate_fields(
        self, data: Dict[str, Any], field_schemas: List[FieldSchema], is_create: bool
    ) -> Dict[str, Any]:
        """Validate record data against collection schema."""
        validated = {}
        errors = {}

        # Check required fields (only on create)
        if is_create:
            for field_schema in field_schemas:
                if field_schema.validation.required and field_schema.name not in data:
                    errors[field_schema.name] = "This field is required"

        # Validate provided fields
        for field_name, value in data.items():
            # Find field schema
            field_schema = next(
                (f for f in field_schemas if f.name == field_name), None
            )

            if not field_schema:
                # Ignore unknown fields
                continue

            # Skip validation if value is None and field is not required
            if value is None and not field_schema.validation.required:
                validated[field_name] = None
                continue

            # Skip validation if value is empty string and field is not required (for text-based fields)
            if (
                value == ""
                and not field_schema.validation.required
                and field_schema.type in [FieldType.TEXT, FieldType.EMAIL, FieldType.URL, FieldType.EDITOR]
            ):
                validated[field_name] = None
                continue

            # Validate field
            try:
                validated_value = self._validate_field(value, field_schema)
                validated[field_name] = validated_value
            except ValueError as e:
                errors[field_name] = str(e)

        if errors:
            raise ValidationException("Validation failed", details={"fields": errors})

        return validated

    def _validate_field(self, value: Any, field_schema: FieldSchema) -> Any:
        """Validate a single field value."""
        validation = field_schema.validation

        # Type-specific validation
        if field_schema.type == FieldType.TEXT or field_schema.type == FieldType.EDITOR:
            if not isinstance(value, str):
                raise ValueError("Must be a string")

            if validation.min_length and len(value) < validation.min_length:
                raise ValueError(f"Minimum length is {validation.min_length}")

            if validation.max_length and len(value) > validation.max_length:
                raise ValueError(f"Maximum length is {validation.max_length}")

            if validation.pattern:
                import re
                if not re.match(validation.pattern, value):
                    raise ValueError("Does not match required pattern")

        elif field_schema.type == FieldType.NUMBER:
            if not isinstance(value, (int, float)):
                raise ValueError("Must be a number")

            if validation.min is not None and value < validation.min:
                raise ValueError(f"Minimum value is {validation.min}")

            if validation.max is not None and value > validation.max:
                raise ValueError(f"Maximum value is {validation.max}")

        elif field_schema.type == FieldType.BOOL:
            if not isinstance(value, bool):
                raise ValueError("Must be a boolean")

        elif field_schema.type == FieldType.EMAIL:
            if not isinstance(value, str):
                raise ValueError("Must be a string")
            # Basic email validation
            if "@" not in value or "." not in value:
                raise ValueError("Invalid email format")

        elif field_schema.type == FieldType.URL:
            if not isinstance(value, str):
                raise ValueError("Must be a string")
            if not value.startswith(("http://", "https://")):
                raise ValueError("Invalid URL format")

        elif field_schema.type == FieldType.DATE:
            if isinstance(value, str):
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    raise ValueError("Invalid date format")
            elif not isinstance(value, datetime):
                raise ValueError("Must be a date string or datetime")

        elif field_schema.type == FieldType.SELECT:
            if validation.values and value not in validation.values:
                raise ValueError(f"Must be one of: {', '.join(validation.values)}")

        elif field_schema.type == FieldType.RELATION:
            if not isinstance(value, str):
                raise ValueError("Must be a string (record ID)")

        elif field_schema.type == FieldType.FILE:
            if not isinstance(value, list):
                raise ValueError("Must be an array of file IDs")

        elif field_schema.type == FieldType.JSON:
            # JSON accepts any structure
            pass

        elif field_schema.type == FieldType.GEOPOINT:
            # Validate GeoPoint coordinates
            return validate_geopoint(value, field_schema.geopoint)

        elif field_schema.type == FieldType.AUTODATE:
            # Autodate fields are managed automatically; ignore user-supplied values
            return None

        return value

    def _to_response(self, record, fields: Optional[List[str]] = None) -> RecordResponse:
        """
        Convert record model to response schema.

        Args:
            record: Database record model
            fields: Optional list of fields to include/exclude (field selection)
                   Supports:
                   - Positive selection: ["id", "title", "author"]
                   - Exclude fields: ["-password", "-internal_notes"]
                   - Field modifiers: ["title:excerpt(50)", "content:lower"]
        """
        data = self._record_to_dict(record)

        # Apply field selection if specified
        if fields:
            data = self._apply_field_selection(data, fields)

        return RecordResponse(
            id=record.id,
            data=data,
            created=record.created,
            updated=record.updated,
        )

    def _apply_field_selection(self, data: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
        """
        Apply field selection with include/exclude and modifiers.

        Args:
            data: Original record data
            fields: Field selection list

        Supports:
        - Include: "title" - include only specified fields
        - Exclude: "-password" - exclude specific fields (starts with -)
        - Modifier: "title:excerpt(100)" - apply modifier to field value
        """
        from app.utils.query_parser import QueryParser

        # Separate include, exclude, and modifiers
        include_fields = []
        exclude_fields = []
        field_modifiers: Dict[str, List[str]] = {}

        for field_spec in fields:
            if field_spec.startswith("-"):
                # Exclude field
                exclude_fields.append(field_spec[1:])
            elif ":" in field_spec:
                # Field with modifier
                field_name, modifiers = QueryParser.parse_field_with_modifiers(field_spec)
                include_fields.append(field_name)
                if modifiers:
                    field_modifiers[field_name] = modifiers
            else:
                # Include field
                include_fields.append(field_spec)

        # Determine which fields to include
        if include_fields:
            # Positive selection - only include specified fields
            result = {}
            for field in include_fields:
                if field in data:
                    value = data[field]
                    # Apply modifiers if any
                    if field in field_modifiers:
                        value = QueryParser.apply_filter_modifiers(value, field_modifiers[field])
                    result[field] = value
            return result
        elif exclude_fields:
            # Negative selection - exclude specified fields
            result = {}
            for field, value in data.items():
                if field not in exclude_fields:
                    result[field] = value
            return result
        else:
            # No selection, return all
            return data

    def _record_to_dict(self, record) -> Dict[str, Any]:
        """Extract record data as dictionary."""
        data = {}
        for key in dir(record):
            if not key.startswith("_") and key not in ["id", "created", "updated", "metadata", "registry"]:
                value = getattr(record, key)
                # Skip SQLAlchemy internal attributes
                if not callable(value) and not key.startswith("_sa_"):
                    data[key] = value
        return data

    async def _expand_relations(
        self,
        responses: List[RecordResponse] | RecordResponse,
        collection: Any,
        expand_fields: List[str],
        depth: int = 0,
        max_depth: int = 3,
    ) -> List[RecordResponse] | RecordResponse:
        """
        Expand relation fields in record responses using batch fetching.
        Supports:
        - Nested expansion (e.g., author.company)
        - Back-relation expansion (e.g., posts_via_author)

        Args:
            responses: Single RecordResponse or list of RecordResponses
            collection: Collection model containing schema
            expand_fields: List of field names to expand
                          - Direct: author, company
                          - Nested: author.company
                          - Back-relation: posts_via_author (find posts where author = this record)
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            Same type as input (single or list) with 'expand' field populated
        """
        is_single = isinstance(responses, RecordResponse)
        items = [responses] if is_single else responses

        if not items or not expand_fields or depth >= max_depth:
            return responses

        # Get relation fields from collection schema
        fields = collection.schema.get("fields", [])
        relation_fields = {
            f["name"]: f for f in fields if f.get("type") == "relation"
        }

        # Separate top-level, nested, and back-relation expand fields
        top_level_expands = []
        nested_expands: Dict[str, List[str]] = {}  # parent -> [nested_fields]
        back_relation_expands = []  # (collection_name, field_name, expand_key)

        for field_path in expand_fields:
            # Check for back-relation pattern: collection_via_field
            if "_via_" in field_path and "." not in field_path:
                parts = field_path.split("_via_")
                if len(parts) == 2:
                    target_collection, via_field = parts
                    back_relation_expands.append((target_collection, via_field, field_path))
                continue

            if "." in field_path:
                # Nested expand (e.g., author.company)
                parent, rest = field_path.split(".", 1)
                if parent not in nested_expands:
                    nested_expands[parent] = []
                nested_expands[parent].append(rest)
                # Ensure parent is expanded first
                if parent not in top_level_expands and parent in relation_fields:
                    top_level_expands.append(parent)
            else:
                if field_path in relation_fields:
                    top_level_expands.append(field_path)

        # Process each top-level expand field
        for field_name in top_level_expands:
            field_config = relation_fields[field_name]
            # Try to get collection from relation options, fallback to validation for backward compat
            target_collection_name = (
                field_config.get("relation", {}).get("collection") or
                field_config.get("validation", {}).get("collection_name")
            )

            if not target_collection_name:
                continue

            # Collect all IDs to fetch
            ids_to_fetch = set()
            for item in items:
                value = item.data.get(field_name)
                if value:
                    if isinstance(value, list):
                        ids_to_fetch.update(value)
                    else:
                        ids_to_fetch.add(value)

            if not ids_to_fetch:
                continue

            # Batch fetch related records
            try:
                target_repo = RecordRepository(self.db, target_collection_name)
                target_collection = await self.collection_repo.get_by_name(target_collection_name)

                # Chunk IDs to avoid query limits (e.g. 100 at a time)
                fetched_records = {}
                id_list = list(ids_to_fetch)
                chunk_size = 100

                for i in range(0, len(id_list), chunk_size):
                    chunk = id_list[i : i + chunk_size]
                    records = await target_repo.get_all(
                        limit=len(chunk),
                        filters=[RecordFilter(field="id", operator="in", value=chunk)]
                    )
                    for r in records:
                        response = self._to_response(r)
                        fetched_records[r.id] = response

                # Handle nested expand for this field if needed
                if field_name in nested_expands and target_collection:
                    nested_responses = list(fetched_records.values())
                    if nested_responses:
                        await self._expand_relations(
                            nested_responses,
                            target_collection,
                            nested_expands[field_name],
                            depth=depth + 1,
                            max_depth=max_depth,
                        )

                # Map back to items
                for item in items:
                    value = item.data.get(field_name)
                    if not value:
                        continue

                    if item.expand is None:
                        item.expand = {}

                    if isinstance(value, list):
                        item.expand[field_name] = [
                            fetched_records[rid].model_dump() if rid in fetched_records else None
                            for rid in value if rid in fetched_records
                        ]
                    else:
                        if value in fetched_records:
                            item.expand[field_name] = fetched_records[value].model_dump()

            except Exception as e:
                # Log error but don't fail the request
                # logger.warning(f"Failed to expand field {field_name}: {e}")
                pass

        # Process back-relation expands (e.g., posts_via_author)
        for target_collection, via_field, expand_key in back_relation_expands:
            try:
                # Check if target collection exists
                target_collection_model = await self.collection_repo.get_by_name(target_collection)
                if not target_collection_model:
                    continue

                # Verify the target collection has a relation field pointing to this collection
                target_fields = target_collection_model.schema.get("fields", [])
                via_field_config = None
                for field in target_fields:
                    if field.get("name") == via_field and field.get("type") == "relation":
                        via_field_config = field
                        break

                if not via_field_config:
                    continue

                # Get all record IDs we need to find back-relations for
                record_ids = [item.id for item in items]

                # Create repository for target collection
                target_repo = RecordRepository(self.db, target_collection)

                # For each record, find records in target collection that reference it
                # We batch this by querying for all related records at once
                related_records = await target_repo.get_all(
                    limit=1000,  # Reasonable limit for back-relations
                    filters=[RecordFilter(field=via_field, operator="in", value=record_ids)]
                )

                # Group related records by the via_field value
                records_by_parent: Dict[str, List[Dict[str, Any]]] = {}
                for record in related_records:
                    response = self._to_response(record)
                    parent_id = response.data.get(via_field)
                    if parent_id:
                        if parent_id not in records_by_parent:
                            records_by_parent[parent_id] = []
                        records_by_parent[parent_id].append(response.model_dump())

                # Map back to items
                for item in items:
                    if item.expand is None:
                        item.expand = {}

                    # Get related records for this item
                    related = records_by_parent.get(item.id, [])
                    item.expand[expand_key] = related

            except Exception as e:
                # Log error but don't fail the request
                # logger.warning(f"Failed to expand back-relation {expand_key}: {e}")
                pass

        return items[0] if is_single else items

    def _create_access_context(
        self,
        record_data: Optional[Dict[str, Any]] = None,
        request_data: Optional[Dict[str, Any]] = None,
        old_record_data: Optional[Dict[str, Any]] = None,
    ) -> AccessContext:
        """Create access context for permission evaluation."""
        return AccessContext(
            user_id=self.user_context.user_id if self.user_context else None,
            user_role=self.user_context.role if self.user_context else "user",
            record_data=record_data,
            request_data=request_data,
            old_record_data=old_record_data,
        )
