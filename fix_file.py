import sys
sys.stdout.reconfigure(encoding="utf-8")

path = "bot/services/ai_service.py"
content = open(path, encoding="utf-8").read()

# Find the closing """ of SYSTEM_PROMPT (the new one we added)
marker = 'используй функцию search_catalog."""'
close_idx = content.index(marker) + len(marker)

# Find FACT_EXTRACTION_PROMPT (next valid code)
next_valid = content.index("FACT_EXTRACTION_PROMPT")

# Content between them is garbage catalog leftovers
garbage = content[close_idx:next_valid]
print(f"Removing {len(garbage)} chars of garbage catalog data")

# Remove it (keep empty lines between)
new_content = content[:close_idx] + "\n\n\n" + content[next_valid:]

with open(path, "w", encoding="utf-8") as f:
    f.write(new_content)

# Verify
import py_compile
try:
    py_compile.compile(path, doraise=True)
    print("File is valid Python!")
except py_compile.PyCompileError as e:
    print(f"SYNTAX ERROR: {e}")
