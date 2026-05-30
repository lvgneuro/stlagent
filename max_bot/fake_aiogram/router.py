from __future__ import annotations

from typing import Any
import inspect

class Router:
    def __init__(self):
        self.message_handlers = []  # each element: (filters, handler)
        # We can add other handler types as needed, but for now we only need message handlers.

    def message(self, *filters, **kwargs):
        def decorator(func):
            self.message_handlers.append((filters, func))
            return func
        return decorator

    # We'll also add a callback_query decorator for completeness, though not used in echo router.
    def callback_query(self, *filters, **kwargs):
        def decorator(func):
            # We'll store them similarly if needed
            return func
        return decorator

    async def process_message(self, message: Any, bot: Any):
        """
        Process a message through the registered handlers.
        This is a simplified version of what aiogram's Dispatcher does.
        """
        for filters, handler in self.message_handlers:
            # Check all filters
            ok = True
            for f in filters:
                if hasattr(f, '__call__'):
                    # If it's a filter instance (like CommandStart, F.text, etc.)
                    if not await f(message):
                        ok = False
                        break
                else:
                    # If it's not callable, we assume it's a MagicFilter instance (like F.text)
                    # which we already handled above? Actually, F.text returns a _Filter instance which is callable.
                    # So we should be fine.
                    pass
            if ok:
                # Call the handler with appropriate arguments.
                # We try to infer the signature.
                # Common patterns in echo router:
                #   async def command_start_handler(message: Message) -> None:
                #   async def ai_handler(message: Message, bot: Bot) -> None:
                # We'll try to pass both message and bot; if the handler doesn't accept bot, we'll catch TypeError.
                try:
                    # Check if handler expects a bot argument
                    sig = inspect.signature(handler)
                    params = sig.parameters
                    if 'bot' in params:
                        await handler(message, bot=bot)
                    elif len(params) >= 2 and any('bot' in p.lower() for p in params):
                        # Try to find a parameter that looks like bot
                        for p in params:
                            if 'bot' in p.lower():
                                await handler(message, **{p: bot})
                                break
                        else:
                            await handler(message)
                    else:
                        await handler(message)
                except TypeError as e:
                    # If we failed because of unexpected keyword argument, try without bot
                    if "got an unexpected keyword argument" in str(e):
                        await handler(message)
                    else:
                        raise
                return  # Assume one handler is enough; in aiogram, the first matching handler is used.
        # If no handler matched, we do nothing (or could log).

# We also need to expose the Router class in the __init__.py, which we already did.