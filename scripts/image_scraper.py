
import os
import asyncio
import aiohttp
import requests
import urllib.parse
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import logging

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    from selenium.webdriver.chrome.service import Service
except ImportError:
    webdriver = None

# valid extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.bmp', '.webp', '.png', '.mp4', '.gif'}

def setup_logger(log_path):
    logger = logging.getLogger('ImageScraper')
    logger.setLevel(logging.INFO)
    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.FileHandler(log_path, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger

def get_valid_filename(url):
    """Generates a folder structure from URL."""
    parsed = urlparse(url)
    domain = parsed.hostname
    path_clean = parsed.path.strip('/').replace('/', '_')
    if not path_clean:
        path_clean = "root"
    return os.path.join(domain, path_clean)

async def download_single_image(session, img_url, output_dir, logger, min_size=10 * 1024):
    try:
        filename = os.path.basename(urlparse(img_url).path)
        if not filename or '.' not in filename:
            filename = f"image_{hash(img_url)}.jpg"
            
        filepath = os.path.join(output_dir, filename)
        
        # Avoid re-download (optional, but good for speed)
        if os.path.exists(filepath):
            return

        async with session.get(img_url, ssl=False, timeout=30) as response:
            if response.status == 200:
                content = await response.read()
                if len(content) >= min_size:
                    with open(filepath, 'wb') as f:
                        f.write(content)
                    if logger:
                        logger.info(f"Downloaded: {filename}")
                else:
                    if logger:
                        logger.info(f"Skipped (too small): {filename}")
            else:
                if logger:
                    logger.warning(f"Failed to download {img_url} status: {response.status}")
    except Exception as e:
        if logger:
            logger.error(f"Error downloading {img_url}: {e}")

async def scrape_static(url, output_base, logger):
    """Scrapes images using requests + BS4."""
    try:
        if logger:
            logger.info(f"Static Scrape starting for: {url}")
        
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            if logger:
                logger.error(f"Failed to load page: {response.status_code}")
            return {'count': 0, 'error': f'HTTP {response.status_code}'}

        soup = BeautifulSoup(response.content, 'html.parser')
        img_tags = soup.find_all('img')
        
        image_urls = []
        for img in img_tags:
            src = img.get('src')
            if src:
                full_url = urllib.parse.urljoin(url, src)
                ext = os.path.splitext(urlparse(full_url).path)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    image_urls.append(full_url)

        if not image_urls:
            if logger:
                logger.info("No images found (static).")
            return {'count': 0}

        # Setup output dir
        sub_path = get_valid_filename(url)
        output_dir = os.path.join(output_base, sub_path)
        os.makedirs(output_dir, exist_ok=True)

        # Download async
        async with aiohttp.ClientSession() as session:
            tasks = [download_single_image(session, u, output_dir, logger) for u in image_urls]
            await asyncio.gather(*tasks)

        return {'count': len(image_urls)}

    except Exception as e:
        if logger:
            logger.error(f"Static scrape exception: {e}")
        return {'count': 0, 'error': str(e)}


async def scrape_dynamic(url, output_base, logger):
    """Scrapes images using Selenium."""
    if not webdriver:
        return {'count': 0, 'error': 'Selenium not installed'}

    driver = None
    try:
        if logger:
            logger.info(f"Dynamic Scrape starting for: {url}")

        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)
        
        driver.get(url)
        
        # Scroll logic
        last_height = driver.execute_script("return document.body.scrollHeight")
        for _ in range(5):  # Scroll up to 5 times (configurable)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            await asyncio.sleep(2)  # Wait for load
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height

        # Parse with BS4 after render
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        img_tags = soup.find_all('img')

        image_urls = []
        for img in img_tags:
            src = soup_src = img.get('src')
            # Fallback for lazy loading attributes often found
            if not src:
                src = img.get('data-src') or img.get('data-original')
            
            if src:
                full_url = urllib.parse.urljoin(url, src)
                ext = os.path.splitext(urlparse(full_url).path)[1].lower()
                if ext in IMAGE_EXTENSIONS:
                    image_urls.append(full_url)
        
        if not image_urls:
            if logger:
                logger.info("No images found (dynamic).")
            return {'count': 0}

        # Setup output dir
        sub_path = get_valid_filename(url)
        output_dir = os.path.join(output_base, sub_path)
        os.makedirs(output_dir, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            tasks = [download_single_image(session, u, output_dir, logger) for u in image_urls]
            await asyncio.gather(*tasks)
            
        return {'count': len(image_urls)}

    except Exception as e:
        if logger:
            logger.error(f"Dynamic scrape exception: {e}")
        return {'count': 0, 'error': str(e)}
    finally:
        if driver:
            driver.quit()

async def scrape_images_task(urls, folder_path, use_dynamic=False, log_path=None):
    """Main entry point for scraping."""
    logger = setup_logger(log_path) if log_path else None
    
    download_base = os.path.join(folder_path, "downloaded_images")
    os.makedirs(download_base, exist_ok=True)
    
    results = {'total_processed': 0, 'errors': 0}
    
    for url in urls:
        url = url.strip()
        if not url:
            continue
            
        try:
            if use_dynamic:
                res = await scrape_dynamic(url, download_base, logger)
            else:
                res = await scrape_static(url, download_base, logger)
                
            if res.get('error'):
                results['errors'] += 1
            results['total_processed'] += 1
            
        except Exception as e:
            if logger:
                logger.error(f"Failed to process URL {url}: {e}")
            results['errors'] += 1
            
    return results
