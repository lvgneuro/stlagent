from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://lineaflexshop.ru"
CATEGORIES = {
    "economica": "https://lineaflexshop.ru/category/matrasy/economica/",
    "grigio": "https://lineaflexshop.ru/category/matrasy/grigio/",
    "razionale": "https://lineaflexshop.ru/category/matrasy/razionale/",
    "popolare": "https://lineaflexshop.ru/category/matrasy/popolare/",
    "anatomica": "https://lineaflexshop.ru/category/matrasy/anatomica/",
    "ergonomica": "https://lineaflexshop.ru/category/matrasy/ergonomica/",
    "champions_league": "https://lineaflexshop.ru/category/matrasy/champions-league/",
    "sensorica": "https://lineaflexshop.ru/category/matrasy/sensorica/",
    "luxury": "https://lineaflexshop.ru/category/matrasy/luxury/",
    "formaflex": "https://lineaflexshop.ru/category/matrasy/formaflex/",
    "di_arte": "https://lineaflexshop.ru/category/matrasy/di-arte/",
}

CATEGORY_NAMES_RU = {
    "economica": "Эконом (Linea Economica)",
    "grigio": "Grigio (Linea Grigio)",
    "razionale": "Рациональный (Linea Razionale)",
    "popolare": "Популярный (Linea Popolare)",
    "anatomica": "Анатомический (Linea Anatomica)",
    "ergonomica": "Эргономический (Linea Ergonomica)",
    "champions_league": "Champions League (Linea Champions League)",
    "sensorica": "Sensorica (Linea Sensorica)",
    "luxury": "Премиум (Linea Luxury)",
    "formaflex": "FormaFlex",
    "di_arte": "Di Arte",
}


@dataclass
class MattressData:
    name_en: str
    name_ru: str
    url: str
    category: str
    height: str | None
    firmness: str | None
    spring_type: str | None
    springs_per_place: str | None
    max_weight: str | None
    description: str | None
    price_from: str | None


def _extract_price(html: str) -> str | None:
    pattern = (
        r'<bdi>\s*([\d\s]+)\s*<span class="woocommerce-Price-currencySymbol">₽</span>'
    )
    match = re.search(pattern, html)
    if match:
        raw = match.group(1).strip()
        raw = re.sub(r"\s", "", raw)
        try:
            val = int(raw)
            if val > 1000:
                return f"{val:,}".replace(",", " ")
        except ValueError:
            pass
    return None


def _extract_spec(html: str, label: str) -> str | None:
    pattern = re.escape(label) + r"\s*[:\-]?\s*([^<;]+)"
    match = re.search(pattern, html)
    if match:
        return match.group(1).strip()
    return None


def _extract_specs_block(html: str) -> dict[str, str]:
    specs: dict[str, str] = {}

    pattern = r'<span[^>]*class="[^"]*value[^"]*"[^>]*>([^<]+)</span>'
    values = re.findall(pattern, html)

    labels = re.findall(r'<span[^>]*class="[^"]*label[^"]*"[^>]*>([^<]+)</span>', html)
    for label, value in zip(labels, values):
        key = label.strip().lower().rstrip(":")
        val = value.strip()
        if key == "высота, см.":
            specs["height"] = val
        elif key == "вес на одно место, кг.":
            specs["max_weight"] = val
        elif key == "число пружин на спальное место, шт.":
            specs["springs"] = val
        elif "жесткость" in key:
            if "сторона 1" in key:
                specs["firmness"] = val

    return specs


