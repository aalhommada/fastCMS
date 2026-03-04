"""
Example FastCMS plugin — demonstrates all plugin capabilities.

Copy this directory (as plugins/my_plugin/) to start writing your own plugin.
This file is the only required file; everything else is optional.
"""

PLUGIN_META = {
    "id": "example-plugin",
    "name": "Example Plugin",
    "version": "1.0.0",
    "author": "FastCMS Team",
    "description": "Demonstration plugin showing routes, hooks, and admin UI.",
}


def register(ctx) -> None:
    """
    Called once at server startup. Register all plugin capabilities here.

    Args:
        ctx: PluginContext — provides the full plugin API
    """
    # 1. Register API routes
    from .routes import router
    ctx.include_router(router, prefix="/example")

    # 2. Register event hooks
    from .hooks import on_post_created
    ctx.on_record_create("posts", on_post_created)

    # 3. Add an admin UI page to the sidebar
    ctx.add_admin_page(
        nav_id="example-plugin",
        label="Example Plugin",
        icon="fa-puzzle-piece",
        url="/admin/plugins/example",
    )
