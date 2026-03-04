"""
Example plugin event hooks.

These handlers are registered in __init__.py via ctx.on_record_create(...).
"""
import logging

logger = logging.getLogger("example_plugin")


async def on_post_created(event) -> None:
    """Fires whenever a record is created in the 'posts' collection."""
    logger.info(
        f"[example-plugin] New post created: id={event.record_id} "
        f"collection={event.collection_name}"
    )
