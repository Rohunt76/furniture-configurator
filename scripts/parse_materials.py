"""
scripts/parse_materials.py
Парсить актуальні дані з viyar.ua через Selenium (headless Chrome).
Запускається через GitHub Actions щодня о 05:00 UTC.
"""

import json
import time
import re
from datetime import datetime, timezone
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

MATERIALS_PATH = Path("data/materials.json")
DELAY = 2.0


def make_driver() -> webdriver.Chrome:
    opts = Options()
    opts.add_argument("--headless")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1280,800")
    opts.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    return webdriver.Chrome(options=opts)


def parse_material(driver: webdriver.Chrome, url: str) -> dict:
    result = {
        "nayvnist": None,
        "price_site": None,
        "aktsia": False,
        "chystyy_rozmir": False,
    }

    try:
        driver.get(url)
        wait = WebDriverWait(driver, 12)

        # Чекаємо поки завантажиться ціна
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".price, [class*='price']")))
        except Exception:
            pass

        time.sleep(1.5)

        # --- Ціна ---
        for selector in [
            ".item-price .price-val",
            ".price-block .price",
            "[class*='price-val']",
            "[class*='item-price']",
            ".price",
        ]:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in els:
                txt = el.text.strip()
                raw = re.sub(r"[^\d,.]", "", txt).replace(",", ".")
                if raw:
                    try:
                        result["price_site"] = round(float(raw), 2)
                        break
                    except ValueError:
                        continue
            if result["price_site"]:
                break

        # --- Наявність ---
        for selector in ["[class*='avail']", "[class*='stock']", "[class*='status']"]:
            els = driver.find_elements(By.CSS_SELECTOR, selector)
            for el in els:
                txt = el.text.strip().lower()
                if txt:
                    result["nayvnist"] = "є" in txt or "наявн" in txt or "в наяв" in txt
                    break
            if result["nayvnist"] is not None:
                break

        # --- Акція ---
        akts_els = driver.find_elements(By.CSS_SELECTOR,
            "[class*='sale'], [class*='discount'], [class*='promo'], [class*='znyzh'], [class*='акці']"
        )
        result["aktsia"] = any(el.is_displayed() for el in akts_els)

        # --- Чистий розмір ---
        page_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        result["chystyy_rozmir"] = "чистий розмір" in page_text or "чистовой размер" in page_text

    except Exception as e:
        print(f"    ПОМИЛКА: {e}")

    return result


def main():
    if not MATERIALS_PATH.exists():
        print(f"Файл не знайдено: {MATERIALS_PATH}")
        return

    with open(MATERIALS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    materials = data["materials"]
    total = len(materials)
    print(f"Починаємо парсинг {total} матеріалів...")

    driver = make_driver()
    updated = 0

    try:
        for i, mat in enumerate(materials):
            url = mat.get("url_supplier")
            if not url:
                continue

            print(f"[{i+1}/{total}] {mat['id']} — {mat['name'][:40]}...")
            parsed = parse_material(driver, url)
            print(f"    ціна={parsed['price_site']} | наявн={parsed['nayvnist']} | акція={parsed['aktsia']}")
            mat.update(parsed)
            updated += 1
            time.sleep(DELAY)
    finally:
        driver.quit()

    data["_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    with open(MATERIALS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nГотово. Оновлено {updated}/{total}. Час: {data['_updated']}")


if __name__ == "__main__":
    main()
