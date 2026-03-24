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
        return {
            "Email": "N/A", "Instagram": "N/A", "LinkedIn": "N/A",
            "Tem_Pixel_Meta": "Não", "Tem_Google_Ads": "Não"
        }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text()

            # Tracking Pixels Audit
            tem_meta = "Sim" if any(x in html_content for x in ['fbevents.js', 'connect.facebook.net']) else "Não"
            tem_google = "Sim" if any(x in html_content for x in ['googletagmanager.com', 'gtag']) else "Não"

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

            return {
                "Email": email, "Instagram": instagram, "LinkedIn": linkedin,
                "Tem_Pixel_Meta": tem_meta, "Tem_Google_Ads": tem_google
            }
    except Exception:
        return {
            "Email": "N/A", "Instagram": "N/A", "LinkedIn": "N/A",
            "Tem_Pixel_Meta": "Não", "Tem_Google_Ads": "Não"
        }

# Global concurrency limit (Semaphore)
# For 16GB RAM, 10 simultaneous browsers/tabs is a safe "Turbo" limit
SEMAPHORE = asyncio.Semaphore(10)

async def process_query(p, browser, query, proxy):
    async with SEMAPHORE:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ]

        context = await browser.new_context(user_agent=random.choice(user_agents))
        page = await context.new_page()
        stealth_obj = Stealth()
        await stealth_obj.apply_stealth_async(page)

        print(f"Searching for: {query}...")
        try:
            await page.goto(f"https://www.google.com/maps/search/{query}", timeout=60000)
            await page.wait_for_selector('div[role="feed"]', timeout=30000)

            # Infinite scroll
            for _ in range(3):
                await page.mouse.wheel(0, 5000)
                await asyncio.sleep(random.uniform(2, 4))

            # Extraction logic
            results = []
            listings = await page.query_selector_all('div[role="article"]')

            for listing in listings:
                data = {}
                name_el = await listing.query_selector('div.fontHeadlineSmall')
                data['Name'] = await name_el.inner_text() if name_el else "N/A"
                rating_el = await listing.query_selector('span.MW4etd')
                data['Rating'] = await rating_el.inner_text() if rating_el else "0.0"
                data['Sponsored'] = "Sim" if await listing.query_selector('span:has-text("Patrocinado")') else "Não"
                website_el = await listing.query_selector('a[data-value="Website"]')
                data['Website'] = await website_el.get_attribute('href') if website_el else "N/A"
                text_content = await listing.inner_text()
                phone_match = re.search(r'(\(?\d{2}\)?\s?\d{4,5}-?\d{4})', text_content)
                data['Phone'] = phone_match.group(0) if phone_match else "N/A"
                results.append(data)
                if len(results) >= 10: break

            # Concurrent Enrichment
            async def enrich_item(item):
                enrichment = await scrape_website(item['Website'])
                item.update(enrichment)
                return item

            results = await asyncio.gather(*[enrich_item(item) for item in results])

            # Classification
            for item in results:
                if item['Website'] != "N/A" and item['Tem_Pixel_Meta'] == "Não":
                    item['Status'] = 'Oportunidade de Implementação'
                elif item['Tem_Pixel_Meta'] == "Sim":
                    item['Status'] = 'Lead de Alta Performance'
                else:
                    item['Status'] = 'Lead Frio'

            await context.close()
            return results
        except Exception as e:
            print(f"Error processing {query}: {e}")
            await context.close()
            return []

async def main():
    # Proxy Setup (Placeholder)
    # proxy = {"server": "http://your-proxy-address:port", "username": "user", "password": "pass"}
    proxy = None

    cities = ["Assaí", "Londrina"] # Expand this list as needed
    search_queries = [f"Imobiliárias em {city}" for city in cities]

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=proxy)

        print(f"Starting 'Turbo' mining for {len(search_queries)} queries...")
        all_results_lists = await asyncio.gather(*[process_query(p, browser, q, proxy) for q in search_queries])

        # Consolidate Results
        all_results = [item for sublist in all_results_lists for item in sublist]

        print(f"Finished mining. Total leads: {len(all_results)}")

        # Sanitization and Export
        if all_results:
            df = pd.DataFrame(all_results)
            df.drop_duplicates(subset=['Name', 'Phone'], inplace=True)

            def clean_rating(rating):
                try:
                    rating = rating.replace(',', '.').replace(' stars', '').strip()
                    return float(rating)
                except: return 0.0

            df['Rating'] = df['Rating'].apply(clean_rating)

            def format_phone(phone):
                if phone == "N/A": return "N/A"
                digits = re.sub(r'\D', '', phone)
                if len(digits) >= 10:
                    if not digits.startswith('55'): digits = '55' + digits
                    return '+' + digits
                return phone

            df['Phone'] = df['Phone'].apply(format_phone)

            filename = "Mineracao_B2B_TURBO.xlsx"
            hot_leads = df[(df['Rating'] < 4.0) | (df['Status'] == 'Oportunidade de Implementação')]
            competitors = df.sort_values(by='Rating', ascending=False).head(5)

            with pd.ExcelWriter(filename) as writer:
                hot_leads.to_excel(writer, sheet_name='Hot Leads', index=False)
                df.to_excel(writer, sheet_name='Lista Completa', index=False)
                competitors.to_excel(writer, sheet_name='Análise de Concorrência', index=False)

            print(f"Master file {filename} created successfully.")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
