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
    
    /* Компактные поля и выравнивание кнопки */
    [data-testid="stNumberInput"], [data-testid="stSelectbox"] {
        max-width: 250px;
    }
    div.stButton {
        margin-top: 28px;
    }
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

# Настройка правильного времени (Киев)
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

# --- ВКЛАДКИ ---
tab_used, tab_new = st.tabs(["Used (Б/У)", "New (Новые)"])

def show_category_table(file_name):
    data = fetch_prices(file_name, user_rate)
    if not data.empty:
        # Берем уникальные категории из твоего CSV
        cat_list = sorted(data['Категория'].unique())
        
        # Выпадающий список (теперь компактный)
        selected_cat = st.selectbox(f"Выберите категорию ({file_name}):", cat_list, key=file_name)
        
        filtered = data[data['Категория'] == selected_cat]
        
        # Строим сводную таблицу
        pivot = filtered.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
            index='Модель', 
            columns='Магазин', 
            values='Цена'
        ).fillna("—")
        
        st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
    else:
        st.info(f"Файл {file_name} пуст или не найден. Добавьте его в репозиторий.")

with tab_used:
    show_category_table('links.csv')

with tab_new:
    show_category_table('links_new.csv')
