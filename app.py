import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
import numpy as np

st.set_page_config(page_title="iPhone Price Monitor", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .market-container { background-color: #f8f9fb; padding: 10px; border-radius: 12px; border: 1px solid #e1e4e8; text-align: center; }
    .market-title { font-size: 13px; color: #586069; margin-bottom: 2px; }
    .market-value { font-size: 18px; font-weight: bold; color: #0366d6; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    table { width: 100% !important; }
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
        
        # 1. Киев и Черновцы (USD - первая строка в блоках)
        # На сайте это обычно div.item:nth-child(1) внутри блока города
        kiev_usd = soup.select_one("#grid > div:nth-child(1) > div.items > div:nth-child(1) .val")
        chern_usd = soup.select_one("#grid > div:nth-child(5) > div.items > div:nth-child(1) .val")
        
        if kiev_usd: res["kiev"] = kiev_usd.text.strip()
        if chern_usd: res["chernivtsi"] = chern_usd.text.strip()

        # 2. Сбор USDT для среднего (по всем 9 городам)
        white_vals, blue_vals = [], []
        for i in range(1, 10):
            # Селекторы, которые ты прислал (подставляем индекс города i)
            white = soup.select_one(f"#grid > div:nth-child({i}) > div.usdt > div:nth-child(1) > div:nth-child(2) > span")
            blue = soup.select_one(f"#grid > div:nth-child({i}) > div.usdt > div:nth-child(2) > div:nth-child(2) > span")
            
            if white:
                num = re.sub(r'[^\d.]', '', white.text.replace(',', '.'))
                if num: white_vals.append(float(num))
            if blue:
                num = re.sub(r'[^\d.]', '', blue.text.replace(',', '.'))
                if num: blue_vals.append(float(num))
        
        if white_vals: res["avg_white"] = round(np.mean(white_vals), 2)
        if blue_vals: res["avg_blue"] = round(np.mean(blue_vals), 2)
    except: pass
    return res

st.title("📱 Мониторинг цен")

# --- ИНФО-ПАНЕЛЬ КУРСОВ ---
m = get_market_data()
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Киев USD</div><div class='market-value'>{m['kiev']}</div></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Черновцы USD</div><div class='market-value'>{m['chernivtsi']}</div></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='market-container'><div class='market-title'>⚪ Средний USDT</div><div class='market-value'>{m['avg_white']}</div></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='market-container'><div class='market-title'>🔵 Средний USDT (синий)</div><div class='market-value'>{m['avg_blue']}</div></div>", unsafe_allow_html=True)

# --- УПРАВЛЕНИЕ ---
col_rate, col_time, col_btn = st.columns([1.5, 2.5, 1.5])
with col_rate:
    user_rate = st.number_input("Ваш рабочий курс ($):", value=44.55, step=0.01)
with col_time:
    st.write(f"Обновлено: **{datetime.now().strftime('%H:%M:%S')}**")
with col_btn:
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        st.cache_data.clear()
        st.rerun()

# --- ТАБЛИЦА ТОВАРОВ ---
