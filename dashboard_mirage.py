import streamlit as st
import pandas as pd
import subprocess
import os
import time
import sys

st.set_page_config(page_title="Mirage Control Center V6.0", layout="wide", initial_sidebar_state="expanded")

# Custom CSS for Dark Mode Aesthetic
st.markdown("""
    <style>
    .stApp {
        background-color: #050505;
        color: #ffffff;
    }
    [data-testid="stSidebar"] {
        background-color: #0a0a0a;
    }
    .stButton>button {
        background-color: #00F0FF;
        color: #000000;
        font-weight: bold;
        border-radius: 10px;
        border: none;
        width: 100%;
    }
    .stButton>button:hover {
        background-color: #FFD700;
        color: #000000;
    }
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        padding: 20px;
        border-radius: 15px;
        border: 1px solid rgba(255, 255, 255, 0.05);
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

def run_script(args):
    """Executes a python script and yields logs."""
    # Use sys.executable for cross-platform compatibility (Windows/Linux)
    process = subprocess.Popen([sys.executable] + args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in process.stdout:
        yield line.strip()
    process.wait()

# Sidebar Navigation
st.sidebar.title("🦅 ORACLE B2B")
menu = st.sidebar.radio("Navegação", ["Minerar Novos Leads", "Banco de Dados", "Gerador de Dossiês", "Configurações"])

if menu == "Minerar Novos Leads":
    st.title("🎯 Search Sniper (Turbo Mode)")

    col1, col2 = st.columns(2)
    with col1:
        niche = st.text_input("Nicho de Mercado", placeholder="ex: Imobiliárias de Alto Padrão")
    with col2:
        city = st.text_input("Cidade", placeholder="ex: Londrina")

    if st.button("🚀 INICIAR OPERAÇÃO DE MINERAÇÃO"):
        if niche and city:
            st.info(f"Iniciando mineração para {niche} em {city}...")
            log_container = st.empty()
            logs = []

            for log_line in run_script(["minerador_b2b.py", niche, city]):
                logs.append(log_line)
                # Keep log buffer small to prevent memory leaks
                if len(logs) > 100: logs.pop(0)
                log_container.code("\n".join(logs[-15:])) # Show last 15 lines

            st.success("Operação finalizada com sucesso!")
        else:
            st.error("Por favor, preencha o Nicho e a Cidade.")

elif menu == "Banco de Dados":
    st.title("💎 A Tabela de Ouro")

    if os.path.exists("Mineracao_B2B_TURBO.xlsx"):
        df = pd.read_excel("Mineracao_B2B_TURBO.xlsx", sheet_name="Lista Completa")

        # Stats
        total = len(df)
        no_pixel = len(df[df['Tem_Pixel_Meta'] == "Não"])

        c1, c2, c3 = st.columns(3)
        c1.metric("Total Minerado", total)
        c2.metric("Sem Pixel (Hot)", no_pixel)
        c3.metric("Taxa de Oportunidade", f"{(no_pixel/total*100):.1f}%" if total > 0 else "0%")

        # Filters
        pixel_filter = st.multiselect("Filtrar por Pixel", options=["Sim", "Não"], default=["Sim", "Não"])
        filtered_df = df[df['Tem_Pixel_Meta'].isin(pixel_filter)]

        st.dataframe(filtered_df, use_container_width=True)

        if st.button("📥 Baixar Excel Completo"):
            with open("Mineracao_B2B_TURBO.xlsx", "rb") as f:
                st.download_button("Clique aqui para baixar", f, file_name="leads_export.xlsx")
    else:
        st.warning("Nenhum dado minerado ainda. Vá para a aba 'Minerar' primeiro.")

elif menu == "Gerador de Dossiês":
    st.title("📊 Gerador de Ativos de Venda")

    if st.button("🔥 GERAR DOSSIÊS DAS 3 MELHORES OPORTUNIDADES"):
        st.info("Iniciando geração de screenshots e relatórios técnicos...")
        log_container = st.empty()
        logs = []
        for log_line in run_script(["prospector_vendas.py"]):
            logs.append(log_line)
            log_container.code("\n".join(logs[-10:]))
        st.success("Dossiês gerados na pasta PROSPECCAO_VENDAS!")

elif menu == "Configurações":
    st.title("⚙️ Configurações do Sistema")
    st.write("Hardware Detectado: Lenovo i5 13th Gen - 16GB RAM")
    st.write("Status do Proxy: Inativo (Conexão Direta)")
    st.write("Versão do Mirage: 7.0 Elite (Analytic Scale)")

    st.divider()
    st.subheader("🛡️ Gestão de Dados")
    if st.button("🗑️ LIMPAR BANCO DE DADOS (STRESS TEST)"):
        if os.path.exists("leads.db"):
            os.remove("leads.db")
            st.success("Banco de dados SQLite removido!")
        if os.path.exists("Mineracao_B2B_TURBO.xlsx"):
            os.remove("Mineracao_B2B_TURBO.xlsx")
            st.info("Arquivo Excel de cache removido.")
