import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re
import time
import json
import os

# Importăm excepția specifică de la Google (dacă este instalată) sau prindem orice eroare
try:
    from google.api_core.exceptions import ResourceExhausted
except ImportError:
    ResourceExhausted = Exception

# --- MODULES FROM YOUR PROJECT ---
from agent import ai_select_filters, load_emag_data
from url_builder import build_emag_url_from_ai

CACHE_FILE = "companies_cache.json"


# ==========================================
# PART 0: JSON CACHE MANAGEMENT
# ==========================================

def load_cache_from_json():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            print(f"[CACHE] S-au încărcat datele pentru {len(data)} firme.")
            return data
    except Exception as e:
        print(f"[CACHE] Eroare la citirea JSON: {e}")
        return {}


def save_cache_to_json(cache_data):
    try:
        with open(CACHE_FILE, 'w', encoding='utf-8') as f:
            json.dump(cache_data, f, ensure_ascii=False, indent=4)
        print(f"[CACHE] Baza de date salvată ({len(cache_data)} firme).")
    except Exception as e:
        print(f"[CACHE] Eroare la salvarea JSON: {e}")


# ==========================================
# PART 1: eMAG SEARCH & PRODUCT EXTRACTION
# ==========================================

def generate_emag_url(prompt):
    emag_data = load_emag_data()
    max_retries = 3
    ai_output = None

    for attempt in range(max_retries):
        try:
            ai_output = ai_select_filters(prompt)
            break
        except Exception as e:
            if "429" in str(e) or "ResourceExhausted" in str(e) or isinstance(e, ResourceExhausted):
                wait_time = 60
                print(f"[AI Limit] Aștept {wait_time}s... (Încercarea {attempt + 1})")
                time.sleep(wait_time)
            else:
                raise e

    if ai_output is None: return None
    return build_emag_url_from_ai(ai_output, emag_data)


def get_product_list(base_url, max_pages=2):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36"}
    if not base_url: return []
    all_product_urls = []

    for page in range(1, max_pages + 1):
        if page == 1:
            target_url = base_url
        else:
            if base_url.endswith('/c'):
                target_url = base_url[:-2] + f'/p{page}/c'
            else:
                target_url = f"{base_url}/p{page}/c"

        print(f"Scraping URL: {target_url}")
        try:
            response = requests.get(target_url, headers=headers, timeout=10)
            if response.status_code == 404: break

            soup = BeautifulSoup(response.text, 'html.parser')
            page_urls = []
            cards = soup.find_all('div', class_='card-item')

            for card in cards:
                url = card.get('data-url')
                if not url:
                    link_tag = card.find('a', href=True)
                    if link_tag: url = link_tag['href']
                if url: page_urls.append(url)

            count = len(page_urls)
            print(f" -> Găsit {count} produse pe pagina {page}.")
            all_product_urls.extend(page_urls)
            if count < 60: break
            time.sleep(1)
        except Exception:
            continue

    return all_product_urls


# ==========================================
# PART 2: VENDOR VALIDATION (CORRECTED)
# ==========================================

def clean_num(text):
    """
    Curăță textul de spații și puncte pentru a-l face int.
    Elimină caracterele non-numerice.
    """
    clean = text.replace(' ', '').replace('\xa0', '').strip()
    clean = clean.replace('.', '').replace(',', '')
    if not clean or not clean[-1].isdigit():
        return "0"
    return clean


def extr_vendor_page(url, session):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.text, 'html.parser')
        vendor_link = soup.select_one('a[href*="v?ref=see_vendor_page"]')

        if vendor_link:
            relative_path = vendor_link.get('href')
            full_link = urljoin(url, relative_path)
            return full_link
        else:
            return None
    except Exception:
        return None


def extr_vendor_name(url, session):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None, None

        soup = BeautifulSoup(response.text, 'html.parser')
        target_label1 = "Denumirea companiei:"
        target_label2 = "Cod unic de inregistrare:"

        company_name = None
        company_code = None

        strong_tag = soup.find('strong', string=target_label1)
        if strong_tag:
            company_name = strong_tag.next_sibling.strip()

        strong_tag = soup.find('strong', string=target_label2)
        if strong_tag:
            company_code = strong_tag.next_sibling.strip()

        if company_name and company_code:
            return company_name, company_code
        else:
            return None, None
    except Exception:
        return None, None


def create_company_site_url(company_name, company_code):
    slug = company_name.lower()
    slug = slug.replace('.', '').replace(',', '')
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = f"{slug}-{company_code}"
    return f"https://listafirme.ro/{slug}/"


