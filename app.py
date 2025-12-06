import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re
import time

# --- MODULES FROM YOUR PROJECT ---
from agent import ai_select_filters, load_emag_data
from url_builder import build_emag_url_from_ai


# ==========================================
# PART 1: eMAG SEARCH & PRODUCT EXTRACTION (UPDATED)
# ==========================================

def generate_emag_url(prompt):
    emag_data = load_emag_data()
    ai_output = ai_select_filters(prompt)
    url = build_emag_url_from_ai(ai_output, emag_data)
    return url


def get_product_list(base_url, max_pages=2):
    """
    Scrapes the search page for individual product URLs.
    Now iterates through pages 1 to max_pages.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    all_product_urls = []

    for page in range(1, max_pages + 1):
        # Construct the URL for the current page
        if page == 1:
            target_url = base_url
        else:
            # Logic based on your example: insert /p{page} before the final /c
            if base_url.endswith('/c'):
                target_url = base_url[:-2] + f'/p{page}/c'
            else:
                # Fallback if URL structure is different, just append
                target_url = f"{base_url}/p{page}/c"

        print(f"Scraping URL (Pagina {page}): {target_url}")

        try:
            response = requests.get(target_url, headers=headers, timeout=10)

            # If page doesn't exist (e.g. only 1 page of results), stop
            if response.status_code == 404:
                print(f"Pagina {page} nu există. Mă opresc.")
                break

            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            page_urls = []

            # Extract based on the structure identified previously
            cards = soup.find_all('div', class_='card-item')

            for card in cards:
                url = card.get('data-url')
                if not url:
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        url = link_tag['href']

                if url:
                    page_urls.append(url)

            print(f" -> Găsit {len(page_urls)} produse pe pagina {page}.")
            all_product_urls.extend(page_urls)

            # Be polite to the server between pages
            time.sleep(1)

        except Exception as e:
            print(f"Eroare la accesarea paginii {page}: {e}")
            # If one page fails, we try to continue or just return what we have
            continue

    return all_product_urls


# ==========================================
# PART 2: VENDOR VALIDATION LOGIC (UNCHANGED)
# ==========================================

def extr_vendor_page(url, session):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None

        soup = BeautifulSoup(response.text, 'html.parser')
        vendor_link = soup.select_one('a[href*="v?ref=see_vendor_page"]')

        if vendor_link:
            relative_path = vendor_link.get('href')
            return urljoin(url, relative_path)
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

        return company_name, company_code
    except Exception:
        return None, None


def create_company_site_url(company_name, company_code):
    slug = company_name.lower()
    slug = slug.replace('.', '').replace(',', '')
    slug = re.sub(r'\s+', '-', slug.strip())
    slug = f"{slug}-{company_code}"
    return f"https://listafirme.ro/{slug}/"


def clean_num(text):
    clean = text.replace(' ', '').replace('\xa0', '').strip()
    clean = clean.replace(',', '')
    if not clean or not clean[-1].isdigit():
        return "0"
    return clean


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
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')
        if len(rows) < 3: return None

        last_row = rows[-3]
        last_row_cells = last_row.find_all('td')
        if not last_row_cells: return None
        oldest_year = int(clean_num(last_row_cells[0].get_text(strip=True)))
        age = 2025 - oldest_year

        first_row = rows[0]
        cells = first_row.find_all('td')
        if len(cells) >= 8:
            cifra_afaceri = int(clean_num(cells[1].get_text()))
            profit = int(clean_num(cells[2].get_text()))
            datorii = int(clean_num(cells[3].get_text()))
            active_imob = int(clean_num(cells[4].get_text()))
            active_cir = int(clean_num(cells[5].get_text()))
            nr_salariati = int(clean_num(cells[7].get_text()))
            active = active_imob + active_cir

            return cifra_afaceri, active, nr_salariati, profit, datorii, age
        return None
    except Exception:
        return None


def check_small_business(cifra_afaceri, active, nr_salariati):
    if cifra_afaceri <= 50000000 and active <= 50000000 and nr_salariati < 50:
        return True
    return False


def compute_credibility(profit, datorii, age):
    try:
        denominator = profit + (abs(datorii) ** (1 / 2))
        if denominator == 0:
            f_s = 0
        else:
            f_s = profit / denominator

        a_s = age / (age + 3)
        factor = 0.8 * f_s + 0.2 * a_s
        return int(factor * 100)
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
            if name in companies_dict:
                return url, name, companies_dict[name]

        lista_firme_url = create_company_site_url(name, code)
        financials = get_latest_financials(lista_firme_url, session)

        if financials is None:
            with lock: companies_dict[name] = (False, 0)
            return url, name, (False, 0)

        cifra_afaceri, active, nr_salariati, profit, datorii, age = financials

        if check_small_business(cifra_afaceri, active, nr_salariati):
            credibility = compute_credibility(profit, datorii, age)
            with lock:
                companies_dict[name] = (True, credibility)
            return url, name, (True, credibility)
        else:
            with lock:
                companies_dict[name] = (False, 0)
            return url, name, (False, 0)

    except Exception as e:
        return None
    finally:
        session.close()


# ==========================================
# PART 3: MAIN EXECUTION
# ==========================================

if __name__ == "__main__":
    prompt = input("Ce vrei să cauți? ")

    print("Generare URL eMAG...")
    search_url = generate_emag_url(prompt)

    print(f"URL Categorie (Bază): {search_url}")
    print("Se extrag produsele (Pagina 1 și 2)...")

    # Call with max_pages=2 to include page 2
    raw_product_urls = get_product_list(search_url, max_pages=2)

    # Filter duplicates (sometimes promoted products appear on multiple pages)
    raw_product_urls = list(set(raw_product_urls))

    total_found = len(raw_product_urls)
    print(f"S-au găsit {total_found} produse unice în total. Începe filtrarea firmelor...")

    links_map = {}
    companies_cache = {}
    lock = Lock()
    valid_urls = []

    start_time = time.time()

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(process_url, url, companies_cache, links_map, lock): url
            for url in raw_product_urls
        }

        completed_count = 0
        for future in as_completed(future_to_url):
            result = future.result()
            completed_count += 1
            print(f"\rProgres: {completed_count}/{total_found}", end="")

            if result:
                url, name, (is_valid, score) = result
                if is_valid:
                    valid_urls.append((url, name, score))

    elapsed_time = time.time() - start_time
    print(f"\n\nAnaliza finalizată în {elapsed_time:.2f} secunde.")

    print(f"Am găsit {len(valid_urls)} produse de la firme mici cu scor de credibilitate bun:\n")

    valid_urls.sort(key=lambda x: x[2], reverse=True)

    for url, name, score in valid_urls:
        print(f"Firma: {name} | Scor: {score}")
        print(f"Link: {url}")
        print("-" * 40)