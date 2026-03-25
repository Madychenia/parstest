import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
from datetime import datetime

# Настройки страницы: убираем боковое меню и расширяем контент
st.set_page_config(page_title="Price Monitor", layout="wide", initial_sidebar_state="collapsed")

# CSS: черная гривна, красный доллар, аккуратная таблица
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    .update-text { font-size: 14px; color: gray; }
    table { width: 100% !important; border-radius: 10px; overflow: hidden; border: 1px solid #f0f2f6; }
    th { background-color: #f8f9fb !important; text-align: center !important; }
    td { text-align: center !important; padding: 12px !important; font-size: 16px !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен: РОЗНИЦА")

# --- ВЕРХНЯЯ ПАНЕЛЬ ---
col_rate, col_time, col_btn = st.columns([1.5, 2.5, 1.5])

with col_rate:
    user_rate = st.number_input("Курс доллара ($):", value=44.55, step=0.01)

with col_time:
    now = datetime.now().strftime("%H:%M:%S")
    st.markdown(f"<p class='update-text'>Обновлено в: <b>{now}</b><br>Данные из файла: links.csv</p>", unsafe_allow_html=True)

with col_btn:
    if st.button("♻️ ОБНОВИТЬ ЦЕНЫ"):
        st.cache_data.clear()
        st.rerun()

# --- ФУНКЦИЯ ПАРСИНГА (Кэш 24 часа) ---
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
                        # Оставляем только цифры
                        clean_price = re.sub(r'\D', '', element.text.strip())
                        price_uah = int(clean_price)
                except: pass

            if price_uah:
                price_usd = round(price_uah / rate, 1)
                val = f'<span class="uah">{price_uah:,} ₴</span><br><span class="usd">{price_usd}$</span>'
            else:
                val = "—"

            results.append({
                'Модель': row.get('модель', '—'),
                'Магазин': row.get('магазин', '—'),
                'Цена': val
            })
            time.sleep(0.05)
            
        return pd.DataFrame(results)
    except:
        return pd.DataFrame()

# --- ВЫВОД ТАБЛИЦЫ С ФИЛЬТРОМ ---
all_data = fetch_prices('links.csv', user_rate)

if not all_data.empty:
    # Авто-группировка по цифрам в названии (13, 14, 15...)
    all_data['Серия'] = all_data['Модель'].apply(
        lambda x: re.search(r'\d+', str(x)).group() if re.search(r'\d+', str(x)) else "Прочее"
    )
    
    series_list = sorted(all_data['Серия'].unique(), key=lambda x: int(x) if x.isdigit() else 999)
    
    # Выбор серии (кнопки-фильтры)
    selected_series = st.selectbox("Выберите модель iPhone:", series_list, index=len(series_list)-1)
    
    # Фильтруем и показываем
    filtered_df = all_data[all_data['Серия'] == selected_series]
    pivot = filtered_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first')
    
    st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
else:
    st.error("Файл links.csv не найден или пуст. Загрузите его на GitHub.")
