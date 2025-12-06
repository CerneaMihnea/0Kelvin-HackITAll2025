from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

import requests
from bs4 import BeautifulSoup
import re

urls = [
    "https://www.emag.ro/set-3-tricouri-galben-simple-barbati-model-elegant-marime-s-100-bumbac-yellow-1strigl03ga01/pd/D9J0TH3BM/",
    "https://www.emag.ro/pantaloni-scurti-de-lucru-engelbert-strauss-e-s-motion-summer-model-es-95590-52-de-vara-bej-khaki-marimea-52-5900415893493/pd/DSJH0J3BM/",
    "https://www.emag.ro/mister-tee-tricou-unisex-supradimensionat-cu-imprimeu-grafic-si-text-maro-galben-pal-albastru-xs-mt1840-soft-yellow-xs/pd/DM7M593BM/"
        ]

# PAGINA PRODUCATOR
def extr_vendor_page(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        vendor_link = soup.select_one('a[href*="v?ref=see_vendor_page"]')

        if vendor_link:
            relative_path = vendor_link.get('href')
            full_link = urljoin(url, relative_path)
            return full_link
        else:
            print(f"Could not find a link containing 'v?ref=see_vendor_page' for {url}")
            return None

    except Exception as e:
        print(f"Error in extr_vendor_page for {url}: {e}")
        return None


# vendor_page = extr_vendor_page(url)

# NUME FIRMA PRODUCATOR
def extr_vendor_name(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # The specific label to look for
        target_label1 = "Denumirea companiei:"
        target_label2 = "Cod unic de inregistrare:"

        company_name = None
        company_code = None

        # 1. Find the <strong> tag containing the exact label
        strong_tag = soup.find('strong', string=target_label1)
        if strong_tag:
            company_name = strong_tag.next_sibling.strip()

        strong_tag = soup.find('strong', string=target_label2)
        if strong_tag:
            company_code = strong_tag.next_sibling.strip()

        if company_name and company_code:
            return company_name, company_code
        else:
            print(f"Could not extract company name/code from {url}")
            return None, None

    except Exception as e:
        print(f"Error in extr_vendor_name for {url}: {e}")
        return None, None

# name, code = extr_vendor_name(vendor_page)
# print(name)
# print(code)


# LINK PT listafirme.ro
def create_company_site_url(company_name, company_code):
    result = ""
    slug = company_name.lower()

    slug = slug.replace('.', '')

    slug = slug.replace(',', '')

    slug = re.sub(r'\s+', '-', slug.strip())
    slug = f"{slug}-{company_code}"
    result = f"https://listafirme.ro/{slug}/"
    return result

# lista_url = create_company_site_url(name, code)
# print(lista_url)

def clean_num(text):
    clean = text.replace(' ', '').replace('\xa0', '').strip()
    clean = clean.replace(',', '')
    return clean

# DATE DIN TABEL listafirme.ro
def get_latest_financials(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = session.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 1. Find the specific container for the balance sheet ("bilanț")
        bilant_section = soup.find('div', id='bilant')

        if not bilant_section:
            return None

        # 2. Find the table inside that section
        table = bilant_section.find('table')
        if not table:
            return None

        tbody = table.find('tbody')
        rows = tbody.find_all('tr') if tbody else table.find_all('tr')

        if len(rows) < 3:
            return None

        last_row = rows[-3]
        last_row_cells = last_row.find_all('td')

        if not last_row_cells:
            return None

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

    except Exception as e:
        return None


# VERIFICA FIRMA MICA
def check_small_business(cifra_afaceri, active, nr_salariati):
    if cifra_afaceri <= 50000000 and active <= 50000000 and nr_salariati < 50:
        return True
    else:
        return False


# CREDIBILITATE
def compute_credibility(profit, datorii, age):
    f_s = profit / (profit + (abs(datorii) ** (1/2)))
    a_s = age / (age + 3)
    factor = 0.8 * f_s + 0.2 * a_s
    factor *= 100
    return int(factor)

def process_url(url, companies_dict, links_dict, lock):
    """Process a single URL and return the result"""
    session = requests.Session()
    
    try:
        vendor_page = extr_vendor_page(url, session)
        if not vendor_page:
            return None
        
        name, code = extr_vendor_name(vendor_page, session)
        if not name or not code:
            return None
        
        with lock:
            links_dict[url] = name
            
            # Check if we already processed this company
            if name in companies_dict:
                return url, name, companies_dict[name]
        
        lista_firme_url = create_company_site_url(name, code)
        financials = get_latest_financials(lista_firme_url, session)
        
        if financials is None:
            with lock:
                companies_dict[name] = (False, 0)
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
        print(f"Error processing {url}: {e}")
        return None
    finally:
        session.close()


# Main processing with parallel execution
start_time = time.time()

links = {}
companies = {}
results = []
lock = Lock()

# Use ThreadPoolExecutor to process URLs in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    # Submit all tasks
    future_to_url = {executor.submit(process_url, url, companies, links, lock): url for url in urls}
    
    # Collect results as they complete
    for future in as_completed(future_to_url):
        result = future.result()
        if result:
            results.append(result)

# Print URLs for small businesses
for url in links.keys():
    if links[url] in companies:
        a, b = companies[links[url]]
        if a:
            print(url)

end_time = time.time()
elapsed_time = end_time - start_time
print(f"\nExecution time: {elapsed_time:.2f} seconds")

# print(url for url in links.keys() and companies[links[url]][0] == True)
    #print(compute_credibility(profit, datorii, age))

