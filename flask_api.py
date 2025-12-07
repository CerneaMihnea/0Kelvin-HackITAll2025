from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re
import time
import json
import os
from datetime import datetime
import stripe

# ===== Import AI conversation system =====
from agent import (
    start_conversation,
    continue_conversation,
    reset_conversation,
    load_emag_data
)

from url_builder import build_emag_url_from_ai


# =====================================================
# FLASK APP INIT
# =====================================================

app = Flask(__name__)
CORS(app)

stripe.api_key = os.getenv('STRIPE_SECRET_KEY', 'sk_test_51SbXPE0K3XOps5QbrJJGSdqs8c8FMaE1sv69Dv6F0JxMNdfoXVyGDhPdjHy5sbXK1RfnmmaTQow3cjcUUxci4CON00IhmoaKv1')


# =====================================================
# GLOBAL CONVERSATION STATE
# =====================================================

conversation_state = None


# =====================================================
# SEARCH HISTORY UTILS
# =====================================================

SEARCH_HISTORY_FILE = 'search_history.json'

def load_search_history():
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_search_history(history):
    try:
        with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving search history: {e}")

def add_to_search_history(prompt, product_count):
    history = load_search_history()
    history.append({
        'id': len(history),
        'prompt': prompt,
        'productCount': product_count,
        'timestamp': datetime.now().isoformat()
    })
    if len(history) > 50:
        history = history[-50:]
    save_search_history(history)



# ===================================================================
# SCRAPING + COMPANY VALIDATION CODE (UNCHANGED FROM YOUR VERSION)
# ===================================================================

def get_product_list(base_url, max_pages=2):
    """
    Extracts product URL, name, image and price from eMAG listing pages.
    Robust version compatible with NEW (2024–2025) layout.
    """

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    all_products = []

    for page in range(1, max_pages + 1):

        # Build paginated URL
        if page == 1:
            target_url = base_url
        else:
            if base_url.endswith('/c'):
                target_url = base_url[:-2] + f'/p{page}/c'
            else:
                target_url = f"{base_url}/p{page}/c"

        print("Scraping:", target_url)

        try:
            response = requests.get(target_url, headers=headers)
            if response.status_code == 404:
                break

            soup = BeautifulSoup(response.text, 'html.parser')

            # =====================================================
            # UNIVERSAL DETECTION OF PRODUCT CARDS
            # =====================================================
            cards = []

            # Old layout
            cards.extend(soup.find_all("div", class_="card-item"))

            # New layout (2024–2025)
            cards.extend(soup.select("div.card-v2"))

            # Another variation seen in A/B tests
            cards.extend(soup.select("section.card-v2"))

            # Remove duplicate tags
            unique_cards = []
            seen_ids = set()
            for c in cards:
                if id(c) not in seen_ids:
                    seen_ids.add(id(c))
                    unique_cards.append(c)

            cards = unique_cards

            # =====================================================
            # PARSE EACH PRODUCT CARD
            # =====================================================
            for card in cards:
                product = {}

                # ==========================================
                # PRODUCT URL
                # ==========================================
                url = card.get("data-url")

                if not url:
                    a_tag = card.find("a", href=True)
                    if a_tag:
                        url = a_tag["href"]

                if not url:
                    continue

                if url.startswith("/"):
                    url = "https://www.emag.ro" + url
                elif not url.startswith("http"):
                    url = "https://www.emag.ro/" + url

                product["url"] = url

                # ==========================================
                # PRODUCT NAME (UNIVERSAL SCRAPER)
                # ==========================================
                name = None
                name_selectors = [
                    "a.card-v2-title",
                    "h2.card-v2-title a",
                    "a[data-zone='title']",
                    "a.js-product-url",
                    "h2 a",
                    "a.product-title",
                    ".card-body a.card-v2-title",
                ]

                for selector in name_selectors:
                    elem = card.select_one(selector)
                    if elem:
                        txt = elem.get_text(strip=True)
                        if txt:
                            name = txt
                            break

                # Fallback: any <a> with meaningful text
                if not name:
                    for a in card.find_all("a"):
                        txt = a.get_text(strip=True)
                        if txt and len(txt) > 4:
                            name = txt
                            break

                product["name"] = name or "Unknown Product"

                # ==========================================
                # PRODUCT IMAGE (UNIVERSAL SCRAPER)
                # ==========================================
                img_elem = card.select_one("img")
                img_src = None

                if img_elem:
                    img_src = img_elem.get("data-src") or img_elem.get("src")

                if img_src:
                    if img_src.startswith("//"):
                        img_src = "https:" + img_src
                    elif img_src.startswith("/"):
                        img_src = "https://www.emag.ro" + img_src

                product["image"] = img_src

                # ==========================================
                # PRODUCT PRICE (UNIVERSAL SCRAPER)
                # ==========================================
                price_selectors = [
                    ".product-new-price",
                    ".card-v2-price .product-new-price",
                    "p.product-new-price",
                    "span.product-new-price",
                    ".price-overview .product-new-price",
                ]

                price_val = None

                for sel in price_selectors:
                    elem = card.select_one(sel)
                    if elem:
                        txt = elem.get_text(strip=True)
                        cleaned = re.sub(r"[^\d.,]", "", txt)
                        cleaned = cleaned.replace(".", "").replace(",", ".")
                        match = re.search(r"\d+\.?\d*", cleaned)

                        if match:
                            try:
                                price_val = float(match.group())
                                break
                            except:
                                pass

                product["price"] = price_val

                # DONE — append card
                all_products.append(product)

            # Slow scraping avoidance
            time.sleep(0.2)

        except Exception as e:
            print("Scraping error:", e)
            continue

    return all_products



