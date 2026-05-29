from __future__ import annotations

from .router import Router

class Dispatcher:
    def __init__(self, bot=None):
        self.bot = bot
        self.router = Router()  # We'll use a single router for simplicity; but we can have multiple.
        # Actually, aiogram's Dispatcher can include multiple routers.
        self.routers = []

    def include_router(self, router: Router):
        self.routers.append(router)

    async def feed_update(self, bot, update):
        # We'll only handle message updates for now.
        message = getattr(update, 'message', None)
        if message is None:
            return
        # Process the message through each router in order.
        for router in self.routers:
            await router.process_message(message, bot)
            # If a handler has been processed, we might want to stop? In aiogram, processing continues
            # through all routers until a handler returns True? Actually, each router processes the update
            # and if a handler is found, it is called and the update is considered processed for that router.
            # We'll just let all routers process the message.