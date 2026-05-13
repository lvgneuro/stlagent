import sys
sys.stdout.reconfigure(encoding="utf-8")
lines = open("bot/services/ai_service.py", encoding="utf-8").readlines()
for i, l in enumerate(lines, 1):
    s = l.strip()
    if i > 200 and (s.startswith("---") or s == '"""'):
        print(f"{i}: {l.rstrip()[:80]}")