def parse_product_card(html: str, url: str) -> MattressData | None:
    soup = BeautifulSoup(html, "html.parser")

    title_el = soup.select_one(".product_title, h1.entry-title")
    if not title_el:
        title_el = soup.find("h1")
    if not title_el:
        return None

    title = title_el.get_text(strip=True)

    name_match = re.match(r"Матрас\s+Lineaflex\s+(\S+)\s*\(([^)]+)\)", title)
    if not name_match:
        return None

    name_en = name_match.group(1)
    name_ru = name_match.group(2)

    desc_el = soup.select_one(
        ".woocommerce-product-details__short-description, .product-short-description"
    )
    description = desc_el.get_text(strip=True) if desc_el else None

    price = _extract_price(html)
    specs = _extract_specs_block(html)

    category_links = soup.select(
        ".posted_in a, .product_meta a, span.posted_in a[rel='tag']"
    )
    category = None
    for link in category_links:
        text = link.get_text(strip=True).lower()
        if text in CATEGORY_NAMES_RU or text in [k.lower() for k in CATEGORY_NAMES_RU]:
            category = text
            break

    height = specs.get("height") or _extract_spec(html, "Высота")
    firmness = specs.get("firmness")
    max_weight = specs.get("max_weight")
    springs = specs.get("springs")

    return MattressData(
        name_en=name_en,
        name_ru=name_ru,
        url=url,
        category=category or "unknown",
        height=height,
        firmness=firmness,
        spring_type=None,
        springs_per_place=springs,
        max_weight=max_weight,
        description=description,
        price_from=price,
    )


def parse_category_page(html: str, category_key: str) -> list[dict]:
    soups = BeautifulSoup(html, "html.parser")
    products: list[dict] = []

    product_links = soups.select(
        "a.woocommerce-LoopProduct-link, "
        "li.product a.woocommerce-LoopProduct-link, "
        "h2.woocommerce-loop-product__title a"
    )
    if not product_links:
        product_links = soups.select("li.product a[href*='/product/']")
    if not product_links:
        product_links = soups.find_all("a", href=re.compile(r"/product/"))

    seen = set()
    for link in product_links:
        href = link.get("href")
        if not href:
            continue
        if href in seen:
            continue
        seen.add(href)
        full_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        title_el = link.select_one(
            "h2.woocommerce-loop-product__title, "
            ".woocommerce-loop-product__title, "
            ".product-title"
        )
        title = title_el.get_text(strip=True) if title_el else ""

        name_match = re.match(r"Матрас\s+Lineaflex\s+(\S+)", title)
        if not name_match:
            alt_match = re.search(r"Матрас\s+Lineaflex\s+(\S+)", html)
            if alt_match:
                products.append(
                    {
                        "title": title or alt_match.group(0),
                        "url": full_url,
                        "category": category_key,
                    }
                )
            continue

        products.append(
            {
                "title": title,
                "url": full_url,
                "category": category_key,
            }
        )

    return products


async def fetch_page(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        resp = await client.get(url, timeout=30.0, follow_redirects=True)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


async def parse_all() -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}

    async with httpx.AsyncClient(
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=30.0,
    ) as client:
        for cat_key, cat_url in CATEGORIES.items():
            logger.info(f"Parsing category: {cat_key} ({cat_url})")
            html = await fetch_page(client, cat_url)
            if not html:
                logger.warning(f"No data for {cat_key}")
                continue

            products = parse_category_page(html, cat_key)
            result[cat_key] = products

            for product in products:
                detail_html = await fetch_page(client, product["url"])
                if detail_html:
                    mattress = parse_product_card(detail_html, product["url"])
                    if mattress:
                        product["details"] = mattress
                await asyncio.sleep(0.5)

    return result


def format_as_catalog_text(
    data: dict[str, list[dict]],
) -> str:
    lines: list[str] = [
        "--- МАТРАСЫ LineaFlex (автоматически обновлено из lineaflexshop.ru) ---",
        "",
        (
            "Матрасы подбираются под размер кровати. "
            "Стандартные размеры: 80×190, 90×190, 120×190, 140×190, "
            "160×200, 180×200, 200×200. "
            "Рекомендуем брать матрас в комплекте с кроватью "
            "для идеального сочетания."
        ),
        "",
    ]

    for cat_key, products in data.items():
        if not products:
            continue
        ru_name = CATEGORY_NAMES_RU.get(cat_key, cat_key)
        lines.append(f"{ru_name}:")

        for prod in products:
            details = prod.get("details")
            if details:
                parts = [f"{details.name_en} ({details.name_ru})"]
                if details.height:
                    parts.append(f"{details.height} см")
                if details.firmness:
                    parts.append(f"жёсткость: {details.firmness.lower()}")
                if details.springs_per_place:
                    parts.append(f"пружины: {details.springs_per_place} шт/сп.м.")
                if details.max_weight:
                    parts.append(f"нагрузка до {details.max_weight} кг")
                if details.price_from:
                    parts.append(f"от {details.price_from} ₽")

                specs_line = ", ".join(parts)
                lines.append(f"- {details.url} — {specs_line}")

                if details.description:
                    desc = details.description
                    if len(desc) > 200:
                        desc = desc[:197] + "..."
                    lines.append(f"  {desc}")
            else:
                title = prod.get("title", "")
                url = prod.get("url", "")
                lines.append(f"- {url} — {title}")

            lines.append("")

        lines.append("")

    return "\n".join(lines)


