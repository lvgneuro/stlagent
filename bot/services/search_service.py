from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request

from tavily import TavilyClient
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


class SearchService:
    STOP_LIST = [
        "askona",
        "аскона",
        "moon",
        "моон",
        "ormatek",
        "орматек",
        "arti mobili",
        "арти мобили",
        "pushe",
        "пуше",
        "erga",
        "эрга",
        "эргомебель",
        "8 марта",
        "братьев баженовых",
        "пинскдрев",
        "100 диванов",
        "мебельград",
        "33 комода",
        "диваны.ру",
        "диваны ру",
    ]

    def __init__(self) -> None:
        tavily_key = os.getenv("TAVILY_API_KEY")
        if not tavily_key:
            raise ValueError("TAVILY_API_KEY not found in .env file")
        self._tavily = TavilyClient(api_key=tavily_key)
        self._ddgs = DDGS()

    def _filter_stoplist(self, text: str) -> str:
        if not text:
            return text
        lines = text.split("\n")
        filtered = []
        for line in lines:
            lower = line.lower()
            if any(brand in lower for brand in self.STOP_LIST):
                continue
            filtered.append(line)
        result = "\n".join(filtered)
        return result if result.strip() else text

    def _search_web(self, query: str) -> str:
        """Try Tavily first, fall back to DuckDuckGo HTML backend."""
        result = self._search_tavily(query)
        if result:
            return result
        result = self._search_duckduckgo(query)
        return result if result else ""

    def _search_duckduckgo(self, query: str) -> str:
        try:
            results = list(self._ddgs.text(query, max_results=8, backend="html"))
            if not results:
                return ""
            summary = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                if not title or not body:
                    continue
                summary.append(f"- {title}: {body[:300]}")
            return "\n\n".join(summary) if summary else ""
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return ""

    def _search_tavily(self, query: str) -> str:
        try:
            results = self._tavily.search(
                query=query,
                max_results=5,
                include_answer=True,
            )
            if results.get("answer"):
                summary = [f"Краткий ответ: {results['answer'][:500]}"]
            else:
                summary = []
            if results.get("results"):
                for r in results["results"][:3]:
                    content = r.get("content", "")[:200]
                    title = r.get("title", "")
                    if title and content:
                        summary.append(f"- {title}: {content}")
            return "\n\n".join(summary) if summary else ""
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")
            return ""

    @staticmethod
    def _clean_query(raw: str) -> str:
        stop_words = {
            "дашь",
            "дай",
            "дайте",
            "знаешь",
            "знаете",
            "расскажи",
            "расскажите",
            "пожалуйста",
            "наконец",
            "есть",
            "можешь",
            "можете",
            "хочешь",
            "скажи",
            "найди",
            "покажи",
            "покажите",
            "ищу",
            "ищете",
            "нужен",
            "нужна",
            "нужно",
            "нужны",
            "подскажи",
            "может",
            "где",
            "когда",
            "как",
            "что",
            "зачем",
            "почему",
            "тебя",
            "меня",
            "мне",
            "тебе",
            "себя",
            "себе",
            "там",
            "тут",
            "здесь",
            "сейчас",
            "сегодня",
            "вчера",
            "завтра",
            "так",
            "сделать",
            "сделал",
            "сделали",
            "сделай",
            "сделаю",
            "делать",
            "делаю",
            "делаешь",
            "делаем",
            "делаете",
            "просто",
            "вообще",
            "ладно",
            "хорошо",
            "конечно",
            "ну",
            "ой",
            "ах",
            "эх",
            "вот",
            "это",
            "этот",
            "деплой",
            "деплоя",
            "деплою",
            "на",
            "от",
            "до",
            "про",
            "для",
            "без",
            "через",
            "мой",
            "моя",
            "моё",
            "мои",
            "моего",
            "моей",
            "моему",
            "твой",
            "твоя",
            "твоё",
            "твои",
            "ваш",
            "ваша",
            "ваше",
            "ваши",
            "же",
            "ж",
            "ли",
            "бы",
            "ведь",
            "даже",
            "уже",
        }
        import re

        words = re.findall(r"[а-яёa-z]+", raw.lower())
        kept = [w for w in words if w not in stop_words and len(w) > 1]
        return " ".join(kept) if kept else raw

    def _dedup_clean(self, clean: str, word: str) -> str:
        return " ".join(w for w in clean.split() if word not in w)

    @staticmethod
    def _fetch_json(url: str) -> dict | None:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as e:
            logger.warning(f"HTTP fetch failed for {url[:60]}: {e}")
            return None

    def _weather_api(self, city: str = "Тюмень") -> str:
        result = self._weather_openmeteo()
        if result:
            return result
        return self._weather_wttr(city)

    def _weather_openmeteo(self) -> str:
        try:
            data = self._fetch_json(
                "https://api.open-meteo.com/v1/forecast?"
                "latitude=57.15&longitude=65.53"
                "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
                "&daily=temperature_2m_max,temperature_2m_min,weather_code"
                "&timezone=auto&forecast_days=3"
            )
            if not data:
                return ""
            current = data.get("current", {})
            daily = data.get("daily", {})
            weather_codes = {
                0: "ясно",
                1: "преимущественно ясно",
                2: "переменная облачность",
                3: "пасмурно",
                45: "туман",
                48: "изморозь",
                51: "морось",
                53: "морось",
                55: "морось",
                61: "дождь",
                63: "дождь",
                65: "сильный дождь",
                71: "снег",
                73: "снег",
                75: "сильный снег",
                80: "ливень",
                81: "ливень",
                82: "сильный ливень",
                95: "гроза",
                96: "гроза с градом",
                99: "гроза с градом",
            }
            wc = current.get("weather_code", 0)
            desc = weather_codes.get(wc, f"код {wc}")
            lines = [
                f"Погода в Тюмени сейчас: {desc}",
                f"Температура: {current.get('temperature_2m', '?')}°C (ощущается как {current.get('apparent_temperature', '?')}°C)",
                f"Ветер: {current.get('wind_speed_10m', '?')} км/ч, влажность: {current.get('relative_humidity_2m', '?')}%",
            ]
            dates = daily.get("time", [])
            t_max = daily.get("temperature_2m_max", [])
            t_min = daily.get("temperature_2m_min", [])
            codes = daily.get("weather_code", [])
            for i in range(min(len(dates), 3)):
                d_desc = weather_codes.get(codes[i] if i < len(codes) else 0, "")
                lines.append(
                    f"\n{dates[i]}: {d_desc}, {t_min[i] if i < len(t_min) else '?'}..{t_max[i] if i < len(t_max) else '?'}°C"
                )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Open-Meteo API failed: {e}")
            return ""

    def _weather_wttr(self, city: str) -> str:
        try:
            data = self._fetch_json(
                f"https://wttr.in/{urllib.parse.quote(city)}?format=j1&lang=ru"
            )
            if not data:
                return ""
            current = data.get("current_condition", [{}])[0]
            forecast = data.get("weather", [])
            lines = [
                f"Погода в {city} сейчас: {current.get('lang_ru', [{}])[0].get('value', '')}",
                f"Температура: {current.get('temp_C', '?')}°C (ощущается как {current.get('FeelsLikeC', '?')}°C)",
                f"Ветер: {current.get('windspeedKmph', '?')} км/ч, влажность: {current.get('humidity', '?')}%",
            ]
            if len(forecast) > 1:
                for day in forecast[1:]:
                    desc = (
                        day.get("hourly", [{}])[0]
                        .get("lang_ru", [{}])[0]
                        .get("value", "")
                    )
                    lines.append(
                        f"\n{day.get('date', '')}: {desc}, {day.get('mintempC', '?')}..{day.get('maxtempC', '?')}°C"
                    )
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"wttr.in API failed: {e}")
            return ""

    def _currency_api(self) -> str:
        try:
            data = self._fetch_json("https://www.cbr-xml-daily.ru/daily_json.js")
            if not data:
                return ""
            valutes = data.get("Valute", {})
            usd = valutes.get("USD", {})
            eur = valutes.get("EUR", {})
            lines = ["Курсы валют ЦБ РФ на сегодня:"]
            if usd:
                lines.append(f"🇺🇸 Доллар США: {usd.get('Value', '?')} руб.")
            if eur:
                lines.append(f"🇪🇺 Евро: {eur.get('Value', '?')} руб.")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"Currency API failed: {e}")
            return ""

    def _horoscope_mailru(self, sign: str = "") -> str:
        try:
            sign_map: dict[str, tuple[str, str]] = {
                "овен": ("aries", "Овен"),
                "овна": ("aries", "Овен"),
                "овну": ("aries", "Овен"),
                "телец": ("taurus", "Телец"),
                "тельца": ("taurus", "Телец"),
                "тельцу": ("taurus", "Телец"),
                "близнецы": ("gemini", "Близнецы"),
                "близнецов": ("gemini", "Близнецы"),
                "рак": ("cancer", "Рак"),
                "рака": ("cancer", "Рак"),
                "раку": ("cancer", "Рак"),
                "лев": ("leo", "Лев"),
                "льва": ("leo", "Лев"),
                "льву": ("leo", "Лев"),
                "дева": ("virgo", "Дева"),
                "девы": ("virgo", "Дева"),
                "деве": ("virgo", "Дева"),
                "весы": ("libra", "Весы"),
                "весов": ("libra", "Весы"),
                "скорпион": ("scorpio", "Скорпион"),
                "скорпиона": ("scorpio", "Скорпион"),
                "скорпиону": ("scorpio", "Скорпион"),
                "стрелец": ("sagittarius", "Стрелец"),
                "стрельца": ("sagittarius", "Стрелец"),
                "стрельцу": ("sagittarius", "Стрелец"),
                "козерог": ("capricorn", "Козерог"),
                "козерога": ("capricorn", "Козерог"),
                "козерогу": ("capricorn", "Козерог"),
                "водолей": ("aquarius", "Водолей"),
                "водолея": ("aquarius", "Водолей"),
                "водолею": ("aquarius", "Водолей"),
                "рыбы": ("pisces", "Рыбы"),
                "рыб": ("pisces", "Рыбы"),
            }
            sign_lower = sign.lower()
            en_slug: str | None = None
            ru_name: str | None = None
            for ru, (en, name) in sign_map.items():
                if ru in sign_lower:
                    en_slug = en
                    ru_name = name
                    break

            if not en_slug or not ru_name:
                signs_list = [
                    "овен", "телец", "близнецы", "рак", "лев", "дева",
                    "весы", "скорпион", "стрелец", "козерог", "водолей", "рыбы",
                ]
                return (
                    "Гороскоп на сегодня. Напиши свой знак зодиака:\n"
                    + ", ".join(s.capitalize() for s in signs_list)
                )

            url = f"https://horo.mail.ru/prediction/{en_slug}/today/"
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode("utf-8", errors="replace")

            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html, "lxml")
            text = soup.get_text(separator=" ", strip=True)

            m = re.search(
                r"Рыбы\s+\d+\s+\S+\s*-\s*\d+\s+\S+\s+(.*?)(?:Финансы|$)",
                text,
                re.DOTALL,
            )
            if m:
                horo = m.group(1).strip()
                horo = re.sub(r"\s+", " ", horo)
                if len(horo) > 50:
                    return f"Гороскоп для {ru_name} на сегодня:\n{horo[:500]}"

            return f"Гороскоп для {ru_name} на сегодня: не удалось получить прогноз"
        except Exception as e:
            logger.warning(f"horo.mail.ru failed: {e}")
            return ""

    def search(self, query: str) -> str:
        try:
            clean = self._clean_query(query)
            lower = query.lower()

            if "погод" in lower:
                result = self._weather_api("Тюмень")
                if result:
                    logger.info(f"Weather API: found for '{query}'")
                    return self._filter_stoplist(result)
                clean_w = self._dedup_clean(clean, "погод")
                search_q = f"погода {clean_w}" if clean_w else "погода сегодня"
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            if "курс" in lower or "доллар" in lower or "евро" in lower:
                result = self._currency_api()
                if result:
                    logger.info(f"Currency API: found for '{query}'")
                    return self._filter_stoplist(result)
                search_q = (
                    f"курс {'доллара' if 'доллар' in lower else 'евро'} цб рф сегодня"
                )
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            is_zodiac = "гороскоп" in lower or any(
                w in lower
                for w in [
                    "овен", "овна", "телец", "тельца", "близнецы", "близнецов",
                    "рак", "рака", "лев", "льва", "дева", "девы",
                    "весы", "весов", "скорпион", "скорпиона",
                    "стрелец", "стрельца", "козерог", "козерога",
                    "водолей", "водолея", "рыбы", "рыб",
                ]
            )
            if is_zodiac:
                clean_h = self._dedup_clean(clean, "гороскоп")
                result = self._horoscope_mailru(clean_h)
                if result:
                    logger.info(f"Horoscope Mail.ru: found for '{query}'")
                    return self._filter_stoplist(result)
                search_q = (
                    f"гороскоп {clean_h} сегодня" if clean_h else "гороскоп сегодня"
                )
                result = self._filter_stoplist(self._search_web(search_q))
                if result:
                    return result

            result = self._filter_stoplist(self._search_web(clean if clean else query))
            return result if result else "No results found."
        except Exception as e:
            logger.error(f"Search error: {e}")
            return f"Search failed: {type(e).__name__}"


search_service = SearchService()
