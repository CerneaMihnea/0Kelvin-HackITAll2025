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

# Import existing modules
from agent import ai_select_filters, load_emag_data
from url_builder import build_emag_url_from_ai

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize Stripe (use environment variable in production)
# IMPORTANT: Never commit your secret key to version control!
# Set it via environment variable: export STRIPE_SECRET_KEY=sk_test_...
stripe.api_key = os.getenv('STRIPE_SECRET_KEY', '')

SEARCH_HISTORY_FILE = 'search_history.json'

def load_search_history():
    """Load search history from file"""
    if os.path.exists(SEARCH_HISTORY_FILE):
        try:
            with open(SEARCH_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []

def save_search_history(history):
    """Save search history to file"""
    try:
        with open(SEARCH_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving search history: {e}")

def add_to_search_history(prompt, product_count):
    """Add a search to history"""
    history = load_search_history()
    history.append({
        'id': len(history),
        'prompt': prompt,
        'productCount': product_count,
        'timestamp': datetime.now().isoformat()
    })
    # Keep only last 50 searches
    if len(history) > 50:
        history = history[-50:]
    save_search_history(history)

# Reuse functions from app.py
def generate_emag_url(prompt):
    emag_data = load_emag_data()
    ai_output = ai_select_filters(prompt)
    url = build_emag_url_from_ai(ai_output, emag_data)
    return url


def get_product_list(base_url, max_pages=2):
    """
    Scrapes the search page for individual product URLs and extracts basic product info.
    Returns list of dicts with url, name, image, and price.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }

    all_products = []

    for page in range(1, max_pages + 1):
        if page == 1:
            target_url = base_url
        else:
            if base_url.endswith('/c'):
                target_url = base_url[:-2] + f'/p{page}/c'
            else:
                target_url = f"{base_url}/p{page}/c"

        try:
            response = requests.get(target_url, headers=headers, timeout=10)
            if response.status_code == 404:
                break
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            cards = soup.find_all('div', class_='card-item')
            
            for card in cards:
                product_info = {}
                
                # Extract URL
                url = card.get('data-url')
                if not url:
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        url = link_tag['href']
                
                if not url:
                    continue
                
                # Make URL absolute if needed
                if url.startswith('/'):
                    url = 'https://www.emag.ro' + url
                elif not url.startswith('http'):
                    url = 'https://www.emag.ro/' + url
                
                product_info['url'] = url
                
                # Extract product name from listing
                name_elem = card.find('a', class_='card-v2-title')
                if not name_elem:
                    name_elem = card.find('h2', class_='card-v2-title')
                if not name_elem:
                    name_elem = card.find('a', {'data-zone': 'title'})
                if name_elem:
                    product_info['name'] = name_elem.get_text(strip=True)
                
                # Extract image from listing
                img_elem = card.find('img')
                if img_elem:
                    img_src = img_elem.get('data-src') or img_elem.get('src')
                    if img_src:
                        if img_src.startswith('//'):
                            img_src = 'https:' + img_src
                        elif img_src.startswith('/'):
                            img_src = 'https://www.emag.ro' + img_src
                        product_info['image'] = img_src
                
                # Extract price from listing (much faster than visiting product page)
                price_elem = card.find('p', class_='product-new-price')
                if not price_elem:
                    price_elem = card.find('span', class_='product-new-price')
                if not price_elem:
                    price_elem = card.find('div', class_='product-new-price')
                
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    # Remove currency symbols and extract number
                    # Remove all non-digit characters except dots and commas
                    price_clean = re.sub(r'[^\d.,]', '', price_text)
                    # Replace comma with dot for decimal
                    price_clean = price_clean.replace(',', '.')
                    # Extract first number
                    price_match = re.search(r'(\d+\.?\d*)', price_clean)
                    if price_match:
                        try:
                            product_info['price'] = float(price_match.group(1))
                        except:
                            product_info['price'] = None
                    else:
                        product_info['price'] = None
                else:
                    product_info['price'] = None
                
                all_products.append(product_info)
            
            time.sleep(0.5)  # Reduced sleep time

        except Exception as e:
            print(f"Error scraping page {page}: {e}")
            continue

    return all_products


def extract_product_details(url, session):
    """
    Extract product name, image, and price from product page.
    """
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None, None, None

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product name
        product_name = None
        # Try multiple selectors for product name
        name_selectors = [
            'h1.page-title',
            'h1[itemprop="name"]',
            '.product-title',
            'h1.product-title',
            'h1'
        ]
        for selector in name_selectors:
            name_elem = soup.select_one(selector)
            if name_elem:
                product_name = name_elem.get_text(strip=True)
                break
        
        # Extract product image
        product_image = None
        # Try multiple selectors for product image
        image_selectors = [
            'img[itemprop="image"]',
            '.product-gallery img',
            '.product-page-gallery img',
            'img.product-gallery-image',
            '.product-main-image img'
        ]
        for selector in image_selectors:
            img_elem = soup.select_one(selector)
            if img_elem:
                product_image = img_elem.get('src') or img_elem.get('data-src')
                if product_image:
                    if product_image.startswith('//'):
                        product_image = 'https:' + product_image
                    elif product_image.startswith('/'):
                        product_image = 'https://www.emag.ro' + product_image
                    break
        
        # Fallback: try to find any large image
        if not product_image:
            img_tags = soup.find_all('img')
            for img in img_tags:
                src = img.get('src') or img.get('data-src')
                if src and ('product' in src.lower() or 'prod' in src.lower()):
                    if src.startswith('//'):
                        product_image = 'https:' + src
                    elif src.startswith('/'):
                        product_image = 'https://www.emag.ro' + src
                    else:
                        product_image = src
                    break

        # Extract product price - try multiple selectors
        product_price = None
        price_selectors = [
            '.product-new-price',
            '.product-page-price .product-new-price',
            '.product-page-pricing .product-new-price',
            '[itemprop="price"]',
            '.price-new',
            '.product-price .price',
            '.product-page-price-container .product-new-price',
            'p.product-new-price',
            'span.product-new-price'
        ]
        
        for selector in price_selectors:
            price_elem = soup.select_one(selector)
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Remove all non-digit characters except dots and commas
                price_clean = re.sub(r'[^\d.,]', '', price_text)
                # Replace comma with dot for decimal (Romanian format: 1.234,56 -> 1234.56)
                # First remove thousand separators (dots), then replace comma with dot
                if '.' in price_clean and ',' in price_clean:
                    # Has both: dots are thousands, comma is decimal
                    price_clean = price_clean.replace('.', '').replace(',', '.')
                elif ',' in price_clean:
                    # Only comma: could be decimal or thousands
                    if price_clean.count(',') == 1 and len(price_clean.split(',')[1]) <= 2:
                        # Likely decimal separator
                        price_clean = price_clean.replace(',', '.')
                    else:
                        # Likely thousands separator
                        price_clean = price_clean.replace(',', '')
                # Extract first number
                price_match = re.search(r'(\d+\.?\d*)', price_clean)
                if price_match:
                    try:
                        product_price = float(price_match.group(1))
                        if product_price > 0:  # Valid price
                            break
                    except:
                        pass
        
        # Fallback: search for price in meta tags or data attributes
        if not product_price:
            price_meta = soup.find('meta', {'itemprop': 'price'})
            if price_meta:
                try:
                    product_price = float(price_meta.get('content', ''))
                except:
                    pass
        
        # Another fallback: look for price in script tags (JSON-LD)
        if not product_price:
            scripts = soup.find_all('script', type='application/ld+json')
            for script in scripts:
                try:
                    import json
                    data = json.loads(script.string)
                    if isinstance(data, dict) and 'offers' in data:
                        offers = data['offers']
                        if isinstance(offers, dict) and 'price' in offers:
                            product_price = float(offers['price'])
                            break
                        elif isinstance(offers, list) and len(offers) > 0:
                            if 'price' in offers[0]:
                                product_price = float(offers[0]['price'])
                                break
                except:
                    continue

        return product_name, product_image, product_price
    except Exception as e:
        return None, None, None


def extr_vendor_page(url, session):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
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
        if response.status_code != 200:
            return None, None
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


def extract_company_address(url, session):
    """Extract company address from listafirme.ro page"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try to find address in various possible locations
        # Common patterns: "Adresa:", "Adresă:", "Sediu:", etc.
        address_labels = ["Adresa:", "Adresă:", "Sediu:", "Adresa sediului:"]
        address = None
        
        for label in address_labels:
            strong_tag = soup.find('strong', string=lambda text: text and label in text)
            if strong_tag:
                address = strong_tag.next_sibling
                if address:
                    address = address.strip()
                    break
        
        # Alternative: look for address in structured data or specific divs
        if not address:
            # Try to find in company info section
            info_section = soup.find('div', class_=lambda x: x and ('info' in x.lower() or 'company' in x.lower()))
            if info_section:
                address_elem = info_section.find(string=lambda text: text and any(label in text for label in address_labels))
                if address_elem:
                    parent = address_elem.find_parent()
                    if parent:
                        address = parent.get_text(strip=True)
                        # Remove the label
                        for label in address_labels:
                            address = address.replace(label, '').strip()
        
        return address if address else None
    except Exception as e:
        print(f"Error extracting address: {e}")
        return None


def geocode_address(address):
    """Convert address to coordinates using Google Maps Geocoding API"""
    google_api_key = "AIzaSyBUye6mET-kClCa7j2cu6NhwqVDmO_aZEM"
    if not google_api_key:
        return None, None
    
    try:
        geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': address,
            'key': google_api_key,
            'region': 'ro'  # Romania
        }
        response = requests.get(geocode_url, params=params, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'OK' and data['results']:
                location = data['results'][0]['geometry']['location']
                return location['lat'], location['lng']
        return None, None
    except Exception as e:
        print(f"Error geocoding address: {e}")
        return None, None


def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates using Haversine formula (returns km)"""
    from math import radians, sin, cos, sqrt, atan2
    
    if not all([lat1, lon1, lat2, lon2]):
        return None
    
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    # Earth radius in km
    R = 6371.0
    distance = R * c
    
    return round(distance, 1)


def get_latest_financials(url, session):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124 Safari/537.36'}
    try:
        response = session.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
        soup = BeautifulSoup(response.text, 'html.parser')
        bilant_section = soup.find('div', id='bilant')
        if not bilant_section:
            return None
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


def process_url(product_info, companies_dict, links_dict, lock):
    """
    Process a product URL to validate vendor and get company info.
    product_info is a dict with url, name, image, price from listing page.
    """
    url = product_info.get('url')
    product_name = product_info.get('name')
    product_image = product_info.get('image')
    product_price = product_info.get('price')
    
    session = requests.Session()
    try:
        vendor_page = extr_vendor_page(url, session)
        if not vendor_page:
            return None

        name, code = extr_vendor_name(vendor_page, session)
        if not name or not code:
            return None

        # If we don't have product details from listing, try to extract from product page
        if not product_name or not product_image:
            extracted_name, extracted_image, extracted_price = extract_product_details(url, session)
            if not product_name:
                product_name = extracted_name
            if not product_image:
                product_image = extracted_image
            if not product_price and extracted_price:
                product_price = extracted_price

        with lock:
            links_dict[url] = name
            if name in companies_dict:
                company_data = companies_dict[name]
                # Handle both old format (tuple) and new format (dict)
                if isinstance(company_data, dict):
                    is_valid = company_data.get('is_valid', False)
                    score = company_data.get('score', 0)
                    company_address = company_data.get('address')
                else:
                    # Old format: (is_valid, score) or (is_valid, score, address)
                    is_valid = company_data[0] if len(company_data) > 0 else False
                    score = company_data[1] if len(company_data) > 1 else 0
                    company_address = company_data[2] if len(company_data) > 2 else None
                return url, name, (is_valid, score), product_name, product_image, product_price, company_address

        lista_firme_url = create_company_site_url(name, code)
        financials = get_latest_financials(lista_firme_url, session)
        
        # Extract company address for distance calculation
        company_address = extract_company_address(lista_firme_url, session)

        if financials is None:
            with lock:
                companies_dict[name] = {'is_valid': False, 'score': 0, 'address': company_address}
            return url, name, (False, 0), product_name, product_image, product_price, company_address

        cifra_afaceri, active, nr_salariati, profit, datorii, age = financials

        if check_small_business(cifra_afaceri, active, nr_salariati):
            credibility = compute_credibility(profit, datorii, age)
            with lock:
                companies_dict[name] = {'is_valid': True, 'score': credibility, 'address': company_address}
            return url, name, (True, credibility), product_name, product_image, product_price, company_address
        else:
            with lock:
                companies_dict[name] = {'is_valid': False, 'score': 0, 'address': company_address}
            return url, name, (False, 0), product_name, product_image, product_price, company_address

    except Exception as e:
        return None
    finally:
        session.close()


@app.route('/api/search', methods=['POST'])
def search_products():
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        if not prompt:
            return jsonify({'error': 'Prompt is required'}), 400

        print(f"Processing prompt: {prompt}")
        
        # Generate eMAG URL
        search_url = generate_emag_url(prompt)
        print(f"Generated URL: {search_url}")
        
        # Get product list with basic info (name, image, price) from listing page
        raw_products = get_product_list(search_url, max_pages=2)
        
        # Remove duplicates based on URL
        seen_urls = set()
        unique_products = []
        for product in raw_products:
            url = product.get('url')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_products.append(product)
        
        total_found = len(unique_products)
        print(f"Found {total_found} unique products")
        
        links_map = {}
        companies_cache = {}
        lock = Lock()
        valid_products = []
        
        with ThreadPoolExecutor(max_workers=10) as executor:  # Increased workers since we're not visiting product pages for most items
            future_to_product = {
                executor.submit(process_url, product_info, companies_cache, links_map, lock): product_info
                for product_info in unique_products
            }
            
            for future in as_completed(future_to_product):
                result = future.result()
                if result:
                    # Handle both old format (6 items) and new format (7 items with address)
                    if len(result) == 7:
                        url, company_name, (is_valid, score), product_name, product_image, product_price, company_address = result
                    else:
                        url, company_name, (is_valid, score), product_name, product_image, product_price = result
                        company_address = None
                    
                    if is_valid:
                        valid_products.append({
                            'url': url,
                            'productName': product_name or 'Unknown Product',
                            'companyName': company_name,
                            'credibilityScore': score,
                            'imageUrl': product_image or '',
                            'price': product_price if product_price is not None and isinstance(product_price, (int, float)) else None,
                            'companyAddress': company_address
                        })
        
        # Sort by credibility score
        valid_products.sort(key=lambda x: x['credibilityScore'], reverse=True)
        
        # Calculate distances if user location is provided
        user_lat = data.get('userLatitude')
        user_lon = data.get('userLongitude')
        
        if user_lat and user_lon:
            for product in valid_products:
                address = product.get('companyAddress')
                if address:
                    company_lat, company_lon = geocode_address(address)
                    if company_lat and company_lon:
                        distance = calculate_distance(user_lat, user_lon, company_lat, company_lon)
                        product['distanceKm'] = distance
        
        # Save to search history
        add_to_search_history(prompt, len(valid_products))
        
        return jsonify({
            'success': True,
            'products': valid_products,
            'count': len(valid_products)
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

@app.route('/api/search-history', methods=['GET'])
def get_search_history():
    """Get all search history"""
    history = load_search_history()
    return jsonify({'success': True, 'history': history})

@app.route('/api/search-history', methods=['POST'])
def update_search_history():
    """Update which searches should be shown"""
    try:
        data = request.get_json()
        selected_ids = data.get('selectedIds', [])
        
        history = load_search_history()
        # Mark searches as selected/not selected
        for item in history:
            item['selected'] = item['id'] in selected_ids
        
        save_search_history(history)
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search-history/products', methods=['POST'])
def get_products_for_searches():
    """Get products for selected search prompts"""
    try:
        data = request.get_json()
        prompts = data.get('prompts', [])
        
        if not prompts:
            return jsonify({'success': True, 'products': []})
        
        all_products = []
        
        # Process each prompt
        for prompt in prompts:
            try:
                # Generate eMAG URL
                search_url = generate_emag_url(prompt)
                if not search_url:
                    continue
                
                # Get product list with basic info
                raw_products = get_product_list(search_url, max_pages=1)  # Limit to 1 page for speed
                
                # Remove duplicates
                seen_urls = set()
                unique_products = []
                for product in raw_products:
                    url = product.get('url')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        unique_products.append(product)
                
                # Process products to validate vendors
                links_map = {}
                companies_cache = {}
                lock = Lock()
                
                with ThreadPoolExecutor(max_workers=5) as executor:
                    future_to_product = {
                        executor.submit(process_url, product_info, companies_cache, links_map, lock): product_info
                        for product_info in unique_products[:20]  # Limit to 20 products per search for performance
                    }
                    
                    for future in as_completed(future_to_product):
                        result = future.result()
                        if result:
                            url, company_name, (is_valid, score), product_name, product_image, product_price = result
                            if is_valid:
                                all_products.append({
                                    'url': url,
                                    'productName': product_name or 'Unknown Product',
                                    'companyName': company_name,
                                    'credibilityScore': score,
                                    'imageUrl': product_image or '',
                                    'price': product_price if product_price is not None and isinstance(product_price, (int, float)) else None,
                                    'searchPrompt': prompt
                                })
            except Exception as e:
                print(f"Error processing prompt '{prompt}': {e}")
                continue
        
        # Sort by credibility score
        all_products.sort(key=lambda x: x['credibilityScore'], reverse=True)
        
        return jsonify({
            'success': True,
            'products': all_products,
            'count': len(all_products)
        })
        
    except Exception as e:
        print(f"Error getting products for searches: {e}")
        return jsonify({'error': str(e)}), 500

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


if __name__ == '__main__':
    app.run(debug=True, port=5000, host="0.0.0.0")

