import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime

# Настройка страницы (убираем меню и отступы)
st.set_page_config(page_title="Price Monitor PRO", layout="wide", initial_sidebar_state="collapsed")

# Продвинутый CSS: скрываем боковое меню, красим цены, ровняем кнопки
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    .update-text { font-size: 14px; color: gray; line-height: 1.2; }
    /* Центрируем таблицу и кнопки */
    .stButton button { width: 100%; margin-top: 25px; }
    table { width: 100% !important; border-radius: 10px; overflow: hidden; }
    th { background-color: #f0f2f6 !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен")

# --- ВЕРХНЯЯ ПАНЕЛЬ ---
col_rate, col_time, col_btn = st.columns([1.5, 2.5, 1.5])

with col_rate:
    user_rate = st.number_input("Курс ($):", value=44.55, step=0.01)

with col_time:
    # Показываем время последнего захода/обновления
    now = datetime.now().strftime("%H:%M:%S")
    today = datetime.now().strftime("%d.%m.%Y")
    st.markdown(f"<p class='update-text'>Дата: <b>{today}</b><br>Проверка в: <b>{now}</b></p>", unsafe_allow_html=True)

with col_btn:
    if st.button("♻️ ОБНОВИТЬ СЕЙЧАС"):
        st.cache_data.clear()
        st.rerun()

# --- ФУНКЦИЯ ПАРСИНГА (кэш на 24 часа) ---
@st.cache_data(ttl=86400)
def fetch_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        results = []
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
        
        for i, row in df.iterrows():
            url = row.get('ссылка')
            selector = row.get('селектор')
            price_uah = None
            
            if url and not pd.isna(url) and str(url).startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    element = soup.select_one(selector)
                    if element:
                        price_uah = int(re.sub(r'\D', '', element.text.strip()))
                except: pass

            if price_uah:
                price_usd = round(price_uah / rate, 1)
                val = f'<span class="uah">{price_uah:,} ₴</span> / <span class="usd">{price_usd}$</span>'
            else:
                val = "—"

            results.append({
                'Модель': row.get('модель', '—'),
                'Магазин': row.get('магазин', '—'),
                'Цена': val
            })
            time.sleep(0.1)
            
        res_df = pd.DataFrame(results)
        return res_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first')
    except Exception as e:
        return pd.DataFrame([{"Ошибка": "Проверьте файлы CSV"}])

# --- ТАБЛИЦЫ ---
tab_opt, tab_roz = st.tabs(["📦 ОПТ", "🛍️ РОЗНИЦА"])

with tab_opt:
    with st.spinner('Парсинг ОПТ...'):
        st.write(fetch_prices('links.csv', user_rate).to_html(escape=False), unsafe_allow_html=True)

with tab_roz:
    with st.spinner('Парсинг РОЗНИЦА...'):
        st.write(fetch_prices('links_r.csv', user_rate).to_html(escape=False), unsafe_allow_html=True)
