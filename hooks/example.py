"""
Example FastCMS hook file.

Copy this file (without "example" prefix) to start writing hooks.
Hooks are loaded automatically at startup from the ./hooks/ directory.

Available decorators (import from fastcms.hooks):
  on_record_create(collection_name)  — fires after a record is created
  on_record_update(collection_name)  — fires after a record is updated
  on_record_delete(collection_name)  — fires after a record is deleted
  on_any_event()                     — fires on all events

The event object contains:
  event.event_type   — EventType enum value
  event.collection_name
  event.record_id
  event.data         — the record data dict
"""

# Uncomment to activate:
# from fastcms.hooks import on_record_create, on_record_update

# @on_record_create("posts")
# async def notify_new_post(event):
#     print(f"New post created: {event.record_id}")

# @on_record_update("users")
# async def sync_profile(event):
#     print(f"User updated: {event.record_id}")
