from __future__ import annotations

import asyncio
from anthropic import AsyncAnthropic


async def main():
    api_key = input("Enter API key: ").strip()
    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=100,
            messages=[{"role": "user", "content": "Hello"}],
        )
        print(f"Response: {response.content[0].text}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")


if __name__ == "__main__":
    asyncio.run(main())