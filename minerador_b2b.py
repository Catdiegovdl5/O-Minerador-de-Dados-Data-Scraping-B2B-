import asyncio
import random
import pandas as pd
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import httpx
from bs4 import BeautifulSoup
import re
import sys
import sqlite3
import time
import hashlib
from fpdf import FPDF
import os
import json
from google import genai

# ==============================================================================
# ⚙️  CONFIGURAÇÃO — coloca a tua chave aqui ou define a variável de ambiente
#    Obtém gratuitamente em: https://aistudio.google.com/app/apikey
# ==============================================================================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "SUA_CHAVE_AQUI")
GEMINI_MODEL   = "gemini-2.0-flash"

# Inicializa o cliente Gemini (só uma vez)
_gemini_client = None
def get_gemini_client():
    global _gemini_client
    if _gemini_client is None and GEMINI_API_KEY != "SUA_CHAVE_AQUI":
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    return _gemini_client

# ==============================================================================
# 🗄️  DB
# ==============================================================================
def init_db():
    conn = sqlite3.connect('leads.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS leads
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT,
                  phone TEXT,
                  website TEXT,
                  rating REAL,
                  tem_pixel_meta TEXT,
                  status TEXT,
                  is_buyer TEXT,
                  ai_score INTEGER,
                  ai_maturidade TEXT,
                  ai_killer_pitch TEXT,
                  UNIQUE(name, phone))''')
    conn.commit()
    conn.close()

init_db()

# ==============================================================================
# 🤖  ANÁLISE COM IA — Gemini "Consultor de Vendas"
# ==============================================================================
async def analisar_lead_com_ia(nome: str, texto_site: str, pixel_meta: str,
                                google_ads: str, rating: str) -> dict:
    """
    Envia dados do lead ao Gemini e recebe uma análise estruturada de vendas.
    Retorna dict com: AI_Score, AI_Maturidade, AI_Killer_Pitch
    """
    client = get_gemini_client()
    if client is None:
        return {"AI_Score": "N/A", "AI_Maturidade": "N/A", "AI_Killer_Pitch": "Configure GEMINI_API_KEY"}

    # Limitar texto para não gastar tokens desnecessariamente
    texto_resumido = texto_site[:1500] if texto_site else "Site sem conteúdo acessível."

    prompt = f"""Você é um Growth Engineer especialista em tráfego pago e marketing digital B2B.
Analise os dados desta empresa e responda APENAS em JSON válido, sem markdown.

DADOS DA EMPRESA:
- Nome: {nome}
- Avaliação Google: {rating} estrelas
- Meta Pixel instalado: {pixel_meta}
- Google Ads/Tag Manager: {google_ads}
- Texto do site (amostra): {texto_resumido}

RESPONDA NESTE FORMATO EXATO (JSON puro, sem ```):
{{
  "score": <número inteiro de 0 a 100 representando a oportunidade de venda>,
  "maturidade": "<uma das opções: Iniciante | Escalando | Elite>",
  "killer_pitch": "<pitch de vendas direto e personalizado em 2 frases, em português, focado no problema específico desta empresa e como a implementação de GTM/CAPI/Pixel resolve. Mencione o nome da empresa.>"
}}

CRITÉRIOS DE SCORE:
- Score alto (70-100): Empresa com bom rating, SEM pixel, SEM Google Ads → oportunidade máxima
- Score médio (40-69): Tem pixel mas não tem Google Ads, ou rating baixo
- Score baixo (0-39): Já tem tudo instalado ou não tem website"""

    try:
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt
            )
        )
        raw = response.text.strip()
        # Limpar markdown caso o modelo insista
        raw = re.sub(r'```json|```', '', raw).strip()
        data = json.loads(raw)
        return {
            "AI_Score":        int(data.get("score", 0)),
            "AI_Maturidade":   data.get("maturidade", "N/A"),
            "AI_Killer_Pitch": data.get("killer_pitch", "N/A")
        }
    except Exception as e:
        print(f"  [IA] Erro ao analisar '{nome}': {e}")
        return {"AI_Score": 0, "AI_Maturidade": "Erro", "AI_Killer_Pitch": str(e)[:100]}

# ==============================================================================
# 🌐  ENRIQUECIMENTO DE WEBSITE
# ==============================================================================
async def scrape_website(url):
    if not url or url == "N/A":
        return {
            "Email": "N/A", "Instagram": "N/A", "LinkedIn": "N/A",
            "Tem_Pixel_Meta": "Não", "Tem_Google_Ads": "Não",
            "_texto_site": ""
        }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            response = await client.get(url)
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)

            tem_meta   = "Sim" if any(x in html_content for x in ['fbevents.js', 'connect.facebook.net']) else "Não"
            tem_google = "Sim" if any(x in html_content for x in ['googletagmanager.com', 'gtag']) else "Não"

            email_match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
            email = email_match.group(0) if email_match else "N/A"

            instagram = "N/A"
            linkedin  = "N/A"
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'instagram.com' in href:  instagram = href
                elif 'linkedin.com' in href: linkedin  = href

            return {
                "Email": email, "Instagram": instagram, "LinkedIn": linkedin,
                "Tem_Pixel_Meta": tem_meta, "Tem_Google_Ads": tem_google,
                "_texto_site": text[:2000]  # Guardamos para a IA
            }
    except Exception:
        return {
            "Email": "N/A", "Instagram": "N/A", "LinkedIn": "N/A",
            "Tem_Pixel_Meta": "Não", "Tem_Google_Ads": "Não",
            "_texto_site": ""
        }

# ==============================================================================
# ⚡  CONCORRÊNCIA
# ==============================================================================
SEMAPHORE = asyncio.Semaphore(10)

async def process_query(p, browser, query, proxy, is_buyer=False):
    async with SEMAPHORE:
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0"
        ]

        context = await browser.new_context(user_agent=random.choice(user_agents))
        page    = await context.new_page()
        stealth_obj = Stealth()
        await stealth_obj.apply_stealth_async(page)

        print(f"  🔍 Buscando: {query}...")
        try:
            for attempt in range(3):
                try:
                    await page.goto(f"https://www.google.com/maps/search/{query}", timeout=60000)
                    if await page.query_selector('text="Are you a robot?"') or \
                       await page.query_selector('iframe[src*="recaptcha"]'):
                        print("  ⚠️  CAPTCHA detectado! Modo Evasão ativado...")
                        await asyncio.sleep(random.uniform(10, 20))
                        return []
                    await page.wait_for_selector('div[role="feed"]', timeout=30000)
                    break
                except Exception as e:
                    if attempt == 2: raise e
                    print(f"  Retry {attempt+1} para {query}...")
                    await asyncio.sleep(random.uniform(2, 5))

            # Scroll para carregar mais resultados
            for _ in range(3):
                await page.mouse.wheel(0, 5000)
                await asyncio.sleep(random.uniform(2, 4))

            results  = []
            listings = await page.query_selector_all('div[role="article"]')

            for listing in listings:
                try:
                    data     = {}
                    name_el  = await listing.query_selector('div.fontHeadlineSmall')
                    if not name_el: continue
                    data['Name'] = await name_el.inner_text()

                    rating_el = await listing.query_selector('span[aria-label*="estrelas"]')
                    if rating_el:
                        aria_label   = await rating_el.get_attribute('aria-label')
                        data['Rating'] = aria_label.split()[0]
                    else:
                        data['Rating'] = "0.0"

                    data['Sponsored'] = "Sim" if await listing.query_selector('span:has-text("Patrocinado")') else "Não"

                    website_el   = await listing.query_selector('a[aria-label*="website"], a[data-value="Website"]')
                    data['Website'] = await website_el.get_attribute('href') if website_el else "N/A"

                    text_content = await listing.inner_text()
                    phone_match  = re.search(r'(\(?\d{2}\)?\s?\d{4,5}-?\d{4})', text_content)
                    data['Phone'] = phone_match.group(0) if phone_match else "N/A"

                    results.append(data)
                    if len(results) >= 50: break
                except Exception as e:
                    print(f"  Listing ignorado: {e}")
                    continue

            # ── Enriquecimento concorrente ──────────────────────────────────
            async def enrich_item(item):
                enrichment = await scrape_website(item['Website'])
                item.update(enrichment)

                # ── Análise com IA ──────────────────────────────────────────
                print(f"  🤖 IA analisando: {item['Name']}...")
                ai_result = await analisar_lead_com_ia(
                    nome       = item['Name'],
                    texto_site = item.get('_texto_site', ''),
                    pixel_meta = item.get('Tem_Pixel_Meta', 'Não'),
                    google_ads = item.get('Tem_Google_Ads', 'Não'),
                    rating     = item.get('Rating', '0.0')
                )
                item.update(ai_result)
                return item

            results = await asyncio.gather(*[enrich_item(item) for item in results])

            # ── Classificação ───────────────────────────────────────────────
            for item in results:
                item['Is_Buyer'] = "Sim" if is_buyer else "Não"
                if is_buyer:
                    item['Status'] = 'Comprador Potencial (Agência)'
                elif item['Website'] != "N/A" and item['Tem_Pixel_Meta'] == "Não":
                    item['Status'] = 'Oportunidade de Implementação'
                elif item['Tem_Pixel_Meta'] == "Sim":
                    item['Status'] = 'Lead de Alta Performance'
                else:
                    item['Status'] = 'Lead Frio'

            await context.close()
            return results
        except Exception as e:
            print(f"  Erro em {query}: {e}")
            await context.close()
            return []

# ==============================================================================
# 📄  GERADOR DE PDF — Sales Kit
# ==============================================================================
def generate_pdf_report(df, filename, city):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", 'B', 16)
    pdf.cell(0, 10, text=f"Relatório de Oportunidades Digitais: {city} {time.strftime('%Y')}", align='C', new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    pdf.ln(10)

    total         = len(df)
    no_pixel      = len(df[df['Tem_Pixel_Meta'] == "Não"])
    pct_no_pixel  = (no_pixel / total * 100) if total > 0 else 0

    ai_enabled    = df['AI_Score'].apply(lambda x: isinstance(x, int)).any()
    top_score     = int(df['AI_Score'].max()) if ai_enabled else "N/A"
    avg_score     = round(df['AI_Score'].mean(), 1) if ai_enabled else "N/A"

    pdf.cell(0, 10, text=f"Total de Leads Auditados: {total}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, text=f"Empresas SEM Meta Pixel: {no_pixel} ({pct_no_pixel:.1f}%)", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 10, text=f"Score IA Médio: {avg_score} | Score Máximo: {top_score}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(8)

    pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(0, 10, text="Análise Estratégica:", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text=(
        f"{pct_no_pixel:.1f}% das empresas em {city} estão investindo em tráfego "
        f"SEM o Meta Pixel instalado — perdendo dados e dinheiro. "
        f"Esta auditoria identifica quem está pronto para comprar uma solução de GTM/CAPI."
    ))

    # Top 5 Leads por IA Score
    if ai_enabled and not df.empty:
        pdf.ln(8)
        pdf.set_font("Helvetica", 'B', 13)
        pdf.cell(0, 10, text="Top 5 Oportunidades (Score IA):", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", size=11)
        top5 = df[df['AI_Score'].apply(lambda x: isinstance(x, int))].nlargest(5, 'AI_Score')
        for _, row in top5.iterrows():
            pdf.set_font("Helvetica", 'B', 11)
            pdf.cell(0, 8, text=f"• {row['Name']} — Score: {row['AI_Score']} | {row['AI_Maturidade']}", new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("Helvetica", 'I', 10)
            pitch = str(row.get('AI_Killer_Pitch', ''))[:200]
            pdf.multi_cell(0, 7, text=f"  Pitch: {pitch}")
            pdf.ln(2)

    pdf.output(filename)

# ==============================================================================
# 🚀  MAIN — Entrada Dinâmica (sem hardcode)
# ==============================================================================
async def main():
    proxy = None

    print("=" * 60)
    print("  💎 MINERADOR B2B V2 — Powered by Gemini AI")
    print("=" * 60)

    # ── Configuração de alvos ────────────────────────────────────────────────
    if len(sys.argv) > 2:
        # Modo CLI: python minerador_b2b.py "Clínicas de Estética" "São Paulo"
        niche  = sys.argv[1]
        city   = sys.argv[2]
        niche_queries  = [f"{niche} {city}"]
        buyer_queries  = [f"Agência de Marketing {city}"]
        print(f"\n  🎯 Alvo: {niche} em {city}")
    else:
        # Modo interativo
        print("\n  Para uso direto via CLI: python minerador_b2b.py \"Nicho\" \"Cidade\"")
        city  = input("\n  🏙️  Qual cidade deseja minerar? (ex: São Paulo): ").strip() or "Londrina"
        niche = input("  🎯  Qual nicho? (ex: Clínicas de Estética): ").strip() or "Clínicas de Estética"

        extra = input("  ➕  Adicionar mais nichos? (vírgula, ou Enter para pular): ").strip()
        nichos = [niche] + [n.strip() for n in extra.split(',') if n.strip()] if extra else [niche]
        niche_queries = [f"{n} {city}" for n in nichos]
        buyer_queries = [f"Agência de Marketing {city}", f"Gestor de Tráfego {city}"]
        print(f"\n  🔥 Iniciando mineração: {len(niche_queries)} nicho(s) em {city}")

    # ── Verificação da API Key ───────────────────────────────────────────────
    if GEMINI_API_KEY == "SUA_CHAVE_AQUI":
        print("\n  ⚠️  ATENÇÃO: GEMINI_API_KEY não configurada.")
        print("     A IA será desativada. Score e Pitch não serão gerados.")
        print("     Configure: $env:GEMINI_API_KEY = 'sua_chave'")
        print("     Chave gratuita em: https://aistudio.google.com/app/apikey\n")
    else:
        print(f"\n  ✅ Gemini AI ativo (modelo: {GEMINI_MODEL})\n")

    # ── Execução ─────────────────────────────────────────────────────────────
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, proxy=proxy)

        all_tasks = (
            [process_query(p, browser, q, proxy, is_buyer=False) for q in niche_queries] +
            [process_query(p, browser, q, proxy, is_buyer=True)  for q in buyer_queries]
        )

        print(f"  ⚡ Turbo Mode: {len(all_tasks)} queries simultâneas...\n")
        all_results_lists = await asyncio.gather(*all_tasks)

        all_results = [item for sublist in all_results_lists for item in sublist]
        print(f"\n  ✅ Mineração concluída. Total de leads: {len(all_results)}")

        await browser.close()

    if not all_results:
        print("  ❌ Nenhum resultado encontrado.")
        return

    # ── Pós-processamento ────────────────────────────────────────────────────
    df = pd.DataFrame(all_results)

    # Remove coluna interna de texto (não vai para o Excel)
    df.drop(columns=['_texto_site'], errors='ignore', inplace=True)

    # Persistência no SQLite
    conn = sqlite3.connect('leads.db')
    new_leads = 0
    for _, row in df.iterrows():
        try:
            conn.execute(
                """INSERT INTO leads (name, phone, website, rating, tem_pixel_meta,
                   status, is_buyer, ai_score, ai_maturidade, ai_killer_pitch)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (row.get('Name'), row.get('Phone'), row.get('Website'),
                 row.get('Rating'), row.get('Tem_Pixel_Meta'), row.get('Status'),
                 row.get('Is_Buyer'), row.get('AI_Score'), row.get('AI_Maturidade'),
                 row.get('AI_Killer_Pitch'))
            )
            new_leads += 1
        except sqlite3.IntegrityError:
            continue
    conn.commit()
    conn.close()
    print(f"  💾 {new_leads} leads novos persistidos no SQLite.")

    # Limpeza e formatação
    df.drop_duplicates(subset=['Name', 'Phone'], inplace=True)

    def clean_rating(r):
        try:   return float(str(r).replace(',', '.').replace(' stars', '').strip())
        except: return 0.0

    def format_phone(p):
        if p == "N/A": return "N/A"
        digits = re.sub(r'\D', '', p)
        if len(digits) >= 10:
            if not digits.startswith('55'): digits = '55' + digits
            return '+' + digits
        return p

    df['Rating'] = df['Rating'].apply(clean_rating)
    df['Phone']  = df['Phone'].apply(format_phone)

    # Ordenar por AI_Score (descrescente)
    if 'AI_Score' in df.columns:
        df['AI_Score'] = pd.to_numeric(df['AI_Score'], errors='coerce').fillna(0).astype(int)
        df.sort_values('AI_Score', ascending=False, inplace=True)

    # ── Export Excel ─────────────────────────────────────────────────────────
    filename = f"Mineracao_B2B_{city.replace(' ','_')}_V2.xlsx"
    hot_leads   = df[(df['Rating'] < 4.0) | (df['Status'] == 'Oportunidade de Implementação')]
    buyers_df   = df[df['Is_Buyer'] == "Sim"]
    leads_df    = df[df['Is_Buyer'] == "Não"]
    competitors = df.sort_values('Rating', ascending=False).head(5)
    top_ia      = df.nlargest(10, 'AI_Score') if 'AI_Score' in df.columns else pd.DataFrame()

    with pd.ExcelWriter(filename) as writer:
        if not top_ia.empty:
            top_ia.to_excel(writer, sheet_name='🏆 Top IA Score', index=False)
        hot_leads.to_excel(writer, sheet_name='Hot Leads', index=False)
        leads_df.to_excel(writer, sheet_name='Lista Completa', index=False)
        buyers_df.to_excel(writer, sheet_name='COMPRADORES', index=False)
        competitors.to_excel(writer, sheet_name='Concorrência', index=False)

    print(f"  📊 Excel gerado: {filename}")

    # ── Export Meta CAPI (CSV hashed) ────────────────────────────────────────
    def hash_data(d):
        if not d or d == "N/A" or pd.isna(d): return ""
        return hashlib.sha256(str(d).strip().lower().encode()).hexdigest()

    capi_df = leads_df.copy()
    capi_df['client_event_time'] = int(time.time())
    capi_df['event_name']        = 'Lead'
    capi_df['currency']          = 'BRL'
    capi_df['em'] = capi_df['Email'].apply(hash_data)
    capi_df['ph'] = capi_df['Phone'].apply(hash_data)
    capi_df['client_user_agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0"
    capi_export = capi_df.rename(columns={'Name': 'external_id'})
    capi_cols   = ['em', 'ph', 'external_id', 'client_event_time', 'event_name', 'currency', 'client_user_agent']
    capi_filename = f"Meta_CAPI_{city.replace(' ','_')}.csv"
    capi_export[capi_cols].to_csv(capi_filename, index=False)
    print(f"  📤 Meta CAPI Export: {capi_filename}")

    # ── PDF Sales Kit ─────────────────────────────────────────────────────────
    pdf_filename = f"Relatorio_Oportunidades_{city.replace(' ','_')}_V2.pdf"
    generate_pdf_report(df, pdf_filename, city)
    print(f"  📄 PDF Sales Kit: {pdf_filename}")

    print(f"\n  🏆 CONCLUÍDO! Ficheiros gerados em: {os.getcwd()}")

if __name__ == "__main__":
    asyncio.run(main())
