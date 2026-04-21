"""
scripts/parse_materials.py
Парсить актуальні дані з viyar.ua і оновлює data/materials.json.
Запускається через GitHub Actions щодня о 05:00 UTC.
"""

import json
import time
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

MATERIALS_PATH = Path("data/materials.json")
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "uk,en;q=0.9",
}
DELAY = 1.5  # секунд між запитами


def fetch_page(url: str) -> BeautifulSoup | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        print(f"  ПОМИЛКА: {url} → {e}")
        return None


def parse_material(url: str) -> dict:
    """Повертає словник з актуальними полями або порожній dict при помилці."""
    result = {
        "nayvnist": None,
        "price_site": None,
        "aktsia": False,
        "chystyy_rozmir": False,
    }

    soup = fetch_page(url)
    if soup is None:
        return result

    # --- Ціна ---
    price_el = (
        soup.select_one(".item-price .price")
        or soup.select_one("[data-price]")
        or soup.select_one(".price-value")
    )
    if price_el:
        raw = re.sub(r"[^\d.,]", "", price_el.get_text())
        raw = raw.replace(",", ".")
        try:
            result["price_site"] = round(float(raw), 2)
        except ValueError:
            pass

    # --- Наявність ---
    avail_el = (
        soup.select_one(".availability")
        or soup.select_one("[class*='avail']")
        or soup.select_one("[class*='stock']")
    )
    if avail_el:
        text = avail_el.get_text(strip=True).lower()
        result["nayvnist"] = "в наявності" in text or "є в наявності" in text

    # --- Акція ---
    result["aktsia"] = bool(
        soup.select_one(".label-sale")
        or soup.select_one("[class*='discount']")
        or soup.select_one("[class*='promo']")
    )

    # --- Чистий розмір ---
    page_text = soup.get_text().lower()
    result["chystyy_rozmir"] = "чистий розмір" in page_text or "чистовой размер" in page_text

    return result


def main():
    if not MATERIALS_PATH.exists():
        print(f"Файл не знайдено: {MATERIALS_PATH}")
        return

    with open(MATERIALS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    materials = data["materials"]
    total = len(materials)
    updated = 0

    print(f"Починаємо парсинг {total} матеріалів...")

    for i, mat in enumerate(materials):
        url = mat.get("url_supplier")
        if not url:
            continue

        print(f"[{i+1}/{total}] {mat['id']} — {mat['name'][:40]}...")
        parsed = parse_material(url)

        mat.update(parsed)
        updated += 1
        time.sleep(DELAY)

    data["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(MATERIALS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nГотово. Оновлено {updated}/{total} матеріалів. Час: {data['_updated']}")


if __name__ == "__main__":
    main()
