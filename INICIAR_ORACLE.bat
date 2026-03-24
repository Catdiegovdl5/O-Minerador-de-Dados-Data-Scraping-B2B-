@echo off
TITLE ORACLE B2B - Mirage V6.0
echo --------------------------------------------------
echo   🦅 INICIANDO ORACLE B2B - MIRAGE CONTROL CENTER
echo --------------------------------------------------
echo.
echo Verificando dependencias...
pip install -r requirements.txt
playwright install chromium
echo.
echo Abrindo Dashboard no navegador...
streamlit run dashboard_mirage.py
pause
