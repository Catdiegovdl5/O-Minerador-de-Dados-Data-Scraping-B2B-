import asyncio
import random
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import httpx
from bs4 import BeautifulSoup
import re

async def scrape_website(url):
    if not url or url == "N/A":
        return {"Email": "N/A", "Instagram": "N/A", "LinkedIn": "N/A"}
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')
            text = soup.get_text()

            # Find Email
            email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
            email = email_match.group(0) if email_match else "N/A"

            # Find Social links
            instagram = "N/A"
            linkedin = "N/A"
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'instagram.com' in href:
                    instagram = href
                elif 'linkedin.com' in href:
                    linkedin = href

            return {"Email": email, "Instagram": instagram, "LinkedIn": linkedin}
    except Exception:
        return {"Email": "N/A", "Instagram": "N/A", "LinkedIn": "N/A"}

async def main():
    # User-Agent Switcher
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
    ]

    # Proxy Setup (Placeholder as requested)
    # proxy = {"server": "http://your-proxy-address:port", "username": "user", "password": "pass"}
    proxy = None # Set to your proxy dict if available

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=proxy)
        context = await browser.new_context(
            user_agent=random.choice(user_agents)
        )
        page = await context.new_page()
        # Initializing Stealth instance
        stealth_obj = Stealth()
        await stealth_obj.apply_stealth_async(page)

        print("Browser initialized with Stealth.")

        search_query = "Imobiliárias em Assaí"
        await page.goto(f"https://www.google.com/maps/search/{search_query}")
        await page.wait_for_selector('div[role="feed"]')

        # Infinite scroll
        print("Scrolling results...")
        for _ in range(3): # Small range for testing
            await page.mouse.wheel(0, 5000)
            await asyncio.sleep(random.uniform(2, 4))

        # Extraction logic
        print("Extracting basic fields...")
        results = []
        listings = await page.query_selector_all('div[role="article"]')

        for listing in listings:
            data = {}
            # Name
            name_el = await listing.query_selector('div.fontHeadlineSmall')
            data['Name'] = await name_el.inner_text() if name_el else "N/A"

            # Rating
            rating_el = await listing.query_selector('span.MW4etd')
            data['Rating'] = await rating_el.inner_text() if rating_el else "0.0"

            # Sponsored
            data['Sponsored'] = "Sim" if await listing.query_selector('span:has-text("Patrocinado")') else "Não"

            # Phone and Website require clicking or extra logic
            # For simplicity in this base version, we'll try to get them from the visible text/links
            # or by clicking if needed. Google Maps often has website links in the listing.
            website_el = await listing.query_selector('a[data-value="Website"]')
            data['Website'] = await website_el.get_attribute('href') if website_el else "N/A"

            # Phone - often in the secondary text
            text_content = await listing.inner_text()
            phone_match = re.search(r'(\(?\d{2}\)?\s?\d{4,5}-?\d{4})', text_content)
            data['Phone'] = phone_match.group(0) if phone_match else "N/A"

            results.append(data)
            if len(results) >= 10: break

        # Concurrent Website Enrichment
        print(f"Extracted {len(results)} results. Starting concurrent enrichment...")

        async def enrich_item(item):
            print(f"Enriching data for {item['Name']}...")
            enrichment = await scrape_website(item['Website'])
            item.update(enrichment)
            return item

        results = await asyncio.gather(*[enrich_item(item) for item in results])
        print(f"Enriched all {len(results)} results.")

        # Sanitization
        print("Sanitizing data...")
        df = pd.DataFrame(results)
        df.drop_duplicates(subset=['Name', 'Phone'], inplace=True)

        def clean_rating(rating):
            try:
                # Handle Portuguese commas and non-numeric chars
                rating = rating.replace(',', '.').replace(' stars', '').strip()
                return float(rating)
            except (ValueError, AttributeError):
                return 0.0

        df['Rating'] = df['Rating'].apply(clean_rating)

        def format_phone(phone):
            if phone == "N/A": return "N/A"
            digits = re.sub(r'\D', '', phone)
            if len(digits) >= 10:
                if not digits.startswith('55'):
                    digits = '55' + digits
                return '+' + digits
            return phone

        df['Phone'] = df['Phone'].apply(format_phone)

        # Export to Excel
        print("Exporting to Excel...")
        filename = "Mineracao_B2B_Assai.xlsx"

        # Hot Leads: Rating low or N/A website?
        # For this demo, let's say rating < 4.0 or no website
        hot_leads = df[(df['Rating'] < 4.0) | (df['Website'] == "N/A")]

        # Analysis: Top 3 (Rating)
        competitors = df.sort_values(by='Rating', ascending=False).head(3)

        with pd.ExcelWriter(filename) as writer:
            hot_leads.to_excel(writer, sheet_name='Hot Leads', index=False)
            df.to_excel(writer, sheet_name='Lista Completa', index=False)
            competitors.to_excel(writer, sheet_name='Análise de Concorrência', index=False)

        print(f"File {filename} created successfully.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
