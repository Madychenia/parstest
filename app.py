import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'

st.set_page_config(page_title="Мониторинг цен PRO", layout="wide", initial_sidebar_state="collapsed")

# CSS с фиксацией первой колонки (Sticky Column)
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .block-container { padding: 1rem !important; }
    
    /* Контейнер для скролла */
    .table-container { 
        overflow-x: auto; 
        width: 100%; 
        border: 1px solid #eee;
    }
    
    table { 
        border-collapse: separate; 
        border-spacing: 0; 
        width: auto !important; 
    }
    
    th, td { 
        padding: 6px 8px !important; 
        border: 1px solid #eee !important; 
        white-space: nowrap; 
        font-size: 0.82em;
        text-align: center !important;
    }

    /* ФИКСАЦИЯ ПЕРВОЙ КОЛОНКИ */
    td:first-child, th:first-child {
        position: -webkit-sticky;
        position: sticky;
        left: 0;
        z-index: 2;
        background-color: #f8f9fa !important;
        border-right: 2px solid #ddd !important;
        text-align: left !important;
        font-weight: 700;
        min-width: 120px;
    }
    
    /* Чтобы шапка не перекрывала фиксированную колонку */
    th:first-child { z-index: 3; }

    .uah { color: #1a1a1a; font-weight: 800; display: block; line-height: 1.1; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    
    /* Убираем лишние элементы Streamlit для компактности */
    div[data-testid="stNumberInput"] label { display: none; }
    button { padding: 5px !important; height: 35px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен")

# --- ФУНКЦИИ БАЗЫ ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=5)
    except: pass

# --- ИНТЕРФЕЙС ---
col_rate, col_btn, col_test = st.columns([0.8, 1, 1])
with col_rate:
    user_rate = st.number_input("r", value=44.55, step=0.01, label_visibility="collapsed")
with col_btn:
    if st.button("♻️ ОБНОВИТЬ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_test:
    if st.button("🔔 ТЕСТ", use_container_width=True):
        send_telegram("✅ Бот онлайн")
        st.toast("Ок")

@st.cache_data(ttl=3600)
def fetch_and_track(file_name):
    history = load_history()
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        kiev_tz = pytz.timezone('Europe/Kyiv')
        now_str = datetime.now(kiev_tz).strftime('%d.%m %H:%M')
        
        for _, row in df.iterrows():
            p_uah = None
            model, shop = str(row.get('модель', '—')).strip(), str(row.get('магазин', '—')).strip()
            cat = str(row.get('категория', 'Без категории')).strip()
            item_id = f"{model} | {shop}"
            url, sel = str(row.get('ссылка', '')).strip(), str(row.get('селектор', '')).strip()
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        digits = re.sub(r'\D', '', el.text.strip())
                        if digits: p_uah = int(digits)
                except: pass

            if item_id not in history: history[item_id] = []
            if p_uah:
                last = history[item_id][-1] if history[item_id] else None
                if not last or last['price'] != p_uah:
                    if last: send_telegram(f"🔔 <b>{model}</b>\n🏪 {shop}: <b>{p_uah:,} ₴</b>")
                    history[item_id].append({'time': now_str, 'price': p_uah, 'cat': cat})
                else: last['cat'] = cat
            results.append({'Модель': model, 'Магазин': shop, 'Цена_ГРН': p_uah, 'Категория': cat})
            
        save_history(history)
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- ВЫВОД ---
tabs = st.tabs(["Used", "New"])
csv_files = ['links.csv', 'links_new.csv']

for i, tab in enumerate(tabs):
    with tab:
        data = fetch_and_track(csv_files[i])
        if not data.empty:
            sel_cat = st.selectbox("C", data['Категория'].unique(), key=f"c_{i}", label_visibility="collapsed")
            f_df = data[data['Категория'] == sel_cat]
            
            def cell_fmt(v):
                if pd.notnull(v) and v > 0:
                    return f'<span class="uah">{int(v):,} ₴</span><span class="usd">{int(round(v/user_rate)):,} $</span>'
                return '<span style="color:#ccc">—</span>'

            disp = f_df.copy()
            disp['Цена'] = disp['Цена_ГРН'].apply(cell_fmt)
            pivot = disp.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
                index='Модель', columns='Магазин', values='Цена'
            ).fillna('<span style="color:#ccc">—</span>').reindex(f_df['Модель'].unique())
            
            # Оборачиваем в контейнер для скролла с фиксацией
            st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
        else:
            st.info("Пусто")
