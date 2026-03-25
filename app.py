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

# CSS для оформления рыночных курсов и основной таблицы
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .market-container { background-color: #f8f9fb; padding: 15px; border-radius: 12px; border: 1px solid #e1e4e8; margin-bottom: 20px; }
    .market-title { font-size: 14px; color: #586069; margin-bottom: 5px; }
    .market-value { font-size: 20px; font-weight: bold; color: #0366d6; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    table { width: 100% !important; border-radius: 10px; overflow: hidden; }
    th { background-color: #f6f8fa !important; }
    td { text-align: center !important; padding: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- ПАРСЕР РЫНОЧНЫХ КУРСОВ ---
@st.cache_data(ttl=300)  # Обновление данных раз в 5 минут
def get_market_data():
    url = "http://185.233.38.179:3000/"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = {"kiev": "—", "chernivtsi": "—", "avg_usdt": "—"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Находим все блоки городов (карточки)
        cards = soup.find_all('div', class_='card') # Базовый класс для блоков на таких сайтах
        
        usdt_all = []
        
        for card in cards:
            city = card.find('h5').text.strip().lower() if card.find('h5') else ""
            rows = card.find_all('div', class_='row') # Ищем строки внутри карточки
            
            # 1. Берем USD (первая строка)
            if len(rows) > 0:
                usd_val = rows[0].find_all('div')[-1].text.strip() # Значение в конце строки
                if "київ" in city: res["kiev"] = usd_val
                if "чернівці" in city: res["chernivtsi"] = usd_val
            
            # 2. Собираем USDT (предпоследняя и последняя строки)
            for i in [-1, -2]:
                if len(rows) >= abs(i):
                    usdt_val = rows[i].find_all('div')[-1].text.strip()
                    # Чистим строку, оставляя только цифры и точку
                    num = re.sub(r'[^\d.]', '', usdt_val.replace(',', '.'))
                    if num: usdt_all.append(float(num))
        
        if usdt_all:
            res["avg_usdt"] = round(np.mean(usdt_all), 2)
    except:
        pass
    return res

st.title("📱 Мониторинг цен: iPhone")

# --- БЛОК РЫНОЧНЫХ КУРСОВ ---
m_data = get_market_data()
mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.markdown(f"<div class='market-container'><div class='market-title'>📍 Киев (USD)</div><div class='market-value'>{m_data['kiev']}</div></div>", unsafe_allow_html=True)
with mc2:
    st.markdown(f"<div class='market-container'><div class='market-title'>📍 Черновцы (USD)</div><div class='market-value'>{m_data['chernivtsi']}</div></div>", unsafe_allow_html=True)
with mc3:
    st.markdown(f"<div class='market-container'><div class='market-title'>📊 Средний USDT (9 городов)</div><div class='market-value'>{m_data['avg_usdt']}</div></div>", unsafe_allow_html=True)

# --- УПРАВЛЕНИЕ КУРСОМ ---
col_rate, col_time, col_btn = st.columns([1.5, 2.5, 1.5])
with col_rate:
    user_rate = st.number_input("Ваш рабочий курс ($):", value=44.55, step=0.01)
with col_time:
    now = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"<div style='margin-top:10px; color:gray;'>Последнее обновление: <b>{now}</b></div>", unsafe_allow_html=True)
with col_btn:
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        st.cache_data.clear()
        st.rerun()

# --- ОСНОВНОЙ ПАРСИНГ ТОВАРОВ ---
@st.cache_data(ttl=86400)
def fetch_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        
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
                val = f'<span class="uah">{price_uah:,} ₴</span><br><span class="usd">{price_usd}$</span>'
            else:
                val = "—"
            results.append({'Модель': row.get('модель', '—'), 'Магазин': row.get('магазин', '—'), 'Цена': val})
            time.sleep(0.05)
        return pd.DataFrame(results)
    except:
        return pd.DataFrame()

# --- ТАБЛИЦА С ФИЛЬТРОМ ---
all_data = fetch_prices('links.csv', user_rate)
if not all_data.empty:
    all_data['Серия'] = all_data['Модель'].apply(lambda x: re.search(r'\d+', str(x)).group() if re.search(r'\d+', str(x)) else "Прочее")
    series_list = sorted(all_data['Серия'].unique(), key=lambda x: int(x) if x.isdigit() else 999)
    selected_series = st.selectbox("Выберите серию iPhone:", series_list, index=len(series_list)-1)
    
    filtered_df = all_data[all_data['Серия'] == selected_series]
    pivot = filtered_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first')
    st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
else:
    st.error("Файл links.csv не найден.")
