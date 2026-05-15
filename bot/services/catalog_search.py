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


def _word_match_count(line: str, words: list[str]) -> int:
    lowered = line.lower()
    return sum(1 for w in words if w in lowered)


def search_catalog(query: str) -> str:
    """Search the furniture catalog by query string.

    Matches brand names, model names, categories, and descriptions.
    """
    catalog = _load_catalog()
    if not catalog:
        return ""

    query_lower = query.lower()
    words = query_lower.split()
    n_words = len(words)

    lines = catalog.split("\n")
    matched: list[str] = []
    current_section = ""
    active_sections: set[str] = set()
    shown_sections: set[str] = set()
    # For single-word queries, any match in a section header is enough
    # For multi-word queries, require at least 2 words to match a section
    min_section_match = 1 if n_words == 1 else max(2, n_words // 2 + 1)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        is_section_header = stripped.startswith("===") or stripped.startswith("---")

        if is_section_header:
            current_section = stripped
            if _word_match_count(stripped, words) >= min_section_match:
                active_sections.add(stripped)
                matched.append(stripped)
                shown_sections.add(stripped)
            continue

        count = _word_match_count(stripped, words)
        line_in_active_section = current_section in active_sections

        if count == 0:
            continue

        # In a matching section → include all matching lines
        if line_in_active_section:
            if current_section not in shown_sections:
                matched.append(current_section)
                shown_sections.add(current_section)
            matched.append(stripped)
            continue

        # Outside matching section → only include if ≥2 words match
        if count >= 2 or n_words == 1:
            matched.append(stripped)

    if not matched:
        return ""

    result = "\n".join(matched[:30])
    if len(matched) > 30:
        result += f"\n... и ещё {len(matched) - 30} результатов"
    return result
