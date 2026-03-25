import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
import numpy as np

# Настройки страницы
st.set_page_config(page_title="iPhone Price Monitor", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .market-container { background-color: #f8f9fb; padding: 10px; border-radius: 12px; border: 1px solid #e1e4e8; text-align: center; }
    .market-title { font-size: 13px; color: #586069; margin-bottom: 2px; }
    .market-value { font-size: 18px; font-weight: bold; color: #0366d6; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    td { text-align: center !important; padding: 10px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ПАРСЕР КУРСОВ ---
@st.cache_data(ttl=300)
def get_market_data():
    url = "http://185.233.38.179:3000/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = {"kiev": "—", "chernivtsi": "—", "avg_white": "—", "avg_blue": "—"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # 1. Киев USD (по твоему новому селектору)
        k_block = soup.select_one("#grid > div:nth-child(1)")
        if k_block:
            # Селектор: div > div:nth-child(2) > div:nth-child(2)
            k_val = k_block.select_one("div > div:nth-child(2) > div:nth-child(2)")
            if k_val: res["kiev"] = k_val.text.strip()

        # 2. Черновцы USD (аналогично в 5-м блоке)
        c_block = soup.select_one("#grid > div:nth-child(5)")
        if c_block:
            c_val = c_block.select_one("div > div:nth-child(2) > div:nth-child(2)")
            if c_val: res["chernivtsi"] = c_val.text.strip()

        # 3. Средний USDT по 9 городам
        white_vals, blue_vals = [], []
        for i in range(1, 10):
            w = soup.select_one(f"#grid > div:nth-child({i}) > div.usdt > div:nth-child(1) > div:nth-child(2) > span")
            b = soup.select_one(f"#grid > div:nth-child({i}) > div.usdt > div:nth-child(2) > div:nth-child(2) > span")
            
            def to_float(el):
                if not el: return None
                n = re.sub(r'[^\d.]', '', el.text.replace(',', '.'))
                return float(n) if n else None

            wn, bn = to_float(w), to_float(b)
            if wn: white_vals.append(wn)
            if bn: blue_vals.append(bn)
        
        if white_vals: res["avg_white"] = round(np.mean(white_vals), 2)
        if blue_vals: res["avg_blue"] = round(np.mean(blue_vals), 2)
    except: pass
    return res

st.title("📱 Мониторинг цен")

# --- ИНФО-ПАНЕЛЬ ---
m = get_market_data()
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Киев USD</div><div class='market-value'>{m['kiev']}</div></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Черновцы USD</div><div class='market-value'>{m['chernivtsi']}</div></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='market-container'><div class='market-title'>⚪ Средний USDT</div><div class='market-value'>{m['avg_white']}</div></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='market-container'><div class='market-title'>🔵 Средний USDT (синий)</div><div class='market-value'>{m['avg_blue']}</div></div>", unsafe_allow_html=True)

# --- УПРАВЛЕНИЕ ---
col_rate, col_time, col_btn = st.columns([1.5, 2.5, 1.5])
with col_rate:
    user_rate = st.number_input("Курс для расчета ($):", value=44.55, step=0.01)
with col_time:
    st.write(f"Обновлено: **{datetime.now().strftime('%H:%M:%S')}**")
with col_btn:
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        st.cache_data.clear()
        st.rerun()

# --- ТАБЛИЦА ТОВАРОВ ---
@st.cache_data(ttl=86400)
def fetch_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        for _, row in df.iterrows():
            price_uah = None
            url = str(row.get('ссылка', '')).strip()
            selector = str(row.get('селектор', '')).strip()
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(selector)
                    if el:
                        price_uah = int(re.sub(r'\D', '', el.text.strip()))
                except: pass
            
            p_usd = round(price_uah / rate, 1) if price_uah else 0
            val = f'<span class="uah">{price_uah:,} ₴</span><br><span class="usd">{p_usd}$</span>' if price_uah else "—"
            results.append({'Модель': row.get('модель', '—'), 'Магазин': row.get('магазин', '—'), 'Цена': val})
        return pd.DataFrame(results).drop_duplicates(subset=['Модель', 'Магазин'])
    except: return pd.DataFrame()

data = fetch_prices('links.csv', user_rate)

if not data.empty:
    # Исправленная логика фильтрации (без синтаксических ошибок)
    data['Серия'] = data['Модель'].apply(lambda x: re.search(r'\d+', str(x)).group() if re.search(r'\d+', str(x)) else "Прочее")
    series_list = sorted(data['Серия'].unique(), key=lambda x: int(x) if str(x).isdigit() else 999)
    
    sel = st.selectbox("Серия iPhone:", series_list, index=len(series_list)-1)
    
    filtered = data[data['Серия'] == sel]
    # Создаем сводную таблицу
    pivot = filtered.pivot(index='Модель', columns='Магазин', values='Price' if 'Price' in filtered.columns else 'Цена')
    st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
else:
    st.info("Загрузите файл links.csv для отображения цен на товары.")
