import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import re
from urllib.parse import urlparse
import time
import random

class PriceTracker:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.setup_selenium()

    def setup_selenium(self):
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )

    def get_product_price(self, url):
        try:
            self.driver.get(url)
            time.sleep(random.uniform(2, 4))
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            title = self._find_title(soup)
            price = self._find_price(soup)
            image_url = self._find_image(soup)
            return title, self._clean_price(price), image_url
        except Exception as e:
            print(f"Error fetching product info: {str(e)}")
            return None, None, None

    def _find_title(self, soup):
        selectors = [
            {'name': 'span', 'attrs': {'id': 'productTitle'}},
            {'name': 'h1', 'attrs': {}},
            {'name': 'title', 'attrs': {}},
        ]
        for sel in selectors:
            elem = soup.find(sel['name'], sel['attrs'])
            if elem and elem.text.strip():
                return elem.text.strip()
        return None

    def _find_price(self, soup):
        # Add logic for price extraction
        price = None
        price_selectors = [
            {'name': 'span', 'attrs': {'id': 'priceblock_ourprice'}},
            {'name': 'span', 'attrs': {'id': 'priceblock_dealprice'}},
            {'name': 'span', 'attrs': {'class': 'a-price-whole'}},
        ]
        for sel in price_selectors:
            elem = soup.find(sel['name'], sel['attrs'])
            if elem and elem.text.strip():
                price = elem.text.strip()
                break
        return price

    def _find_image(self, soup):
        img = soup.find('img')
        if img and img.get('src'):
            return img['src']
        return None

    def _clean_price(self, price):
        if not price:
            return None
        price = re.sub(r'[^\d.]', '', price)
        try:
            return float(price)
        except Exception:
            return None

tracker = PriceTracker()

def get_product_price(url):
    return tracker.get_product_price(url)