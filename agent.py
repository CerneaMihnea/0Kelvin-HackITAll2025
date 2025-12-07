import json
import google.generativeai as genai

API_KEY = "AIzaSyAhengV9JPXsRGYn-fV5kaV427QJQKOPoQ"
genai.configure(api_key=API_KEY)

def load_emag_data():
    with open("emag_filters_and_categories.json", "r", encoding="utf-8") as f:
        return json.load(f)


def build_ai_prompt(user_prompt, emag_data):
    # extragem automat pattern-urile din JSON
    url_examples = []

    for fname, items in emag_data["filters"].items():
        for it in items:
            url_examples.append(it["url_path"])

    # pattern dedus automat:
    # - orice apare între "/label/" și "/<context>" este un filtru valid
    # - filtrul de preț este detectabil pentru că are forma pret,intre-X-si-Y

    auto_patterns = """
Acestea sunt toate pattern-urile reale extrase automat din HTML-ul eMAG:

{}
    
Observații:
- Orice filtru are structura: /label/<ceva>/<context>
- Filtre multiple se unesc cu: /filter/A/B/C
- Prețul are forma observată: pret,intre-<min>-si-<max>
- Rating-ul are forma observată: rating,star-<min>
""".format("\n".join(url_examples))

    return f"""
Ești un agent specializat în generarea URL-urilor corecte pentru eMAG.ro.

Ai acces la tot dump-ul brut de categorii și filtre extras din HTML:
CATEGORII:
{json.dumps(emag_data["categories"], indent=2, ensure_ascii=False)}

FILTRE:
{json.dumps(emag_data["filters"], indent=2, ensure_ascii=False)}

PATTERN-URI DEDUSE AUTOMAT DIN HTML:
{auto_patterns}

REGULILE INVĂȚATE AUTOMAT:
1. Toate filtrele respectă SEF-ul furnizat în url_path
2. Dacă un filtru nu există în JSON, îl deduci logic din pattern-uri
3. PREȚUL trebuie interpretat cu formula:
   /label/pret,intre-<min>-si-<max>/
4. Pentru rating:
   /label/rating,star-<min>/
5. Tu ești responsabil să găsești categoria potrivită, să extragi toate filtrele relevante și să construiești doar structura JSON finală.

TREBUIE SĂ RETURNZI STRICT JSON-ul:

{{
  "category": "<exact category name>",
  "filters": [
      {{
         "filter_name": "Pret",
         "min": 50,
         "max": 200
      }},
      {{
         "filter_name": "Culoare",
         "option_label": "Negru"
      }}
  ]
}}

NU returna text explicativ.
NU returna alte câmpuri.

Cerința utilizatorului este:
\"{user_prompt}\"
"""






def ai_select_filters(user_prompt):
    emag_data = load_emag_data()
    prompt = build_ai_prompt(user_prompt, emag_data)

    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content(prompt)

    # Extragere text corectă
    raw = response.candidates[0].content.parts[0].text.strip()

    # Curățare markup / fencing
    raw = raw.replace("```json", "").replace("```", "").strip()

    # Parsare JSON
    try:
        ai_output = json.loads(raw)
    except Exception as e:
        print("NU AM PUTUT PARSA JSON:\n", raw)
        raise e

    return ai_output