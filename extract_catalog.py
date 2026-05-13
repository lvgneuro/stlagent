import sys
content = open("bot/services/ai_service.py", encoding="utf-8").read()

# Find the catalog section
start_marker = "--- КАТАЛОГ МЕБЕЛИ (обновлено 10.05.2026) ---"
start = content.index(start_marker)

# Find end: look for the closing """ of SYSTEM_PROMPT after the catalog
# by counting triple quotes
search_from = start + len(start_marker)
triple_quote_pos = []
idx = 0
while True:
    idx = content.find('"""', idx)
    if idx == -1:
        break
    triple_quote_pos.append(idx)
    idx += 3

# Find quotes AFTER the catalog start
end_quotes = [q for q in triple_quote_pos if q > start]
if end_quotes:
    end = end_quotes[0]
    catalog = content[start:end]
    print(f"Catalog: {len(catalog)} chars, {len(catalog)//3} tokens")
    with open("bot/services/catalog_data.txt", "w", encoding="utf-8") as f:
        f.write(catalog)
    print("OK")
else:
    print("ERROR: no closing quotes found")
