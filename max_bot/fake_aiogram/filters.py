from __future__ import annotations

import re
from typing import Any, Callable

class CommandStart:
    def __init__(self, ignore_case: bool = False, ignore_prefix: bool = False):
        self.ignore_case = ignore_case
        self.ignore_prefix = ignore_prefix

    async def __call__(self, message) -> bool:
        text = message.text or ""
        if self.ignore_case:
            text = text.lower()
        prefix = "" if self.ignore_prefix else "/"
        return text.startswith(prefix + "start")

class Command:
    def __init__(self, *commands, ignore_case: bool = False, ignore_prefix: bool = False):
        self.commands = set(commands)
        self.ignore_case = ignore_case
        self.ignore_prefix = ignore_prefix

    async def __call__(self, message) -> bool:
        text = message.text or ""
        if self.ignore_case:
            text = text.lower()
        if not self.ignore_prefix and text.startswith('/'):
            text = text[1:]
        # take first word
        cmd = text.split()[0] if text else ""
        return cmd in self.commands

class F:
    class _Filter:
        def __init__(self, attr: str, op: str = None, value: Any = None):
            self.attr = attr
            self.op = op
            self.value = value

        async def __call__(self, obj: Any) -> bool:
            val = getattr(obj, self.attr, None)
            if self.op is None:
                return bool(val)
            if self.op == "==":
                return val == self.value
            if self.op == "!=":
                return val != self.value
            if self.op == "in":
                return val in self.value if isinstance(val, (str, list, tuple)) else False
            if self.op == "not_in":
                return val not in self.value if isinstance(val, (str, list, tuple)) else True
            if self.op == "contains":
                return isinstance(val, str) and self.value in val
            # add more ops if needed
            return False

        def __and__(self, other):
            return AndFilter([self, other])
        def __or__(self, other):
            return OrFilter([self, other])

    text = _Filter("text")
    caption = _Filter("caption")
    contact = _Filter("contact")
    photo = _Filter("photo")
    content_type = _Filter("content_type")

class AndFilter:
    def __init__(self, filters):
        self.filters = filters

    async def __call__(self, obj):
        for f in self.filters:
            if not await f(obj):
                return False
        return True

class OrFilter:
    def __init__(self, filters):
        self.filters = filters

    async def __call__(self, obj):
        for f in self.filters:
            if await f(obj):
                return True
        return False