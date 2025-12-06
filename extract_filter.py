import json
from bs4 import BeautifulSoup

def extract_all_filters(html):
    soup = BeautifulSoup(html, "html.parser")

    modal_data = soup.find("script", {"id": "grid-controls-v2-filter-modal-data"})
    if not modal_data:
        raise Exception("Nu am găsit block-ul JSON cu filtre.")

    data = json.loads(modal_data.text)
    raw_filters = data["filters"]["items"]

    filters = {}

    for f in raw_filters:
        filter_name = f["name"].strip()
        filters[filter_name] = []

        for item in f["items"]:
            entry = {
                "label": item["name"],
                "value_id": item["id"],
                "url_base": item["url"]["desktop_base"],
                "url_path": item["url"]["path"]
            }

            if "count" in item:
                entry["count"] = item["count"]

            filters[filter_name].append(entry)

    return filters


def extract_categories(html):
    soup = BeautifulSoup(html, "html.parser")
    categories = []

    for a in soup.select('a[data-type="category"]'):
        categories.append({
            "name": a.get_text(strip=True),
            "url": a["href"]
        })

    for a in soup.select('a.js-sidebar-tree-url'):
        name_tag = a.select_one(".category-name")
        name = name_tag.get_text(strip=True) if name_tag else a.get_text(strip=True)

        categories.append({
            "name": name,
            "url": a["href"]
        })

    # Unique
    seen = set()
    clean = []
    for c in categories:
        if c["url"] not in seen:
            seen.add(c["url"])
            clean.append(c)

    return clean


# === RUN SCRIPT ===
with open("Articole pentru EL eMAG.ro.html", "r", encoding="utf-8") as f:
    html = f.read()

filters = extract_all_filters(html)
categories = extract_categories(html)

output = {
    "categories": categories,
    "filters": filters
}

with open("emag_filters_and_categories.json", "w", encoding="utf-8") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print("Fișier generat: emag_filters_and_categories.json")
