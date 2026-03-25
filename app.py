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
    .market-container { background-color: #f8f9fb; padding: 15px; border-radius: 12px; border: 1px solid #e1e4e8; margin-bottom: 20px; min-height: 100px; }
    .market-title { font-size: 14px; color: #586069; margin-bottom: 5px; }
    .market-value { font-size: 20px; font-weight: bold; color: #0366d6; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    td { text-align: center !important; padding: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- УЛУЧШЕННЫЙ ПАРСЕР РЫНОЧНЫХ КУРСОВ ---
@st.cache_data(ttl=300)
def get_market_data():
    url = "http://185.233.38.179:3000/"
    # Добавляем заголовки, чтобы сайт не блокировал "бота"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    res = {"kiev": "—", "chernivtsi": "—", "avg_usdt": "—"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Ищем все текстовые блоки
        text_content = soup.get_text(separator='|', strip=True)
        
        # Ищем USD для Киева и Черновцов (универсальный поиск по тексту)
        parts = text_content.split('|')
        for i, part in enumerate(parts):
            clean_part = part.lower()
            if "київ" in clean_part and i+2 < len(parts):
                res["kiev"] = parts[i+2] # Обычно значение через пару элементов
            if "чернівці" in clean_part and i+2 < len(parts):
                res["chernivtsi"] = parts[i+2]
        
        # Поиск всех USDT через регулярные выражения
        usdt_pattern = re.findall(r'(\d{2}[,.]\d{1,3})', text_content)
        # Отфильтруем только те, что похожи на курс USDT (в районе 40-46)
        valid_usdt = [float(x.replace(',', '.')) for x in usdt_pattern if 40 < float(x.replace(',', '.')) < 47]
        
        if valid_usdt:
            res["avg_usdt"] = round(np.mean(valid_usdt), 2)
    except:
        pass
    return res

st.title("📱 Мониторинг цен: iPhone")

# --- ИНФО-ПАНЕЛЬ ---
m_data = get_market_data()
mc1, mc2, mc3 = st.columns(3)
with mc1:
    st.markdown(f"<div class='market-container'><div class='market-title'>📍 Киев (USD)</div><div class='market-value'>{m_data['kiev']}</div></div>", unsafe_allow_html=True)
with mc2:
    st.markdown(f"<div class='market-container'><div class='market-title'>📍 Черновцы (USD)</div><div class='market-value'>{m_data['chernivtsi']}</div></div>", unsafe_allow_html=True)
with mc3:
    st.markdown(f"<div class='market-container'><div class='market-title'>📊 Средний USDT</div><div class='market-value'>{m_data['avg_usdt']}</div></div>", unsafe_allow_html=True)

# --- КУРС И ОБНОВЛЕНИЕ ---
col_rate, col_time, col_btn = st.columns([1.5, 2.5, 1.5])
with col_rate:
    user_rate = st.number_input("Ваш рабочий курс ($):", value=44.55, step=0.01)
with col_time:
    st.write(f"Обновлено в: **{datetime.now().strftime('%H:%M:%S')}**")
with col_btn:
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        st.cache_data.clear()
        st.rerun()

# --- ПАРСИНГ ТОВАРОВ (с защитой от ошибок в CSV) ---
@st.cache_data(ttl=86400)
def fetch_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        # Принудительно чистим названия колонок
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        # Проверка наличия нужных колонок
        required = ['модель', 'магазин', 'ссылка', 'селектор']
        if not all(col in df.columns for col in required):
            st.error(f"В CSV не хватает колонок! Нужны: {', '.join(required)}")
            return pd.DataFrame()

        results = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        for _, row in df.iterrows():
            url = str(row['ссылка']).strip()
            selector = str(row['селектор']).strip()
            price_uah = None
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(selector)
                    if el:
                        price_uah = int(re.sub(r'\D', '', el.text.strip()))
                except: pass

            price_display = "—"
            if price_uah:
                price_usd = round(price_uah / rate, 1)
                price_display = f'<span class="uah">{price_uah:,} ₴</span><br><span class="usd">{price_usd}$</span>'
            
            results.append({
                'Модель': row['модель'],
                'Магазин': row['магазин'],
                'Цена': price_display
            })
            time.sleep(0.05)
        
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка файла: {e}")
        return pd.DataFrame()

# --- ВЫВОД ТАБЛИЦЫ ---
all_data = fetch_prices('links.csv', user_rate)
if not all_data.empty:
    # Убираем дубликаты перед сводной таблицей, чтобы не было ошибки ValueError
    all_data = all_data.drop_duplicates(subset=['Модель', 'Магазин'], keep='first')
    
    all_data['Серия'] = all_data['Модель'].apply(lambda x: re.search(r'\d+', str(x)).group() if re.search(r'\d+', str(x)) else "Прочее")
    series = sorted(all_data['Серия'].unique(), key=lambda x: int(x) if x.isdigit() else 999)
    
    sel_series = st.selectbox("Выберите серию iPhone:", series, index=len(series)-1)
    
    filtered = all_data[all_data['Серия'] == sel_series]
    pivot = filtered.pivot(index='Модель', columns='Магазин', values='Цена')
    st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
