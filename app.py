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

# Компактный CSS с поддержкой прокрутки
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: #1a1a1a; font-weight: 800; font-size: 0.95em; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.85em; }
    
    /* Контейнер для прокрутки на мобилках */
    .table-container { overflow-x: auto; width: 100%; }
    
    table { width: auto !important; min-width: 400px; border-collapse: collapse; border: 1px solid #eee !important; margin-bottom: 20px; }
    th { background-color: #f8f9fb !important; padding: 8px !important; border: 1px solid #eee !important; font-size: 0.85em; }
    td { padding: 6px 10px !important; border: 1px solid #eee !important; height: auto !important; vertical-align: middle !important; text-align: center !important; }
    
    /* Первая колонка - Название модели */
    td:first-child { text-align: left !important; font-weight: 700; background-color: #fafafa; min-width: 140px; white-space: nowrap; }
    
    /* Убираем лишние отступы Streamlit */
    .block-container { padding-top: 2rem !important; }
    div[data-testid="stNumberInput"] label { display: none; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен PRO")

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

# --- КОМПАКТНАЯ ПАНЕЛЬ ---
col_rate, col_btn, col_test = st.columns([1, 1.5, 1.5])
with col_rate:
    # Убрали надпись, оставили только ввод числа
    user_rate = st.number_input("rate", value=44.55, step=0.01, label_visibility="collapsed")
with col_btn:
    if st.button("♻️ ОБНОВИТЬ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_test:
    if st.button("🔔 ТЕСТ ТГ", use_container_width=True):
        send_telegram("✅ Связь в норме!")
        st.toast("Тест отправлен")

# --- ЛОГИКА ---
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
            model = str(row.get('модель', '—')).strip()
            shop = str(row.get('магазин', '—')).strip()
            cat = str(row.get('категория', 'Без категории')).strip()
            item_id = f"{model} | {shop}"
            
            url = str(row.get('ссылка', '')).strip()
            sel = str(row.get('селектор', '')).strip()
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
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
                    if last:
                        diff = p_uah - last['price']
                        msg = f"🔔 <b>{model}</b>\n🏪 {shop}\n💰 <b>{p_uah:,} ₴</b>"
                        send_telegram(msg)
                    history[item_id].append({'time': now_str, 'price': p_uah, 'cat': cat})
                else:
                    last['cat'] = cat
            
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
            all_cats = data['Категория'].unique().tolist()
            sel_cat = st.selectbox("Категория:", all_cats, key=f"s_{i}", label_visibility="collapsed")
            
            f_df = data[data['Категория'] == sel_cat]
            mod_order = f_df['Модель'].unique().tolist()
            
            def cell_fmt(v):
                if pd.notnull(v) and v > 0:
                    return f'<span class="uah">{int(v):,} ₴</span><span class="usd">{int(round(v/user_rate)):,} $</span>'
                return '<span style="color:#ccc">—</span>'

            disp = f_df.copy()
            disp['Цена'] = disp['Цена_ГРН'].apply(cell_fmt)
            
            pivot = disp.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
                index='Модель', columns='Магазин', values='Цена'
            ).fillna('<span style="color:#ccc">—</span>').reindex(mod_order)
            
            # Оборачиваем таблицу в div для прокрутки
            st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
            
            # --- ИСТОРИЯ ---
            with st.expander("📜 История (выбрать)"):
                h_db = load_history()
                h_c1, h_c2 = st.columns(2)
                with h_c1:
                    h_mod = st.selectbox("Модель:", sorted(f_df['Модель'].unique().tolist()), key=f"hm_{i}")
                with h_c2:
                    h_shop = st.selectbox("Магазин:", sorted(f_df[f_df['Модель'] == h_mod]['Магазин'].unique().tolist()), key=f"hs_{i}")
                
                target = f"{h_mod} | {h_shop}"
                if target in h_db:
                    for log in reversed(h_db[target]):
                        st.write(f"📅 {log['time']} — **{log['price']:,} ₴**")
        else:
            st.info("Нет данных")
