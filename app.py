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
    if st.button("♻️ ОБНОВИТЬ"):
        st.cache_data.clear()
        st.rerun()

try:
    kiev_tz = pytz.timezone('Europe/Kyiv')
    now_kiev = datetime.now(kiev_tz)
    time_str = now_kiev.strftime('%H:%M:%S')
except:
    time_str = datetime.now().strftime('%H:%M:%S')

st.write(f"Обновлено (Киев): **{time_str}**")

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
            
            p_usd = round(p_uah / rate, 1) if p_uah else 0
            val = f'<span class="uah">{p_uah:,} ₴</span><br><span class="usd">{p_usd}$</span>' if p_uah else "—"
            
            results.append({
                'Модель': row.get('модель', '—'), 
                'Магазин': row.get('магазин', '—'), 
                'Цена': val,
                'Категория': row.get('категория', 'Без категории') 
            })
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ СОРТИРОВКИ ПАМЯТИ ---
def sort_by_memory(model_name):
    # Ищем числа рядом с ГБ, GB или ТБ, TB
    size = re.findall(r'(\d+)\s*(?:ГБ|GB|ТБ|TB|tb|gb)', str(model_name), re.IGNORECASE)
    if not size:
        return 0
    val = int(size[0])
    # Если это Терабайты (1, 2), умножаем на 1024 для правильного веса
    if 'ТБ' in str(model_name).upper() or 'TB' in str(model_name).upper() or val < 10:
        return val * 1024
    return val

# --- ВКЛАДКИ ---
tab_used, tab_new = st.tabs(["Used (Б/У)", "New (Новые)"])

def show_category_table(file_name):
    data = fetch_prices(file_name, user_rate)
    if not data.empty:
        cat_list = sorted(data['Категория'].unique())
        selected_cat = st.selectbox(f"Выберите категорию ({file_name}):", cat_list, key=file_name)
        
        filtered = data[data['Категория'] == selected_cat].copy()
        
        # Создаем временную колонку для правильной сортировки моделей
        filtered['mem_rank'] = filtered['Модель'].apply(sort_by_memory)
        filtered = filtered.sort_values(by='mem_rank')
        
        # Строим таблицу
        pivot = filtered.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
            index='Модель', 
            columns='Магазин', 
            values='Цена'
        ).fillna("—")
        
        # Чтобы pivot не сбросил нашу сортировку моделей
        pivot = pivot.reindex(filtered['Модель'].unique())
        
        st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
    else:
        st.info(f"Файл {file_name} не найден.")

with tab_used:
    show_category_table('links.csv')

with tab_new:
    show_category_table('links_new.csv')
