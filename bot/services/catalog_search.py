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


def search_catalog(query: str) -> str:
    """Search the furniture catalog by query string.

    Matches brand names, model names, categories, and descriptions.
    """
    catalog = _load_catalog()
    if not catalog:
        return ""

    query_lower = query.lower()
    words = query_lower.split()

    lines = catalog.split("\n")
    matched = []
    current_section = ""

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Track section headers
        if stripped.startswith("===") or stripped.startswith("---"):
            current_section = stripped
            if all(w in stripped.lower() for w in words) or any(
                w in stripped.lower() for w in words
            ):
                matched.append(stripped)
            continue

        is_match = all(w in stripped.lower() for w in words) or any(
            w in stripped.lower() for w in words
        )
        if is_match:
            if current_section and (
                not matched or matched[-1] != current_section
            ):
                matched.append(current_section)
            matched.append(stripped)

    if not matched:
        return ""

    result = "\n".join(matched[:30])
    if len(matched) > 30:
        result += f"\n... и ещё {len(matched) - 30} результатов"
    return result
