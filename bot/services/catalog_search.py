from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_catalog_text: str | None = None


def _load_catalog() -> str:
    global _catalog_text
    if _catalog_text is not None:
        return _catalog_text
    path = Path(__file__).parent / "catalog_data.txt"
    if path.exists():
        _catalog_text = path.read_text(encoding="utf-8")
        logger.info(f"Catalog loaded: {len(_catalog_text)} chars")
    else:
        _catalog_text = ""
        logger.warning("catalog_data.txt not found")
    return _catalog_text


_BRAND_KEYWORDS: dict[str, list[str]] = {
    "калинка": ["калинка"],
    "опрайм": ["опрайм"],
    "oprime": ["опрайм", "oprime"],
    "ривалли": ["ривалли", "rivalli"],
    "rivalli": ["ривалли", "rivalli"],
    "андреа": ["андреа", "andrea"],
    "andrea": ["андреа", "andrea"],
    "homelike18": ["homelike18", "хоумлайк"],
    "frendom": ["frendom", "френдом"],
    "lineaflex": ["lineaflex", "линеафлекс"],
}


def _detect_brand(words: list[str]) -> str | None:
    """Detect brand from query words."""
    for w in words:
        for brand, keywords in _BRAND_KEYWORDS.items():
            if w in keywords:
                return brand
    return None


def _section_matches_brand(section_header: str, brand: str) -> bool:
    """Check if a section header belongs to the given brand."""
    header_lower = section_header.lower()
    keywords = _BRAND_KEYWORDS.get(brand, [])
    return any(kw in header_lower for kw in keywords)


def _word_match_count(line: str, words: list[str]) -> int:
    lowered = line.lower()
    return sum(1 for w in words if w in lowered)


def search_catalog(query: str) -> str:
    """Search the furniture catalog by query string.

    Matches brand names, model names, categories, and descriptions.
    If a known brand is mentioned in the query, results are restricted
    to only that brand's sections.
    """
    catalog = _load_catalog()
    if not catalog:
        return ""

    query_lower = query.lower()
    words = query_lower.split()
    brand_filter = _detect_brand(words)

    lines = catalog.split("\n")
    matched: list[str] = []
    inside_brand_section = (
        brand_filter is None
    )  # if no brand filter, accept all sections

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_section_header = stripped.startswith("===") or stripped.startswith("---")

        if is_section_header:
            if brand_filter:
                inside_brand_section = _section_matches_brand(stripped, brand_filter)
            else:
                inside_brand_section = True
            continue

        # Skip lines outside the brand-filtered section
        if not inside_brand_section:
            continue

        count = _word_match_count(stripped, words)
        if count == 0:
            continue

        matched.append(stripped)

    if not matched:
        return ""

    result = "\n".join(matched[:30])
    if len(matched) > 30:
        result += f"\n... и ещё {len(matched) - 30} результатов"
    return result