def extr_vendor_page(url, session):
    try:
        response = session.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        v = soup.select_one('a[href*="v?ref=see_vendor_page"]')
        if not v:
            return None
        return urljoin(url, v.get('href'))
    except:
        return None


def extr_vendor_name(url, session):
    try:
        r = session.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        n = soup.find('strong', string="Denumirea companiei:")
        c = soup.find('strong', string="Cod unic de inregistrare:")
        if n and c:
            return n.next_sibling.strip(), c.next_sibling.strip()
    except:
        return None, None
    return None, None


def create_company_site_url(name, code):
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower().strip()) + f"-{code}"
    return f"https://listafirme.ro/{slug}/"


def clean_num(t):
    return re.sub(r'\D', '', t)


def get_latest_financials(url, session):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    try:
        response = session.get(url, headers=headers)
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


def check_small_business(cifra, active, nr):
    return cifra <= 50_000_000 and active <= 50_000_000 and nr < 50


def compute_credibility(profit, datorii, age):
    try:
        f = profit / (profit + (abs(datorii)**0.5)) if profit + abs(datorii)**0.5 != 0 else 0
        a = age / (age + 3)
        return int((0.8*f + 0.2*a)*100)
    except:
        return 0


def process_url(product, companies_cache, links_dict, lock):
    url = product['url']
    session = requests.Session()

    try:
        vendor_page = extr_vendor_page(url, session)
        if not vendor_page:
            return None

        name, code = extr_vendor_name(vendor_page, session)
        if not name or not code:
            return None

        with lock:
            if name in companies_cache:
                is_valid = companies_cache[name]['is_valid']
                score = companies_cache[name]['score']
                return url, name, is_valid, score, product

        firm_url = create_company_site_url(name, code)
        fin = get_latest_financials(firm_url, session)

        if not fin:
            res = {'is_valid': False, 'score': 0}
        else:
            cifra, active, nr, profit, datorii, age = fin
            if check_small_business(cifra, active, nr):
                score = compute_credibility(profit, datorii, age)
                res = {'is_valid': True, 'score': score}
            else:
                res = {'is_valid': False, 'score': 0}

        with lock:
            companies_cache[name] = res

        return url, name, res['is_valid'], res['score'], product

    except:
        return None
    finally:
        session.close()



# ===================================================================
# MAIN API ENDPOINT — FIXED TO USE AI CONVERSATION
# ===================================================================

