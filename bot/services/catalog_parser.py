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
                # Match specific model pages (not categories)
                if re.match(r"/catalog/divany/[a-z]+(-\w+)*$", href):
                    # Extract model name from URL path
                    model_name = href.split("/")[-1].lower()
                    full_url = f"https://oprime.ru{href}"

                    # Add various name variants
                    models[model_name] = full_url
                    # Also add uppercase for exact matching
                    models[model_name.upper()] = full_url

                    # Add simple name (first part before hyphen)
                    if "-" in model_name:
                        simple = model_name.split("-")[0]
                        models[simple] = full_url

                    # Check if link has visible name that matches a known model
                    text = link.get_text(strip=True).lower()
                    if text and text not in [
                        "на ножках",
                        "раскладные",
                        "п-образные",
                        "модульные",
                        "угловые",
                        "прямые",
                        "со спальным местом",
                        "с бельевым коробом",
                        "все фильтры",
                        "сортировать",
                        "показать еще",
                    ]:
                        models[text] = full_url

            logger.info(f"Parsed OPRIME: {len(models)} models found")

            # Add known models as fallback (in case parsing misses them)
            known_models = {
                "каро": "https://oprime.ru/catalog/divany/caro-a22l-t3s-a22p",
                "симпл": "https://oprime.ru/catalog/divany/simple-i",
                "тейлор": "https://oprime.ru/catalog/divany/taylor-a4l-t3s-a4p",
                "тноф": "https://oprime.ru/catalog/divany/snof-a2o",
                "сноф": "https://oprime.ru/catalog/divany/snof-a2o",
                "мэттью": "https://oprime.ru/catalog/divany/matthew-divan",
                "флекс": "https://oprime.ru/catalog/divany/flex-m4l-v3s-m4p",
                "флай": "https://oprime.ru/catalog/divany/fly-t310",
                "fly": "https://oprime.ru/catalog/divany/fly-t310",
                "taylor": "https://oprime.ru/catalog/divany/taylor-a4l-t3s-a4p",
                "вега": "https://oprime.ru/modeli/vega",
                "тулип": "https://oprime.ru/modeli/tulip",
                "сноб": "https://oprime.ru/modeli/snob",
                "уно": "https://oprime.ru/catalog/divany/uno-a21o",
            }
            # KALINKA known models - verified URLs
            kalinka_models = {
                "оскар": "https://mebel-kalinka.ru/katalog/item/oskar/",
                "к72": "https://mebel-kalinka.ru/katalog/item/kalinka_72/",
                "к25": "https://mebel-kalinka.ru/katalog/item/kalinka_25/",
                "к26": "https://mebel-kalinka.ru/katalog/item/kalinka_26/",
                "к21": "https://mebel-kalinka.ru/katalog/item/kalinka_21_1/",
                "калинка 21": "https://mebel-kalinka.ru/katalog/item/kalinka_21_1/",
                "калинка-21": "https://mebel-kalinka.ru/katalog/item/kalinka_21_1/",
                "домус": "https://mebel-kalinka.ru/katalog/item/domus/",
                "domus": "https://mebel-kalinka.ru/katalog/item/domus/",
                "к28": "https://mebel-kalinka.ru/katalog/item/kalinka_28/",
                "к29": "https://mebel-kalinka.ru/katalog/item/kalinka_29/",
                "к30": "https://mebel-kalinka.ru/katalog/item/kalinka_30_1/",
                "к31": "https://mebel-kalinka.ru/katalog/item/kalinka_30/",
                "калинка к28": "https://mebel-kalinka.ru/katalog/item/kalinka_28/",
                "калинка-28": "https://mebel-kalinka.ru/katalog/item/kalinka_28/",
                "калинка 28": "https://mebel-kalinka.ru/katalog/item/kalinka_28/",
                "калинка к29": "https://mebel-kalinka.ru/katalog/item/kalinka_29/",
                "калинка к30": "https://mebel-kalinka.ru/katalog/item/kalinka_30_1/",
                "калинка к31": "https://mebel-kalinka.ru/katalog/item/kalinka_30/",
            }
            # Add with proper format
            for name, url in kalinka_models.items():
                models[name] = url
                if name.startswith("к") and len(name) == 2:
                    models[f"калинка {name}"] = url
                    models[f"калинка_{name}"] = url
            for name, url in known_models.items():
                if name not in models:
                    models[name] = url
            logger.info(f"Added {len(known_models)} known OPRIME models")

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
