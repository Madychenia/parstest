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

# ВОЗВРАЩАЕМ СТИЛИ: Красный доллар и чистая таблица
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
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
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
            m = str(row.get('модель','')).strip()
            s = str(row.get('магазин','')).strip()
            u = str(row.get('ссылка','')).strip()
            sel = str(row.get('селектор','')).strip()
            c = str(row.get('категория','')).strip()
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
st.title("📱 Мониторинг") # ВЕРНУЛ ЗАГОЛОВОК

minfin_rate = 44.15 
db = load_data(HISTORY_FILE)
last_run = load_data(LAST_RUN_FILE)

c1, c2, c3 = st.columns(3)
with c1: user_rate = st.number_input("Курс $:", value=44.55)
with c2: st.write(f"Обновлено: **{last_run.get('time', '—')}**")
with c3: 
    if st.button("♻️ ОБНОВИТЬ ВСЁ"): 
        run_parsing()
        st.rerun()

tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
tags = ['u', 'n']

for i, t_tag in enumerate(tags):
    with tabs[i]:
        items = []
        for k, logs in db.items():
            if logs and logs[-1].get('type') == t_tag:
                p = k.split(" | ")
                items.append({'M': p[0], 'S': p[1], 'P': logs[-1]['price'], 'C': logs[-1]['cat']})
        
        df = pd.DataFrame(items)
        if not df.empty:
            cats = sorted(df['C'].unique())
            sel_cat = st.selectbox("Категория:", cats, key=f"s_{t_tag}")
            
            f_df = df[df['C'] == sel_cat].copy()
            if not f_df.empty:
                f_df['Display'] = f_df['P'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first').fillna('—')
                pivot.index.name = None
                pivot.columns.name = None
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)

# ИСТОРИЯ ИЗМЕНЕНИЙ (ВЕРНУЛ ТРОЙНОЙ ФИЛЬТР)
st.markdown("---")
st.subheader("📜 История изменений")
if db:
    all_rows = []
    for k, logs in db.items():
        if logs:
            p = k.split(" | ")
            all_rows.append({'M': p[0], 'S': p[1], 'C': logs[-1]['cat']})
    
    h_df = pd.DataFrame(all_rows)
    f1, f2, f3 = st.columns(3)
    with f1: h_cat = st.selectbox("1. Категория", sorted(h_df['C'].unique()), key="h_cat")
    with f2: h_mod = st.selectbox("2. Модель", sorted(h_df[h_df['C'] == h_cat]['M'].unique()), key="h_mod")
    with f3: h_shop = st.selectbox("3. Поставщик", sorted(h_df[(h_df['C'] == h_cat) & (h_df['M'] == h_mod)]['S'].unique()), key="h_shop")
    
    h_key = f"{h_mod} | {h_shop}"
    if h_key in db:
        for e in reversed(db[h_key]):
            st.markdown(f"{e['time']} — **{e['price']:,} ₴** <span class='log-usd'>({int(e['price']/minfin_rate)} $)</span>", unsafe_allow_html=True)