def build_fallback_catalog() -> str:
    return """--- МАТРАСЫ LineaFlex (Тюмень) ---

Матрасы подбираются под размер кровати. Стандартные размеры: 80×190, 90×190, 120×190, 140×190, 160×200, 180×200, 200×200. Рекомендуем брать матрас в комплекте с кроватью для идеального сочетания.

Эконом (Linea Economica):
- Viola (мягкий, 18 см): пружины Боннель, Ergoflex 2 см, нагрузка до 90 кг. Размеры 80×190, 90×190.
- Tulpano (мягкий, 18 см): пружины Боннель, Ergoflex, чехол Premium Eco. Размеры 80×190, 90×190.
- Rosa (мягкий, 18 см): пружины Боннель, Ergoflex. Размеры 80×190, 90×190.
- Edelweiss Эко 16 (средний, 16 см): беспружинный, кокос + ППУ, нагрузка до 120 кг. Размеры 80×190, 90×190.
- Edelweiss Эко 20 (средний, 20 см): беспружинный, кокос + ППУ. Размеры 80×190, 90×190.
- Edelweiss Эко 10 (средний, 10 см): беспружинный тонкий. Размеры 80×190, 90×190.

Популярный (Linea Popolare):
- Alba (мягкий, 22 см): 7-зональные пружины Magic Zone, Ergoflex, нагрузка 120–140 кг. Все размеры.
- Paola (средний, 22 см): пружины Magic Zone, Ergoflex + кокос, нагрузка 120 кг. Все размеры.
- Cosma (средний/жёсткий, 22 см): пружины Magic Multi (1000/сп.м.), Ergoflex + кокос, нагрузка 140 кг. Все размеры.
- Donata (жёсткий, 21 см): беспружинный, кокос + Ergoflex, нагрузка 160 кг. Все размеры.
- Edelweiss Classico (средний, 16 см): пружины Боннель, кокос + ППУ, нагрузка 120 кг. Все размеры.

Анатомический (Linea Anatomica):
- Azalia (средний, 25 см): 2-зональные пружины Magic Zone, Ergoflex, нагрузка 120–140 кг. Все размеры.
- Primula Lux (средний, 25 см): пружины Magic Zone, Ergoflex + кокос, нагрузка 140 кг. Все размеры.
- Azalia Lux (жёсткий, 25 см): пружины Magic Chess, кокос, чехол «зима-лето», нагрузка 170 кг. Все размеры.
- Lilia Lux (средний, 25 см): пружины Magic Chess, кокос + латекс, нагрузка 170 кг. Все размеры.
- Lilia (средний/мягкий, 25 см): пружины Magic Chess, латекс + кокос, нагрузка 170 кг. Все размеры.
- Dalia (жёсткий, 25 см): беспружинный, кокос, чехол «зима-лето», нагрузка 160 кг. Все размеры.
- Peonia (средний, 25 см): пружины Magic Chess, Ergoflex + сизаль, нагрузка 170 кг. Все размеры.
- Camelia Lux (средний, 25 см): пружины Magic Chess, кокос + Ergoflex, нагрузка 160 кг. Все размеры.

Эргономический (Linea Ergonomica):
- Sognio (средний, 24 см): пружины Magic Multi (1000/сп.м.), Memory Antracite, чехол Premium Silver, нагрузка 140 кг. Все размеры.
- Sonnodoro (мягкий, 24 см): пружины Magic Multi, Memory Antracite с микромассажем, нагрузка 140 кг. Все размеры.
- Paradiso (средний/мягкий, 24 см): 5-зональные пружины, Memory Antracite Supertouch, нагрузка 140 кг. Все размеры.
- Energia (жёсткий, 26 см): пружины 500/м², кокос, нагрузка 120 кг. Все размеры.
- Superba (средний/жёсткий, 26 см): пружины 500/м², кокос + латекс + Ergoflex, нагрузка 120 кг. Все размеры.
- Evoluzione (средний/мягкий, 26 см): пружины 500/м², Ergoflex + латекс, нагрузка 120 кг. Размеры 80×190, 90×190/200.
- Elegante (средний, 23 см): пружины Magic Multi, Memory, чехол Premium, нагрузка 140 кг. Все размеры.

Рациональный (Linea Razionale):
- Venta (мягкий, 19 см): пружины Magic Comfort (500/сп.м.), Ergoflex 2 см, чехол жаккард, нагрузка 120 кг. Все размеры.
- Demetra (средний/мягкий, 21 см): пружины Magnifica, Ergoflex + кокос 1 см, трикотаж, нагрузка 120 кг. Все размеры.
- Verdeo (средний, 20 см): пружины Magic Comfort, Ergoflex + кокос, съёмный трикотаж, нагрузка 120 кг. Все размеры.
- Silena (средний, 20 см): пружины Magic Comfort, NeoLatex + кокос, нагрузка 120 кг. Все размеры.
- Bertina (средний, 22 см): пружины Magnifica (500/сп.м.), Ergoflex + кокос, нагрузка 120 кг. Все размеры.
- Bettino (мягкий, 20 см): пружины Magic Comfort, NeoLatex, нагрузка 120 кг. Все размеры.
- Luaro (мягкий, 20 см): пружины Magnifica, Ergoflex 2 см, нагрузка 120 кг. Все размеры.
- Bruno (средний/мягкий, 22 см): пружины Magic Comfort, NeoLatex + кокос + Ergoflex, нагрузка 120 кг. Все размеры.

Премиум (Linea Luxury):
- Divine 30 (средний/мягкий, 30 см): пружины Magic Chess Elite (800/сп.м.), Memory Massage, конский волос, чехол Gold/Silver, нагрузка до 200 кг. Размер 140×180.
- Dolce Vita 30 (средний/мягкий, 30 см): пружины Magic Multi Elite (2000/сп.м.), Memory, латекс, нагрузка до 200 кг. Размер 140×180.
- Kristal 30 (средний, 30 см): Ergoflex Multizone Fresh (7 зон), нагрузка до 200 кг. Размер 140×180.
- Gloria 30 (средний, 30 см): Ergoflex Multizone Fresh, нагрузка до 200 кг. Размер 140×180.
- Серия 42 см — топпер в комплекте, нагрузка до 200 кг.

FormaFlex (беспружинный):
- Magnolia (мягкий/средний, 19 см): натуральный латекс 3 зоны + Memory Antracite, чехол Skytouch, нагрузка 140 кг. Все размеры.
- Active Gel (средний, 22 см): охлаждающий гель, нагрузка 140 кг. Размеры 80×190, 90×190/200.
- Ergolife (средний, 19 см): пена Ergoflex, чехол с микрофиброй, нагрузка 140 кг. Размеры 80×190, 90×190/200.

Di Arte (ручная работа):
- Bernini (средний, 23 см): 7-зональные пружины Magic Zone (550/сп.м.), Ergoflex + кокос, чехол Extra Premium Quattro Stagioni, нагрузка 160 кг. Все размеры.

Детские (Linea Bambina):
- Bony, Sinti, Tony, Villi, Kitty — детские матрасы.
"""


async def main() -> str:
    logger.info("Starting LineaFlex parser...")
    data = await parse_all()
    catalog_text = format_as_catalog_text(data)

    # If parsing returned nothing, use fallback
    if not any(products for products in data.values()):
        logger.warning("Parser returned no data, using fallback catalog")
        return build_fallback_catalog()

    return catalog_text


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    result = asyncio.run(main())
    print(result)
