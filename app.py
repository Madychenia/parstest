import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import pytz
import json
import os

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_UPDATE_FILE = 'last_run.json' # Файл для контроля времени
UPDATE_INTERVAL_HOURS = 6

st.set_page_config(page_title="Мониторинг цен PRO", layout="wide", initial_sidebar_state="collapsed")

# Компактный CSS с фиксацией колонки
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding: 0.5rem 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    table { border-collapse: separate; border-spacing: 0; }
    th, td { padding: 6px 8px !important; border: 1px solid #eee !important; white-space: nowrap; font-size: 0.82em; text-align: center !important; }
    td:first-child, th:first-child {
        position: sticky; left: 0; z-index: 2;
        background-color: #f8f9fa !important;
        border-right: 2px solid #ddd !important;
        text-align: left !important; font-weight: 700; min-width: 120px;
    }
    .uah { color: #1a1a1a; font-weight: 800; display: block; line-height: 1.1; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    </style>
    """, unsafe_allow_html=True)

# --- ЛОГИКА РАБОТЫ С ДАННЫМИ ---
def load_data():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def get_last_run_time():
    if os.path.exists(LAST_UPDATE_FILE):
        with open(LAST_UPDATE_FILE, 'r') as f:
            data = json.load(f)
            return datetime.fromisoformat(data['last_run'])
    return datetime.min

def save_run_time():
    with open(LAST_UPDATE_FILE, 'w') as f:
        json.dump({'last_run': datetime.now().isoformat()}, f)

# Основная функция парсинга (теперь вызывается редко)
def run_full_update():
    history = load_data()
    kiev_tz = pytz.timezone('Europe/Kyiv')
    now_str = datetime.now(kiev_tz).strftime('%d.%m %H:%M')
    
    files = ['links.csv', 'links_new.csv']
    for f_name in files:
        if not os.path.exists(f_name): continue
        df = pd.read_csv(f_name, sep=None, engine='python')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        for _, row in df.iterrows():
            model = str(row.get('модель', '—')).strip()
            shop = str(row.get('магазин', '—')).strip()
            url = str(row.get('ссылка', '')).strip()
            sel = str(row.get('селектор', '')).strip()
            cat = str(row.get('категория', 'Без категории')).strip()
            item_id = f"{model} | {shop}"
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        p_uah = int(re.sub(r'\D', '', el.text.strip()))
                        if item_id not in history: history[item_id] = []
                        last = history[item_id][-1] if history[item_id] else None
                        if not last or last['price'] != p_uah:
                            history[item_id].append({'time': now_str, 'price': p_uah, 'cat': cat})
                except: pass
    
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    save_run_time()

# --- ИНТЕРФЕЙС ---
last_run = get_last_run_time()
next_run = last_run + timedelta(hours=UPDATE_INTERVAL_HOURS)

st.title("📱 Мониторинг цен PRO")

col1, col2, col3 = st.columns([1, 1, 1])
with col1:
    user_rate = st.number_input("Курс $:", value=44.55, step=0.1)
with col2:
    st.write(f"Последнее: {last_run.strftime('%H:%M')}")
    if st.button("♻️ ОБНОВИТЬ СЕЙЧАС", use_container_width=True):
        with st.spinner("Парсим..."):
            run_full_update()
            st.rerun()

# Автоматический запуск (фоновый для пользователя)
if datetime.now() > next_run:
    run_full_update()
    st.rerun()

# Вывод таблицы из готового JSON
hist_data = load_data()
if hist_data:
    tabs = st.tabs(["Used", "New"])
    for i, tab_name in enumerate(["Used", "New"]):
        with tabs[i]:
            # Собираем текущий срез цен из истории
            current_prices = []
            for key, entries in hist_data.items():
                if not entries: continue
                model, shop = key.split(" | ")
                last_entry = entries[-1]
                # Фильтр по вкладкам (упрощенно)
                if (i == 0 and "links.csv" in str(entries)) or (i == 1): # Тут можно добавить точную привязку
                    current_prices.append({
                        'Модель': model, 'Магазин': shop, 
                        'Цена_ГРН': last_entry['price'], 'Категория': last_entry.get('cat', '—')
                    })
            
            df_display = pd.DataFrame(current_prices)
            if not df_display.empty:
                cat_list = df_display['Категория'].unique()
                sel_cat = st.selectbox(f"Категория:", cat_list, key=f"cat_{i}")
                
                f_df = df_display[df_display['Категория'] == sel_cat]
                
                def fmt(v):
                    return f'<span class="uah">{int(v):,} ₴</span><span class="usd">{int(round(v/user_rate)):,} $</span>'

                f_df['Цена'] = f_df['Цена_ГРН'].apply(fmt)
                pivot = f_df.pivot(index='Модель', columns='Магазин', values='Цена').fillna('—')
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