@app.route('/api/search', methods=['POST'])
def search_products():
    global conversation_state

    try:
        data = request.get_json()
        prompt = data.get('prompt', '').strip()

        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        print("User prompt:", prompt)

        # RESET conversation
        if prompt.lower() in ["reset", "sterge", "șterge", "reset conversatie", "sterge tot"]:
            reset_conversation()
            conversation_state = None
            return jsonify({"success": True, "message": "Context resetat."})

        # FIRST MESSAGE
        if conversation_state is None:
            warm_msg, ai_output = start_conversation(prompt)
            conversation_state = ai_output
            print("AI:", warm_msg)
        else:
            # FOLLOW-UP MESSAGE
            ai_output = continue_conversation(prompt)
            conversation_state = ai_output
            print("AI: Filtre actualizate")

        # Build eMAG URL
        search_url = build_emag_url_from_ai(ai_output, load_emag_data())
        print("Generated URL:", search_url)

        # SCRAPE PRODUCTS
        products = get_product_list(search_url)
        seen = {}
        unique = []

        for p in products:
            url = p['url']
            if url not in seen:
                seen[url] = True
                unique.append(p)

        # VENDOR CHECK
        companies_cache = {}
        links_dict = {}
        lock = Lock()
        valid = []

        with ThreadPoolExecutor(max_workers=10) as exec:
            futures = {
                exec.submit(process_url, p, companies_cache, links_dict, lock): p
                for p in unique
            }

            for f in as_completed(futures):
                res = f.result()
                if not res:
                    continue
                url, company_name, is_valid, score, prod = res
                if is_valid:
                    valid.append({
                        "url": url,
                        "productName": prod.get("name", "Unknown"),
                        "companyName": company_name,
                        "credibilityScore": score,
                        "imageUrl": prod.get("image", ""),
                        "price": prod.get("price", None)
                    })

        valid.sort(key=lambda x: x['credibilityScore'], reverse=True)

        add_to_search_history(prompt, len(valid))

        return jsonify({
            "success": True,
            "products": valid,
            "count": len(valid),
            "url": search_url,
            "filters": ai_output
        })

    except Exception as e:
        print("ERROR:", e)
        return jsonify({'error': str(e)}), 500



# ===================================================================
# HEALTH & HISTORY ENDPOINTS
# ===================================================================

@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


@app.route('/api/search-history', methods=['GET'])
def get_history():
    return jsonify({"success": True, "history": load_search_history()})

@app.route('/api/create-checkout-session', methods=['POST'])
def create_checkout_session():
    """Create Stripe checkout session"""
    try:
        data = request.get_json()
        items = data.get('items', [])
        
        if not items:
            return jsonify({'error': 'No items in cart'}), 400
        
        # Calculate total amount (in cents for Stripe)
        total_amount = 0
        line_items = []
        
        for item in items:
            price = item.get('price', 0)
            quantity = item.get('quantity', 1)
            # Ensure price is a valid number
            if price and isinstance(price, (int, float)) and price > 0:
                # Convert RON to cents (assuming 1 RON = 100 cents, adjust as needed)
                amount_cents = int(price * 100 * quantity)
                total_amount += amount_cents
                
                line_items.append({
                    'price_data': {
                        'currency': 'ron',  # Romanian Leu
                        'product_data': {
                            'name': item.get('productName', 'Product'),
                            'description': f"From {item.get('companyName', 'Unknown Company')}",
                        },
                        'unit_amount': int(price * 100),  # Convert to cents
                    },
                    'quantity': quantity,
                })
        
        if total_amount == 0:
            return jsonify({'error': 'Invalid cart total'}), 400
        
        # Get frontend URL from request origin or use default
        frontend_url = request.headers.get('Origin', 'http://localhost:3000')
        if not frontend_url.startswith('http'):
            frontend_url = 'http://localhost:3000'
        
        # Create Stripe checkout session
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f'{frontend_url}/cart/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{frontend_url}/cart',
        )
        
        return jsonify({
            'success': True,
            'sessionId': checkout_session.id
        })
        
    except stripe.error.StripeError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error creating checkout session: {e}")
        return jsonify({'error': str(e)}), 500

# ===================================================================
# START FLASK
# ===================================================================

if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")