import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг цен", layout="wide")

# Чистый интерфейс
st.markdown("""
    <style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; }
    th, td { padding: 10px !important; border: 1px solid #eee !important; text-align: center !important; }
    td:first-child, th:first-child { position: sticky; left: 0; background: #f8f9fa; z-index: 2; font-weight: bold; }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    </style>
    """, unsafe_allow_html=True)

def load_data(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def send_tg(msg):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                       data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

def run_parsing():
    history = load_data(HISTORY_FILE)
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    files = {'links.csv': 'u', 'links_new.csv': 'n'}
    
    for f_name, tag in files.items():
        if not os.path.exists(f_name): continue
        df = pd.read_csv(f_name, sep=None, engine='python')
        df.columns = [c.strip().lower() for c in df.columns]
        
        for _, row in df.iterrows():
            model, shop, url, sel = str(row.get('модель', '')), str(row.get('магазин', '')), str(row.get('ссылка', '')), str(row.get('селектор', ''))
            cat = str(row.get('категория', '1'))
            key = f"{model} | {shop}"
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        price = int(re.sub(r'\D', '', el.text.strip()))
                        if key not in history: history[key] = []
                        last = history[key][-1] if history[key] else None
                        
                        if not last or last['price'] != price:
                            if last: send_tg(f"🔔 <b>{model}</b>\n{shop}: <b>{price:,} ₴</b>")
                            history[key].append({'time': now, 'price': price, 'cat': cat, 'type': tag})
                        else:
                            history[key][-1].update({'cat': cat, 'type': tag})
                except: continue
    
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': datetime.now(KIEV_TZ).strftime('%d.%m %H:%M:%S')})

# --- UI ---
st.title("📱 Мониторинг")

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    rate = st.number_input("$:", value=44.55, label_visibility="collapsed")
with c2:
    last_t = load_data(LAST_RUN_FILE).get('time', 'Никогда')
    st.write(f"Обновлено: **{last_t}**")
with c3:
    if st.button("🔔 ТЕСТ"): send_tg("✅ Тест связи")

hist_db = load_data(HISTORY_FILE)

if hist_db:
    t1, t2 = st.tabs(["Used (Б/У)", "New (Новые)"])
    for i, tag in enumerate(['u', 'n']):
        with [t1, t2][i]:
            items = []
            for k, v in hist_db.items():
                if v and v[-1].get('type') == tag:
                    m, s = k.split(" | ")
                    items.append({'Модель': m, 'Магазин': s, 'Цена_ГРН': v[-1]['price'], 'Кат': v[-1].get('cat', '1')})
            
            if items:
                df = pd.DataFrame(items)
                cat_list = sorted(df['Кат'].unique())
                sel_cat = st.selectbox("Категория:", cat_list, key=f"s_{tag}")
                
                f_df = df[df['Кат'] == sel_cat]
                f_df['Цена'] = f_df['Цена_ГРН'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/rate):,} $</span>')
                
                pivot = f_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first').fillna('—')
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
else:
    if st.button("🚀 ЗАПУСТИТЬ ПЕРВЫЙ ПАРСИНГ"):
        run_parsing()
        st.rerun()

with st.expander("📜 Логи"):
    if hist_db:
        sk = st.selectbox("Девайс:", sorted(hist_db.keys()))
        for e in reversed(hist_db[sk]): st.write(f"{e['time']} — {e['price']:,} ₴")
