import asyncio
from bot.database import db
from bot.services.rivalli_search import rivalli_search


async def test():
    await db.init_db()
    count = await db.get_sofa_count()
    print(f"Total sofas: {count}")

    results = await rivalli_search.search("Орлеан")
    print(f"Search Орлеан: {len(results)} results")
    for r in results:
        print(f"  - {r.name}: {r.url}")

    results = await rivalli_search.search("Порто")
    print(f"Search Порто: {len(results)} results")
    for r in results:
        print(f"  - {r.name}: {r.url}")

    results = await rivalli_search.search("Аруба")
    print(f"Search Аруба: {len(results)} results")
    for r in results:
        print(f"  - {r.name}: {r.url}")


asyncio.run(test())