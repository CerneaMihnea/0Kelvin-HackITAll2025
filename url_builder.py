import json

# Ordinea REALĂ a filtrelor eMAG, bazată pe UI
FILTER_PRIORITY = [
    "culoare",
    "material",
    "brand",
    "pret",
    "rating",
    "timp de livrare estimat",
    "pentru",
    "emag genius",
    "produse la oferta",
    "disponibilitate",
    "super pret",
    "disponibil prin easybox",
    "livrat de",
    "disponibil in showroom"
]


def load_emag_data():
    with open("emag_filters_and_categories.json", "r", encoding="utf-8") as f:
        return json.load(f)


def filter_priority(f):
    name = f.get("filter_name", "").lower()
    if name in FILTER_PRIORITY:
        return FILTER_PRIORITY.index(name)
    return 9999


def build_emag_url_from_ai(ai_output, emag_data):

    # -------------------------
    # 1. Categoria
    # -------------------------
    selected_cat = next(
        (c for c in emag_data["categories"]
         if c["name"].lower() == ai_output["category"].lower()),
        None
    )

    if not selected_cat:
        raise Exception(f"Categoria '{ai_output['category']}' nu există în JSON.")

    category_path = selected_cat["url"]
    category_path = category_path.split("https://www.emag.ro")[-1].split("?")[0]

    parts = category_path.strip("/").split("/")
    cat_label = "/".join(parts[:2])
    cat_context = parts[2]
    cat_end = parts[3]

    # -------------------------
    # 2. Sortăm filtrele după ordinea REALĂ eMAG
    # -------------------------
    sorted_filters = sorted(ai_output["filters"], key=filter_priority)

    filter_parts = []

    # -------------------------
    # 3. Procesăm filtrele
    # -------------------------
    for f in sorted_filters:
        fname = f.get("filter_name", "").lower()

        # === PREȚ ===
        if fname == "pret":
            minv = f.get("min")
            maxv = f.get("max")
            if minv is not None and maxv is not None:
                filter_parts.append(f"pret,intre-{minv}-si-{maxv}")
            continue

        # === RATING ===
        if fname == "rating":
            min_rating = f.get("min")
            if min_rating is not None:
                filter_parts.append(f"rating,star-{min_rating}")
            continue

        # === STANDARD ===
        option = f.get("option_label")
        if not option:
            continue

        option = option.lower()

        if f["filter_name"] in emag_data["filters"]:
            match = next(
                (x for x in emag_data["filters"][f["filter_name"]]
                 if x["label"].lower() == option),
                None
            )
            if match:
                raw = match["url_path"]
                clean = raw.split("/filter/")[-1].split("/")[0]
                filter_parts.append(clean)

    # -------------------------
    # 4. Construim URL-ul final
    # -------------------------
    if filter_parts:
        filter_block = "/filter/" + "/".join(filter_parts)
    else:
        filter_block = ""

    final_url = f"https://www.emag.ro/{cat_label}{filter_block}/{cat_context}/{cat_end}"

    # normalize slashes
    final_url = final_url.replace("https:/", "https://")
    final_url = final_url.replace("///", "/").replace("//", "/")
    final_url = final_url.replace("https:/", "https://")

    return final_url
