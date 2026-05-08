from __future__ import annotations

import asyncio
from anthropic import AsyncAnthropic


async def main():
    client = AsyncAnthropic(
        api_key="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"
    )
    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(f"SUCCESS! Response: {response.content[0].text}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
