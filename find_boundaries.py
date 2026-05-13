import sys
sys.stdout.reconfigure(encoding="utf-8")
lines = open("bot/services/ai_service.py", encoding="utf-8").readlines()
for i, l in enumerate(lines, 1):
    if i > 210 and ('"""' in l.strip() or "КАТАЛОГ" in l):
        print(f"{i}: {l.rstrip()[:80]}")
