import json
import google.generativeai as genai

API_KEY = "AIzaSyCw2Vdd4-BOvk4g4y-hG8efxsGC08rNU90aaaaaaa"
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
""".format(
        "\n".join(url_examples)
    )

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


# ==========================================================
#   SUPORT PENTRU CONVERSAȚIE (context + rafinare filtre)
# ==========================================================

# Starea curentă a conversației (ultimul JSON generat)
conversation_state = None  # {"category": "...", "filters": [...]}


def reset_conversation():
    """
    Resetează contextul conversației (categoria și filtrele curente).
    """
    global conversation_state
    conversation_state = None


def start_conversation(user_prompt):
    """
    Pornește o conversație nouă:
    - întoarce un mesaj "cald" (explicativ)
    - întoarce JSON-ul inițial (category + filters)
    """
    global conversation_state

    warm_message = (
        f'Am înțeles: "{user_prompt}". '
        "Aleg categoria potrivită și filtrele de pe eMAG pentru tine..."
    )

    ai_output = ai_select_filters(user_prompt)
    conversation_state = ai_output
    print(conversation_state)
    return warm_message, ai_output


def build_refine_prompt(user_message, current_state, emag_data):
    """
    Construiește prompt-ul pentru rafinarea JSON-ului existent.
    """
    url_examples = []
    for fname, items in emag_data["filters"].items():
        for it in items:
            url_examples.append(it["url_path"])

    auto_patterns = """
Acestea sunt toate pattern-urile reale extrase automat din HTML-ul eMAG:

{}
    
Observații:
- Orice filtru are structura: /label/<ceva>/<context>
- Filtre multiple se unesc cu: /filter/A/B/C
- Prețul are forma observată: pret,intre-<min>-si-<max>
- Rating-ul are forma observată: rating,star-<min>
""".format(
        "\n".join(url_examples)
    )

    return f"""
Ești un agent specializat în ACTUALIZAREA unui JSON de filtre pentru eMAG.ro.

Ai acces la tot dump-ul brut de categorii și filtre extras din HTML:
CATEGORII:
{json.dumps(emag_data["categories"], indent=2, ensure_ascii=False)}

FILTRE:
{json.dumps(emag_data["filters"], indent=2, ensure_ascii=False)}

PATTERN-URI DEDUSE AUTOMAT DIN HTML:
{auto_patterns}

REGULILE:
1. Categoria NU se schimbă decât dacă utilizatorul cere explicit o altă categorie.
   Exemple: cere schimbare de categorie:
     - "nu mai vreau tricouri, vreau blugi"
     - "caut pantaloni"
     - "vreau haine pentru femei"
   Dacă utilizatorul NU cere clar o categorie nouă, păstrezi categoria EXACT cum este în JSON-ul curent.
   
2. Filtrele se actualizează doar cu ce cere utilizatorul.

3. Dacă utilizatorul spune clar că vrea ceva complet diferit
   (ex: "schimb tot", "vreau altceva", "reset", "sterge tot", "de la zero"),
   IGNORI JSON-ul curent și generezi unul NOU de la zero.

4. Daca vreau in mesajul user ului folosesc "si" adauga la url ul curent , noua caracteristica

5. PREȚUL trebuie interpretat cu formula:
   /label/pret,intre-<min>-si-<max>/

6. Rating:
   /label/rating,star-<min>/

7. TREBUIE SĂ RETURNZI STRICT JSON-ul:

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

JSON-UL CURENT ESTE:
{json.dumps(current_state, indent=2, ensure_ascii=False)}

MESAJUL NOU AL UTILIZATORULUI ESTE:
\"{user_message}\"

NU returna text explicativ.
NU returna alte câmpuri.
"""


def ai_refine_filters(user_message, current_state):
    """
    Apelează LLM-ul pentru a rafina JSON-ul curent pe baza mesajului nou.
    """
    emag_data = load_emag_data()
    prompt = build_refine_prompt(user_message, current_state, emag_data)

    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    response = model.generate_content(prompt)

    raw = response.candidates[0].content.parts[0].text.strip()
    raw = raw.replace("```json", "").replace("```", "").strip()

    try:
        ai_output = json.loads(raw)
    except Exception as e:
        print("NU AM PUTUT PARSA JSON LA RAFINARE:\n", raw)
        raise e

    return ai_output


def continue_conversation(user_message):
    global conversation_state

    if conversation_state is None:
        _, ai_output = start_conversation(user_message)
        return ai_output

    old_category = conversation_state["category"]

    # cuvinte care indică REAL schimbarea categoriei
    category_keywords = [
        "tricou", "tricouri",
        "blugi", "pantaloni",
        "camasa", "camasi", "cămăși",
        "hanorac", "hanorace",
        "trening", "pijamale",
        "bluza", "bluze",
    ]

    explicit_change = any(word in user_message.lower() for word in category_keywords)

    ai_output = ai_refine_filters(user_message, conversation_state)

    # -------------------------------------------------------------
    # 🔒 Pas 1: Blocăm TOT timpul categoria să nu se schimbe
    # -------------------------------------------------------------
    ai_output["category"] = old_category

    # -------------------------------------------------------------
    # 🔒 Pas 2: DOAR dacă userul cere explicit o altă categorie
    #           → verificăm dacă există în JSON și abia atunci o schimbăm
    # -------------------------------------------------------------
    if explicit_change:
        emag_categories = [
            c["name"].lower()
            for c in load_emag_data()["categories"]
        ]

        # Modelul a generat o nouă categorie?
        if ai_output["category"].lower() in emag_categories:
            ai_output["category"] = ai_output["category"]  # o păstrăm
        else:
            ai_output["category"] = old_category  # invalidă, revenim la vechea categorie

    conversation_state = ai_output
    return ai_output
