import asyncio
import pandas as pd
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import random
import os

def send_email(to_email, agency_name, pdf_report_path, sample_dossier_path, my_email, my_password, smtp_server="smtp.gmail.com", smtp_port=587):
    """Sends the sales email with PDF report and sample dossier as attachments."""
    msg = MIMEMultipart()
    msg['From'] = my_email
    msg['To'] = to_email
    msg['Subject'] = f"Oportunidade Técnica: 91,4% das Imobiliárias de Londrina com erro de Pixel"

    body = f"""Olá, Responsável da {agency_name}, tudo bem?

Meu nome é Diego e sou Arquiteto de Dados B2B. Acabo de finalizar uma auditoria regional em Londrina, Cambé e Ibiporã e identifiquei um gargalo técnico massivo que pode ser a chave para sua agência escalar em 2026.

**O Fato:** 91,4% das empresas de alto padrão (Imobiliárias, Clínicas e Escolas) possuem sites ativos e tráfego, mas NÃO possuem Meta Pixel ou Google Tags instalados. Elas estão perdendo dados e dinheiro agora mesmo.

Tenho em mãos o **Relatório Estratégico de Auditoria Regional**, um inventário completo com 150+ leads auditados individualmente.

**O que estou entregando:**
- Nome e WhatsApp direto do decisor.
- Diagnóstico exato de Pixel (Sim/Não).
- Link de Redes Sociais e Rating.
- Dossiê técnico pronto para abordagem de vendas.

Para você validar a qualidade da minha inteligência, estou anexando um **Mini-Dossiê de Amostra** e o **Relatório Estratégico** em PDF.

Gostaria de adquirir o inventário completo de Londrina e sair na frente da concorrência?

Aguardo seu retorno para conversarmos sobre pacotes exclusivos para sua agência.

Atenciosamente,

**Diego**
Oracle B2B Data Miner
"""
    msg.attach(MIMEText(body, 'plain'))

    # Attachment 1: PDF Report
    if pdf_report_path and os.path.exists(pdf_report_path):
        with open(pdf_report_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(pdf_report_path)}")
            msg.attach(part)

    # Attachment 2: Sample Dossier
    if sample_dossier_path and os.path.exists(sample_dossier_path):
        with open(sample_dossier_path, "rb") as attachment:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename= {os.path.basename(sample_dossier_path)}")
            msg.attach(part)

    try:
        # For simulation, we won't actually send emails to avoid auth errors in sandbox
        print(f"SIMULATION: Sending email to {agency_name} ({to_email})...")
        # server = smtplib.SMTP(smtp_server, smtp_port)
        # server.starttls()
        # server.login(my_email, my_password)
        # server.send_message(msg)
        # server.quit()
        return True
    except Exception as e:
        print(f"Error sending to {agency_name}: {e}")
        return False

async def main():
    # 1. Load the Buyers (Agencies)
    try:
        df_buyers = pd.read_excel("Mineracao_B2B_TURBO.xlsx", sheet_name="LISTA DE COMPRADORES")
    except Exception as e:
        print(f"Error: LISTA DE COMPRADORES not found: {e}")
        return

    # 2. Get a sample dossier path
    sample_lead_dir = "PROSPECCAO_VENDAS"
    if not os.path.exists(sample_lead_dir) or not os.listdir(sample_lead_dir):
        print("Error: No sample dossiers found. Run prospector_vendas.py first.")
        return

    first_lead = os.listdir(sample_lead_dir)[0]
    sample_dossier = f"{sample_lead_dir}/{first_lead}/dossier_tecnico.txt"
    pdf_report = "Relatorio_Oportunidades_Londrina_2026.pdf"

    # 3. Process Agencies
    count = 0
    for index, agency in df_buyers.iterrows():
        email = agency['Email']
        name = agency['Name']

        # Filter out NaN or "N/A" emails
        if email != "N/A" and not pd.isna(email):
            success = send_email(email, name, pdf_report, sample_dossier, "oracle@data.miner", "password")
            if success:
                count += 1
                # Anti-Spam random sleep
                sleep_time = random.uniform(30, 90) # Correct sleep forlive mode
                print(f"Sleeping for {sleep_time:.1f}s...")
                await asyncio.sleep(sleep_time)

            if count >= 20: # Limit per hour
                print("Reached hourly limit of 20 emails.")
                break

    print(f"Successfully processed {count} agency outreach tasks.")

if __name__ == "__main__":
    asyncio.run(main())
