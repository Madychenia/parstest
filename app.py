import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime

st.set_page_config(page_title="Price Monitor PRO", layout="wide")

# Стиль для компактности и цветов
st.markdown("""
    <style>
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    .last-update { font-size: 14px; color: gray; }
    div[data-testid="stColumn"] { display: flex; align-items: center; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен")

# --- ВЕРХНЯЯ ПАНЕЛЬ (Курс и Время) ---
col1, col2 = st.columns([1, 2])
with col1:
    user_rate = st.number_input("Курс ($):", value=44.55, step=0.05)
with col2:
    # Показываем время прямо сейчас
    now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    st.markdown(f"<p class='last-update'>Последняя проверка цен:<br><b>{now}</b> (обновление раз в сутки)</p>", unsafe_allow_html=True)

# --- ФУНКЦИЯ ПАРСИНГА (с кэшем на 24 часа) ---
@st.cache_data(ttl=86400) # 86400 секунд = 24 часа
def fetch_all_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        results = []
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        
        for i, row in df.iterrows():
            url = row.get('ссылка')
            selector = row.get('селектор')
            price_uah = None
            
            if url and not pd.isna(url):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    element = soup.select_one(selector)
                    if element:
                        clean_price = re.sub(r'\D', '', element.text.strip())
                        price_uah = int(clean_price)
                except:
                    pass

            if price_uah:
                price_usd = round(price_uah / rate, 1)
                display_val = f'<span class="uah">{price_uah:,} ₴</span> / <span class="usd">{price_usd}$</span>'
            else:
                display_val = "—"

            results.append({
                'Модель': row.get('модель', '—'),
                'Магазин': row.get('магазин', '—'),
                'Цена': display_val
            })
            time.sleep(0.2) # Небольшая пауза, чтобы не забанили
            
        res_df = pd.DataFrame(results)
        return res_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first')
    except Exception as e:
        return pd.DataFrame([{"Ошибка": str(e)}])

# --- ВКЛАДКИ ---
tab1, tab2 = st.tabs(["📦 ОПТ", "🛍️ РОЗНИЦА"])

with tab1:
    data_opt = fetch_all_prices('links.csv', user_rate)
    st.write(data_opt.to_html(escape=False), unsafe_allow_html=True)

with tab2:
    data_roz = fetch_all_prices('links_r.csv', user_rate)
    st.write(data_roz.to_html(escape=False), unsafe_allow_html=True)

# Кнопка для принудительного сброса кэша (если вдруг надо обновить прямо сейчас)
if st.sidebar.button("♻️ Обновить принудительно"):
    st.cache_data.clear()
    st.rerun()
