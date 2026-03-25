import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# Настройки страницы
st.set_page_config(page_title="Мониторинг цен", layout="wide", initial_sidebar_state="collapsed")

# Стили для таблицы и компактного списка
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    td { text-align: center !important; padding: 10px !important; }
    th { background-color: #f0f2f6 !important; text-align: center !important; }
    /* Сужаем выпадающий список */
    [data-testid="stSelectbox"] { max-width: 300px; }
    </style>
    """, unsafe_allow_html=True)

# Убран заголовок : iPhone
st.title("📱 Мониторинг цен")

# --- ФУНКЦИЯ ПАРСИНГА ---
@st.cache_data(ttl=3600)
def fetch_prices(file_name, rate):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        for _, row in df.iterrows():
            p_uah = None
            url, sel = str(row.get('ссылка', '')).strip(), str(row.get('селектор', '')).strip()
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        digits = re.sub(r'\D', '', el.text.strip())
                        if digits: p_uah = int(digits)
                except: pass
            
            p_usd = round(p_uah / rate, 1) if p_uah else 0
            val = f'<span class="uah">{p_uah:,} ₴</span><br><span class="usd">{p_usd}$</span>' if p_uah else "—"
            results.append({'Модель': row.get('модель', '—'), 'Магазин': row.get('магазин', '—'), 'Цена': val})
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- ВЕРХНЯЯ ПАНЕЛЬ УПРАВЛЕНИЯ (Курс + Кнопка) ---
col_rate, col_btn = st.columns([4, 1])
with col_rate:
    user_rate = st.number_input("Курс для расчета ($):", value=44.55, step=0.01)
with col_btn:
    st.write(" ") # Выравнивание
    if st.button("♻️ ОБНОВИТЬ"):
        st.cache_data.clear()
        st.rerun()

st.write(f"Обновлено: **{datetime.now().strftime('%H:%M:%S')}**")

# --- ВЫВОД ТАБЛИЦЫ ---
data = fetch_prices('links.csv', user_rate)

if not data.empty:
    data['Серия'] = data['Модель'].apply(lambda x: re.search(r'\d+', str(x)).group() if re.search(r'\d+', str(x)) else "Прочее")
    series_list = sorted(data['Серия'].unique(), key=lambda x: int(x) if str(x).isdigit() else 999)
    
    # Компактный выбор серии
    selected_series = st.selectbox("Серия:", series_list, index=len(series_list)-1)
    
    filtered = data[data['Серия'] == selected_series]
    pivot = filtered.drop_duplicates(subset=['Модель', 'Магазин']).pivot(index='Модель', columns='Магазин', values='Цена').fillna("—")
    
    st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
else:
    st.warning("Загрузите корректный links.csv")
