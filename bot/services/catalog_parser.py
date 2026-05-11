import httpx
import re
import logging
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

KALINKA_URL = "https://mebel-kalinka.ru"
KALINKA_CATALOG = "https://mebel-kalinka.ru/katalog/sayt/divany/"
OPRIME_CATALOG = "https://oprime.ru/catalog/divany"


async def parse_kalinka() -> dict[str, str]:
    """Parse KALINKA catalog and return model -> URL mapping."""
    models = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(KALINKA_CATALOG)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/katalog/item/kalinka" in href:
                    match = re.search(r"kalinka[_-]?(\d+)", href.lower())
                    if match:
                        model_id = match.group(1)
                        models[f"к{model_id}"] = href
                        models[f"калинка {model_id}"] = href
                        models[f"калинка_{model_id}"] = href
            logger.info(f"Parsed KALINKA: {len(models)} models found")
        except Exception as e:
            logger.warning(f"Failed to parse KALINKA: {e}")
    return models


async def parse_oprime() -> dict[str, str]:
    """Parse OPRIME catalog and return model -> URL mapping."""
    models = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(OPRIME_CATALOG)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if "/catalog/divany/" in href and href != "/catalog/divany":
                    name = link.get_text(strip=True).lower()
                    if name and not name.startswith("/"):
                        models[name] = f"https://oprime.ru{href}"
                        if "-" in name:
                            simple = name.split("-")[0].strip()
                            models[simple] = f"https://oprime.ru{href}"
            logger.info(f"Parsed OPRIME: {len(models)} models found")
        except Exception as e:
            logger.warning(f"Failed to parse OPRIME: {e}")
    return models


async def update_catalog_urls() -> dict[str, str]:
    """Update all model URLs from both factories."""
    kalinka = await parse_kalinka()
    oprime = await parse_oprime()
    combined = {**kalinka, **oprime}
    logger.info(f"Total models parsed: {len(combined)}")
    return combined


if __name__ == "__main__":
    import asyncio

    async def test():
        models = await update_catalog_urls()
        for name, url in list(models.items())[:10]:
            print(f"{name}: {url}")

    asyncio.run(test())