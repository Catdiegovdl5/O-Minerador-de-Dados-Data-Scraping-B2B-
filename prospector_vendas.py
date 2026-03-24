import asyncio
import pandas as pd
from playwright.async_api import async_playwright
import os

async def generate_dossier(p, lead):
    """Takes a screenshot of the lead's website and generates a text dossier."""
    url = lead['Website']
    name = lead['Name'].replace(' ', '_').replace('/', '_')
    folder = f"PROSPECCAO_VENDAS/{name}"
    os.makedirs(folder, exist_ok=True)

    if not url or url == "N/A" or pd.isna(url):
        return

    try:
        # Check if URL is absolute, if not prepend https://
        if not url.startswith('http'):
            url = f"https://{url}"

        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
        page = await context.new_page()
        await page.goto(url, timeout=45000, wait_until="networkidle")
        await page.screenshot(path=f"{folder}/screenshot_site.png")
        await browser.close()

        dossier_text = f"""📊 MINI-DOSSIÊ TÉCNICO: {lead['Name']}

🏢 Empresa: {lead['Name']}
⭐ Rating Google: {lead['Rating']}
📍 Localização: {lead['Phone']} (WhatsApp)
🌐 Website: {url}

🔴 GARGALO TÉCNICO IDENTIFICADO:
O site está online e recebendo tráfego, mas NÃO possui Meta Pixel ou Google Tags instalados.
A empresa está "rasgando" dinheiro em anúncios (se houver) ou perdendo a chance de remarketing.

💡 OPORTUNIDADE P/ SUA AGÊNCIA:
Ligue oferecendo a implementação do Pixel como "Auditoria Gratuita" e feche o contrato de Gestão de Tráfego.
"""
        with open(f"{folder}/dossier_tecnico.txt", "w") as f:
            f.write(dossier_text)

        print(f"Dossier and screenshot generated for {lead['Name']}.")
    except Exception as e:
        print(f"Error generating dossier for {lead['Name']}: {e}")

async def main():
    # 1. Load the leads
    try:
        df = pd.read_excel("Mineracao_B2B_TURBO.xlsx", sheet_name="Lista Completa")
    except FileNotFoundError:
        print("Error: Mineracao_B2B_TURBO.xlsx not found. Run minerador_b2b.py first.")
        return

    # 2. Select the 3 'Hottest' Leads (High Rating but NO Pixel)
    # Sort by Rating descending and filter for NO Pixel
    # Filter for NO Pixel and valid URLs (not Google Ads redirect paths like /aclk)
    hot_candidates = df[
        (df['Tem_Pixel_Meta'] == "Não") &
        (df['Website'] != "N/A") &
        (~df['Website'].str.contains('/aclk', na=False))
    ]
    hot_leads = hot_candidates.sort_values(by='Rating', ascending=False).head(3)

    if hot_leads.empty:
        print("No hot leads found with websites but without pixels.")
        return

    print(f"Selected {len(hot_leads)} hot leads for prospecção.")

    # 3. Generate assets
    async with async_playwright() as p:
        for index, lead in hot_leads.iterrows():
            await generate_dossier(p, lead)

    # 4. Generate Pricing Table
    pricing = """💰 TABELA DE PREÇOS SUGERIDA: ORACLE B2B DATA MINER

🥉 Pacote Bronze (30 leads auditados): R$ 147,00
🥈 Pacote Prata (80 leads auditados): R$ 297,00
🥇 Pacote Ouro (Inventário Completo + Atualizações mensais): R$ 597,00

🚀 NOTA: Cada lead auditado inclui Telefone (WhatsApp), Diagnóstico de Pixel e Links de Redes Sociais.
"""
    with open("precos.txt", "w") as f:
        f.write(pricing)

    print("Pricing table 'precos.txt' created.")

if __name__ == "__main__":
    asyncio.run(main())