def get_latest_financials(url, session):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.text, 'html.parser')
        bilant_section = soup.find('div', id='bilant')
        if not bilant_section: return None

        table = bilant_section.find('table')
        if not table: return None

        tbody = table.find('tbody')
        # Dacă există tbody, luăm rândurile de acolo, altfel din tabel direct
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')

        if len(rows) < 2: return None

        # 1. Găsirea rândului cu datele cele mai recente (trebuie să sărim peste header)
        data_row = None

        # Iterăm prin primele câteva rânduri pentru a găsi primul care începe cu un AN (număr)
        for row in rows:
            cells = row.find_all('td')
            if not cells: continue

            first_cell_text = clean_num(cells[0].get_text(strip=True))

            # Verificăm dacă prima celulă este un an valid (ex: > 2000)
            if first_cell_text.isdigit() and int(first_cell_text) > 2000:
                data_row = row
                break  # Am găsit cel mai recent an

        if not data_row:
            return None

        # 2. Extragerea datelor din rândul identificat
        cells = data_row.find_all('td')
        if len(cells) < 8: return None

        cifra_afaceri = int(clean_num(cells[1].get_text()))
        profit = int(clean_num(cells[2].get_text()))
        datorii = int(clean_num(cells[3].get_text()))
        active_imob = int(clean_num(cells[4].get_text()))
        active_cir = int(clean_num(cells[5].get_text()))
        nr_salariati = int(clean_num(cells[7].get_text()))

        active = active_imob + active_cir

        # 3. Calculul vechimii (căutăm cel mai vechi an din listă)
        oldest_year = 2024  # default
        for i in range(len(rows) - 1, -1, -1):
            r_cells = rows[i].find_all('td')
            if not r_cells: continue
            txt = clean_num(r_cells[0].get_text(strip=True))
            if txt.isdigit() and int(txt) > 1900:
                oldest_year = int(txt)
                break

        age = 2025 - oldest_year

        return cifra_afaceri, active, nr_salariati, profit, datorii, age

    except Exception:
        return None


def check_small_business(cifra_afaceri, active, nr_salariati):
    # Praguri: CA <= 50M, Active <= 50M, Angajati < 50
    if cifra_afaceri <= 50000000 and active <= 50000000 and nr_salariati < 50:
        return True
    else:
        return False

# Am mai putea adauga criterii ca sa fie mai exact
def compute_credibility(profit, datorii, age):
    try:
        denominator = profit + (abs(datorii) ** 0.5)
        if denominator == 0:
            f_s = 0
        else:
            f_s = profit / denominator

        a_s = age / (age + 3)
        factor = 0.8 * f_s + 0.2 * a_s
        factor *= 100
        if factor > 100:
            factor = 100
        return int(factor)
    except:
        return 0


def process_url(url, companies_dict, links_dict, lock):
    session = requests.Session()
    try:
        vendor_page = extr_vendor_page(url, session)
        if not vendor_page: return None

        name, code = extr_vendor_name(vendor_page, session)
        if not name or not code: return None

        with lock:
            links_dict[url] = name
            # VERIFICARE CACHE
            if name in companies_dict:
                is_valid, score = companies_dict[name]
                if is_valid:
                    return url, name, (True, score)
                # Dacă e marcat ca invalid, verificăm dacă e o firmă mare (True rejection) sau eroare (False rejection)
                # Pentru siguranță, dacă a fost invalid, lăsăm invalid pentru a nu încetini,
                # dar ideal ar fi să re-verifici dacă ai avut bug-uri înainte.
                return url, name, (False, 0)

        lista_firme_url = create_company_site_url(name, code)
        financials = get_latest_financials(lista_firme_url, session)

        if financials is None:
            # Dacă nu găsim date, presupunem că nu e eligibil sau e eroare
            res = (False, 0)
        else:
            cifra_afaceri, active, nr_salariati, profit, datorii, age = financials

            if check_small_business(cifra_afaceri, active, nr_salariati):
                credibility = compute_credibility(profit, datorii, age)
                res = (True, credibility)
            else:
                # E firmă mare
                res = (False, 0)

        with lock:
            companies_dict[name] = res
        return url, name, res

    except Exception:
        return None
    finally:
        session.close()


# ==========================================
# MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    prompt = input("Ce vrei să cauți? ")

    print("\n[1] Generare URL eMAG...")
    search_url = generate_emag_url(prompt)

    if search_url:
        print(f"URL Categorie: {search_url}")
        print("[2] Se extrag produsele...")

        raw_urls = get_product_list(search_url, max_pages=2)
        raw_urls = list(set(raw_urls))
        total = len(raw_urls)
        print(f"S-au găsit {total} produse unice. Începe analiza firmelor...\n")

        # Încărcăm cache-ul la pornire (ȘTERGE companies_cache.json DACĂ AI AVUT REZULTATE PROASTE ÎNAINTE)
        if os.path.exists(CACHE_FILE):
            print("[INFO] Se folosește cache-ul existent. Șterge 'companies_cache.json' dacă vrei o verificare curată.")

        companies_cache = load_cache_from_json()
        lock = Lock()
        valid_urls = []

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {
                executor.submit(process_url, url, companies_cache, {}, lock): url
                for url in raw_urls
            }

            count = 0
            for future in as_completed(future_to_url):
                res = future.result()
                count += 1
                print(f"\rProgres: {count}/{total}", end="")
                if res and res[2][0]:  # if is_valid
                    valid_urls.append((res[0], res[1], res[2][1]))

        print(f"\n\nAnaliza gata în {time.time() - start_time:.2f}s.")

        save_cache_to_json(companies_cache)

        print(f"\nREZULTATE ({len(valid_urls)} produse de la firme mici validate):")
        valid_urls.sort(key=lambda x: x[2], reverse=True)

        for url, name, score in valid_urls:
            print(f"Firma: {name} | Scor: {score}")
            print(f"Link: {url}")
            print("-" * 40)
    else:
        print("Eroare la generarea URL-ului.")