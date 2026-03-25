import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import pytz
import json
import os

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг цен PRO", layout="wide")

# CSS для мобильных (фиксация первой колонки)
st.markdown("""
    <style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    th, td { padding: 8px !important; border: 1px solid #eee !important; white-space: nowrap; font-size: 0.85em; text-align: center !important; }
    td:first-child, th:first-child {
        position: sticky; left: 0; z-index: 2;
        background-color: #f8f9fa !important;
        border-right: 2px solid #ddd !important;
        text-align: left !important; font-weight: bold;
    }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    </style>
    """, unsafe_allow_html=True)

# --- ФУНКЦИИ ХРАНЕНИЯ ---
def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_history(data):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_last_run():
    if os.path.exists(LAST_RUN_FILE):
        with open(LAST_RUN_FILE, 'r') as f: return json.load(f).get('time', 'Никогда')
    return "Никогда"

def update_last_run():
    now_kiev = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M:%S')
    with open(LAST_RUN_FILE, 'w') as f: json.dump({'time': now_kiev}, f)

def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

# --- ПАРСЕР (ФОНОВЫЙ) ---
def run_parsing():
    history = load_history()
    now_kiev = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    
    for f_name in ['links.csv', 'links_new.csv']:
        if not os.path.exists(f_name): continue
        df = pd.read_csv(f_name, sep=None, engine='python')
        df.columns = [c.strip().lower() for c in df.columns]
        
        for _, row in df.iterrows():
            model, shop = str(row.get('модель', '')), str(row.get('магазин', ''))
            url, sel = str(row.get('ссылка', '')), str(row.get('селектор', ''))
            cat = str(row.get('категория', 'Без категории'))
            key = f"{model} | {shop}"
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=7)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        price = int(re.sub(r'\D', '', el.text.strip()))
                        if key not in history: history[key] = []
                        
                        last = history[key][-1] if history[key] else None
                        if not last or last['price'] != price:
                            if last: send_tg(f"🔔 <b>{model}</b>\n{shop}: <b>{price:,} ₴</b>")
                            history[key].append({'time': now_kiev, 'price': price, 'cat': cat})
                        else:
                            # Обновляем категорию, если она изменилась в CSV
                            history[key][-1]['cat'] = cat
                except: pass
    
    save_history(history)
    update_last_run()

# --- ИНТЕРФЕЙС ---
st.title("📱 Мониторинг цен PRO")

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    rate = st.number_input("Курс $:", value=44.55, step=0.01)
with c2:
    st.write(f"Обновлено: **{get_last_run()}**")
    if st.button("♻️ ОБНОВИТЬ ВСЁ", use_container_width=True):
        with st.spinner("Парсим..."):
            run_parsing()
            st.rerun()
with c3:
    if st.button("🔔 ТЕСТ ТГ", use_container_width=True):
        send_tg("✅ Связь с ботом установлена!")
        st.toast("Отправлено")

# ОСНОВНОЙ ВЫВОД
hist_db = load_history()

if hist_db:
    t1, t2 = st.tabs(["Used (Б/У)", "New (Новые)"])
    
    # Собираем данные для таблиц
    for i, tab in enumerate([t1, t2]):
        with tab:
            items = []
            for key, logs in hist_db.items():
                if not logs: continue
                last = logs[-1]
                mod, shp = key.split(" | ")
                # Фильтр по файлам: упрощенно, если в links.csv - Used, в links_new - New
                # Для точности используем категории из логов
                items.append({
                    'Модель': mod, 'Магазин': shp, 
                    'Цена_ГРН': last['price'], 'Категория': last.get('cat', 'Без категории')
                })
            
            df = pd.DataFrame(items)
            if not df.empty:
                # Фильтр категорий
                cats = sorted(df['Категория'].unique())
                sel_cat = st.selectbox("Категория:", cats, key=f"sel_{i}")
                
                f_df = df[df['Категория'] == sel_cat]
                
                def make_cell(v):
                    return f'<span class="uah">{int(v):,} ₴</span><span class="usd">{int(round(v/rate)):,} $</span>'

                f_df['Цена'] = f_df['Цена_ГРН'].apply(make_cell)
                pivot = f_df.pivot(index='Model', columns='Shop', values='Price') # Исправлено на правильные ключи
                # Но лучше использовать безопасный pivot:
                pivot = f_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first').fillna('—')
                
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)

    # --- ИСТОРИЯ ЦЕН ВНИЗУ ---
    st.markdown("---")
    with st.expander("📜 История изменений (Логи)"):
        all_keys = sorted(hist_db.keys())
        sel_key = st.selectbox("Выберите устройство:", all_keys)
        if sel_key in hist_db:
            for e in reversed(hist_db[sel_key]):
                st.write(f"📅 {e['time']} — **{e['price']:,} ₴**")
else:
    st.warning("База данных пуста. Нажми 'ОБНОВИТЬ ВСЁ', чтобы собрать цены в первый раз.")
