import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz

# Настройки страницы
st.set_page_config(page_title="Мониторинг цен", layout="wide", initial_sidebar_state="collapsed")

# Стили оформления
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    td { text-align: center !important; padding: 10px !important; }
    th { background-color: #f0f2f6 !important; text-align: center !important; }
    [data-testid="stNumberInput"], [data-testid="stSelectbox"] { max-width: 250px; }
    div.stButton { margin-top: 28px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен")

# --- ПАНЕЛЬ УПРАВЛЕНИЯ ---
col1, col2, col3 = st.columns([2, 2, 6])
with col1:
    user_rate = st.number_input("Курс для расчета ($):", value=44.55, step=0.01)
with col2:
    if st.button("♻️ ОБНОВИТЬ ЦЕНЫ"):
        st.cache_data.clear()
        st.rerun()

try:
    kiev_tz = pytz.timezone('Europe/Kyiv')
    now_kiev = datetime.now(kiev_tz)
    time_str = now_kiev.strftime('%H:%M:%S')
except:
    time_str = datetime.now().strftime('%H:%M:%S')

st.write(f"Обновлено (Киев): **{time_str}**")

# --- ШАГ 1: ПАРСИНГ ---
@st.cache_data(ttl=3600)
def get_raw_prices(file_name):
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        for _, row in df.iterrows():
            p_uah = None
            url = str(row.get('ссылка', '')).strip()
            sel = str(row.get('селектор', '')).strip()
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        digits = re.sub(r'\D', '', el.text.strip())
                        if digits: p_uah = int(digits)
                except: pass
            
            results.append({
                'Модель': row.get('модель', '—'), 
                'Магазин': row.get('магазин', '—'), 
                'Цена_ГРН': p_uah,
                'Категория': row.get('категория', 'Без категории') 
            })
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- ШАГ 2: БЕЗОПАСНЫЙ ПЕРЕСЧЕТ ---
def format_data(df, rate):
    formatted = df.copy()
    def process_row(p_uah):
        # Проверяем, что p_uah — это число и оно не пустое
        if pd.notnull(p_uah) and isinstance(p_uah, (int, float)) and rate > 0:
            try:
                p_usd = int(round(p_uah / rate)) # Убираем .0 через int()
                return f'<span class="uah">{int(p_uah):,} ₴</span><br><span class="usd">{p_usd:,} $</span>'
            except:
                return "—"
        return "—"
    
    formatted['Цена'] = formatted['Цена_ГРН'].apply(process_row)
    return formatted

# --- ВКЛАДКИ ---
tab_used, tab_new = st.tabs(["Used (Б/У)", "New (Новые)"])

def show_tab_content(file_name):
    raw_data = get_raw_prices(file_name)
    if not raw_data.empty:
        display_data = format_data(raw_data, user_rate)
        cat_list = raw_data['Категория'].unique().tolist()
        selected_cat = st.selectbox(f"Выберите категорию:", cat_list, key=file_name)
        
        filtered = display_data[display_data['Категория'] == selected_cat].copy()
        original_order = filtered['Модель'].unique().tolist()
        
        pivot = filtered.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
            index='Model', # Используем внутреннее имя для индекса
            columns='Магазин', 
            values='Цена'
        ).fillna("—")
        
        # Переименовываем индекс для красоты
        pivot.index.name = 'Модель'
        pivot = pivot.reindex(original_order)
        st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
    else:
        st.info(f"Файл {file_name} не найден.")

with tab_used:
    show_tab_content('links.csv')

with tab_new:
    show_tab_content('links_new.csv')
