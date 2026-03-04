"""
Example FastCMS hook file.

Copy this file (e.g. as hooks/my_hooks.py) to start writing hooks.
Hooks in the hooks/ directory are loaded automatically at startup.

Import decorators from:
    from app.fastcms_hooks_api import on_record_create, on_record_update, on_record_delete, on_any_event

The event object contains:
    event.type            — EventType enum value  (e.g. EventType.RECORD_CREATED)
    event.collection_name — name of the collection
    event.record_id       — ID of the affected record (None for delete payload)
    event.data            — the record data dict
    event.timestamp       — ISO timestamp string when the event occurred

All handler functions must be async.
"""

# Uncomment and customise to activate:

# from app.fastcms_hooks_api import on_record_create, on_record_update, on_record_delete

# @on_record_create("posts")
# async def notify_new_post(event):
#     print(f"New post created: {event.record_id} in {event.collection_name}")

# @on_record_update("users")
# async def sync_profile(event):
#     print(f"User updated: {event.record_id}, data: {event.data}")

# @on_record_delete()   # no collection filter = fires for all collections
# async def log_deletions(event):
#     print(f"Record deleted: {event.record_id} from {event.collection_name}")
