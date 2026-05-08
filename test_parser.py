import asyncio
import re
import aiohttp


async def test():
    async with aiohttp.ClientSession() as session:
        async with session.get("https://rivalli.ru/catalog/divany/") as resp:
            html = await resp.text()
            print(f"Length: {len(html)}")

            pattern = r'href="(https://rivalli\.ru/catalog/divany/[^/"]+/)"'
            links = re.findall(pattern, html)
            print(f"Found {len(links)} links")

            pattern2 = r'<a[^>]+href="/catalog/divany/([^/"]+)/"'
            links2 = re.findall(pattern2, html)
            print(f"Found {len(links2)} relative links")

            # Check for product items
            if "product" in html.lower():
                print("Has 'product' in html")

            # Check for item links
            item_pattern = r'<a[^>]+href="/catalog/divany/[^/"]+/"[^>]*>'
            items = re.findall(item_pattern, html)
            print(f"Found {len(items)} a tags with /catalog/divany/")


asyncio.run(test())