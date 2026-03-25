import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import numpy as np

# Настройки страницы
st.set_page_config(page_title="Мониторинг цен", layout="wide", initial_sidebar_state="collapsed")

# --- СТИЛИ (Кнопка и блоки) ---
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .market-container { background-color: #f8f9fb; padding: 10px; border-radius: 12px; border: 1px solid #e1e4e8; text-align: center; min-height: 80px; }
    .market-title { font-size: 13px; color: #586069; margin-bottom: 2px; }
    .market-value { font-size: 18px; font-weight: bold; color: #0366d6; }
    </style>
    """, unsafe_allow_html=True)

# --- ФУНКЦИЯ ПАРСИНГА ---
@st.cache_data(ttl=300)
def get_market_data():
    url = "http://185.233.38.179:3000/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    res = {"kiev": "—", "chernivtsi": "—", "avg_white": "—", "avg_blue": "—"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.encoding = 'utf-8'
        all_text = r.text
        # Ищем все числа курса
        nums = [float(n.replace(',', '.')) for n in re.findall(r'(\d{2}[.,]\d{2})', all_text)]
        valid = [n for n in nums if 43.0 <= n <= 46.0]
        if valid:
            res["kiev"] = valid[0]
            if len(valid) >= 9: res["chernivtsi"] = valid[8]
            res["avg_white"] = round(np.mean(valid[1::3]), 2) if len(valid) > 1 else "—"
            res["avg_blue"] = round(np.mean(valid[2::3]), 2) if len(valid) > 2 else "—"
    except: pass
    return res

st.title("📱 Мониторинг цен")

# --- ВЕРХНЯЯ ПАНЕЛЬ С КУРСАМИ ---
m = get_market_data()
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Киев USD</div><div class='market-value'>{m['kiev']}</div></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Черновцы USD</div><div class='market-value'>{m['chernivtsi']}</div></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='market-container'><div class='market-title'>⚪ Средний USDT</div><div class='market-value'>{m['avg_white']}</div></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='market-container'><div class='market-title'>🔵 Средний USDT (синий)</div><div class='market-value'>{m['avg_blue']}</div></div>", unsafe_allow_html=True)

# --- УПРАВЛЕНИЕ И КНОПКА ---
col_input, col_btn = st.columns([4, 1])
with col_input:
    user_rate = st.number_input("Ваш рабочий курс ($):", value=44.55, step=0.01)
with col_btn:
    st.write(" ") # Отступ для выравнивания
    # ВОТ ОНА, ТВОЯ КНОПКА
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        st.cache_data.clear()
        st.rerun()

st.info("Если курсы всё еще '—', нажмите кнопку 'ОБНОВИТЬ ВСЁ'. Это сбросит кэш и попробует достучаться до сайта заново.")
