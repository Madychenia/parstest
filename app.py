import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
import numpy as np

st.set_page_config(page_title="iPhone Price Monitor", layout="wide", initial_sidebar_state="collapsed")

# Стили для оформления блоков
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .market-container { background-color: #f8f9fb; padding: 10px; border-radius: 12px; border: 1px solid #e1e4e8; text-align: center; min-height: 80px; }
    .market-title { font-size: 13px; color: #586069; margin-bottom: 2px; }
    .market-value { font-size: 18px; font-weight: bold; color: #0366d6; }
    </style>
    """, unsafe_allow_html=True)

# --- НОВЫЙ СУПЕР-ПАРСЕР КУРСОВ ---
@st.cache_data(ttl=300)
def get_market_data():
    url = "http://185.233.38.179:3000/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    res = {"kiev": "—", "chernivtsi": "—", "avg_white": "—", "avg_blue": "—"}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.encoding = 'utf-8'
        text = r.text
        
        # 1. Извлекаем все курсы формата XX,XX или XX.XX
        all_numbers = re.findall(r'(\d{2}[.,]\d{2})', text)
        clean_nums = [float(n.replace(',', '.')) for n in all_numbers]
        
        # 2. Фильтруем цифры, похожие на курс (от 43 до 46)
        market_nums = [n for n in clean_nums if 43.0 <= n <= 46.0]
        
        if market_nums:
            # Киев и Черновцы (обычно это первые значения в списке для своих блоков)
            # Если в списке много данных, берем из определенных позиций
            if len(market_nums) >= 1: res["kiev"] = market_nums[0]
            if len(market_nums) >= 9: res["chernivtsi"] = market_nums[8] # Примерная позиция для 5-го города
            
            # Разделяем на обычный USDT (белый) и синий
            # Обычно они идут парами: [USD, USDT, USDT синий]
            white_list = market_nums[1::3] # Каждый второй в тройке
            blue_list = market_nums[2::3]  # Каждый третий в тройке
            
            if white_list: res["avg_white"] = round(np.mean(white_list), 2)
            if blue_list: res["avg_blue"] = round(np.mean(blue_list), 2)
    except:
        pass
    return res

st.title("📱 Мониторинг цен")

# --- ВЕРХНЯЯ ПАНЕЛЬ ---
m = get_market_data()
c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Киев USD</div><div class='market-value'>{m['kiev']}</div></div>", unsafe_allow_html=True)
with c2: st.markdown(f"<div class='market-container'><div class='market-title'>📍 Черновцы USD</div><div class='market-value'>{m['chernivtsi']}</div></div>", unsafe_allow_html=True)
with c3: st.markdown(f"<div class='market-container'><div class='market-title'>⚪ Средний USDT</div><div class='market-value'>{m['avg_white']}</div></div>", unsafe_allow_html=True)
with c4: st.markdown(f"<div class='market-container'><div class='market-title'>🔵 Средний USDT (синий)</div><div class='market-value'>{m['avg_blue']}</div></div>", unsafe_allow_html=True)

# --- ПОЛЕ ВВОДА КУРСА ---
user_rate = st.number_input("Ваш рабочий курс ($):", value=44.55, step=0.01)

# --- ТАБЛИЦА ТОВАРОВ ---
@st.cache_data(ttl=3600)
def fetch_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name)
        df.columns = [c.strip().lower() for c in df.columns]
        # ... (здесь логика парсинга твоих ссылок из links.csv)
        # Для теста вернем пустой или обработанный кадр
        return df
    except:
        return pd.DataFrame()

# Инструкция для пользователя
st.info("Если курсы все еще '—', попробуйте нажать 'Обновить всё'. Это может быть связано с временной блокировкой IP.")
