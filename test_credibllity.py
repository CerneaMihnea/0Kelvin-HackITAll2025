import requests
from bs4 import BeautifulSoup

def has_https(url: str):
    return url.startswith("https://")

def page_exists(base_url, path):
    try:
        r = requests.get(base_url + path, timeout=5)
        return r.status_code == 200
    except:
        return False

def find_company_info(text):
    keywords = ["CUI", "CIF", "SRL", "S.R.L", "company", "registered", "registration"]
    return any(k.lower() in text.lower() for k in keywords)

def credibility_retailer(url):
    score = 0

    # HTTPS
    if has_https(url):
        score += 10

    # Fetch main page
    try:
        r = requests.get(url, timeout=5)
        soup = BeautifulSoup(r.text, "html.parser")
        text = soup.get_text()
    except:
        return 0

    # Pagini obligatorii
    important_pages = ["/contact", "/about", "/privacy", "/terms", "/return", "/refund"]
    valid_pages = sum(page_exists(url, p) for p in important_pages)
    score += valid_pages * 3  # max 18 puncte

    # Date firmă
    if find_company_info(text):
        score += 20

    # Reclame (dacă sunt prea multe, scazi puncte)
    ads = len(soup.find_all("iframe")) + len(soup.find_all("script"))
    if ads < 20:
        score += 10
    else:
        score -= 5

    # Reduceri suspecte
    suspicious_words = ["70% off", "80% off", "last day", "super reducere", "liquidation"]
    if any(word in text.lower() for word in suspicious_words):
        score -= 15

    return max(score, 0)

# Test
data = ["https://www.zara.com/ro/", "https://www.hm.com", "https://www.bershka.com", "https://www.stradivarius.com", "https://www.pullandbear.com"]

for i in range(len(data)):
    print(f"Credibility score for {data[i]} is {credibility_retailer(data[i])}")