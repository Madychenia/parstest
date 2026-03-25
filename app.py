import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os
import io

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг", layout="wide")

# Убираем лишние заголовки
st.markdown("""
    <style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    th, td { padding: 8px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    .blank, .index_name { display: none !important; }
    td:first-child, th:first-child { 
        position: sticky; left: 0; background: #f8f9fa; z-index: 2; 
        font-weight: bold; border-right: 2px solid #ddd !important; 
    }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    .log-usd { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

def load_data(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def clean_price(text):
    res = re.sub(r'[^\d]', '', text)
    return int(res) if res else None

def run_parsing():
    history = load_data(HISTORY_FILE)
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    mapping = {'links.csv': 'u', 'links_new.csv': 'n'}
    
    for f_name, tag in mapping.items():
        if not os.path.exists(f_name): continue
        df = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
        df.columns = [c.strip().lower() for c in df.columns]
        for _, row in df.iterrows():
            m, s, u, sel, c = str(row.get('модель','')).strip(), str(row.get('магазин','')).strip(), str(row.get('ссылка','')).strip(), str(row.get('селектор','')).strip(), str(row.get('категория','')).strip()
            if u.startswith('http'):
                try:
                    r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    p = clean_price(soup.select_one(sel).text)
                    if p:
                        key = f"{m} | {s}"
                        if key not in history: history[key] = []
                        history[key].append({'time': now, 'price': p, 'cat': c, 'type': tag})
                except: pass
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': now})

# --- ИНТЕРФЕЙС ---
minfin_rate = 44.15 #
db = load_data(HISTORY_FILE)
last_run = load_data(LAST_RUN_FILE)

c1, c2, c3 = st.columns(3)
with c1: user_rate = st.number_input("Курс $:", value=44.55)
with c2: st.write(f"Обновлено: {last_run.get('time', '—')}")
with c3: 
    if st.button("♻️ ОБНОВИТЬ"): 
        run_parsing()
        st.rerun()

tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
tags = ['u', 'n']

for i, t_tag in enumerate(tags):
    with tabs[i]:
        rows = []
        for k, logs in db.items():
            if logs and logs[-1].get('type') == t_tag:
                p = k.split(" | ")
                rows.append({'Модель': p[0], 'Магазин': p[1], 'Цена': logs[-1]['price'], 'Кат': logs[-1]['cat']})
        
        df = pd.DataFrame(rows)
        if not df.empty:
            cats = sorted(df['Кат'].unique())
            sel_cat = st.selectbox("Категория:", cats, key=f"s_{t_tag}")
            
            f_df = df[df['Кат'] == sel_cat].copy()
            if not f_df.empty:
                f_df['Display'] = f_df['Цена'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='Модель', columns='Магазин', values='Display', aggfunc='first').fillna('—')
                pivot.index.name = None
                pivot.columns.name = None
                st.markdown(pivot.to_html(escape=False), unsafe_allow_html=True)
                
                # ИСТОРИЯ ИЗМЕНЕНИЙ ВНИЗУ
                st.markdown("---")
                st.subheader("📜 История цен")
                f1, f2 = st.columns(2)
                with f1: h_mod = st.selectbox("Модель", sorted(f_df['Модель'].unique()), key=f"m_{t_tag}")
                with f2: h_shop = st.selectbox("Магазин", sorted(f_df[f_df['Модель'] == h_mod]['Магазин'].unique()), key=f"sh_{t_tag}")
                
                h_key = f"{h_mod} | {h_shop}"
                if h_key in db:
                    for e in reversed(db[h_key]):
                        st.write(f"{e['time']} — **{e['price']:,} ₴** ({int(e['price']/minfin_rate)} $)")
