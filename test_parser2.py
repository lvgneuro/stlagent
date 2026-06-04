import asyncio
from bot.services.rivalli_parser import RivalliParser


async def test():
    async with RivalliParser() as parser:
        sofa_links = await parser.parse_catalog_page(
            "https://rivalli.ru/catalog/divany/"
        )
        print(f"Found {len(sofa_links)} sofa links")
        for name, url in sofa_links[:5]:
            print(f"{name}: {url}")


asyncio.run(test())
