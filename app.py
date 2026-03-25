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
import sys

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг", layout="wide")

# Стили для чистой таблицы (убираем Модель/Магазин)
st.markdown("""
    <style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    th, td { padding: 8px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    /* Скрываем пустые ячейки заголовков */
    thead tr:first-child th { display: none !important; }
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

def load_json(file):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return {}

def save_json(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def clean_p(text):
    res = re.sub(r'[^\d]', '', text)
    return int(res) if res else None

def run_parsing():
    db = load_json(HISTORY_FILE)
    errs = []
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    
    for f_name, tag in [('links.csv', 'u'), ('links_new.csv', 'n')]:
        if not os.path.exists(f_name): continue
        df = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
        df.columns = [c.strip().lower() for c in df.columns]
        
        for _, r in df.iterrows():
            m, s, u, sel, c = str(r.get('модель','')).strip(), str(r.get('магазин','')).strip(), str(r.get('ссылка','')).strip(), str(r.get('селектор','')).strip(), str(r.get('категория','')).strip()
            if not u.startswith('http'): continue
            try:
                res = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                soup = BeautifulSoup(res.text, 'html.parser')
                val = clean_p(soup.select_one(sel).text)
                if val:
                    key = f"{m} | {s}"
                    if key not in db: db[key] = []
                    db[key].append({'time': now, 'price': val, 'cat': c, 'type': tag})
            except Exception as e:
                errs.append(f"{m}: {str(e)[:30]}")
    
    save_json(HISTORY_FILE, db)
    save_json(LAST_RUN_FILE, {'time': now, 'errors': errs})

# --- UI ---
minfin = 44.15 #
last = load_json(LAST_RUN_FILE)
db = load_json(HISTORY_FILE)

c1, c2, c3 = st.columns(3)
with c1: cur = st.number_input("Курс:", value=44.55)
with c2: st.write(f"Обновлено: {last.get('time', '—')}")
with c3: 
    if st.button("♻️ ОБНОВИТЬ"): 
        run_parsing()
        st.rerun()

tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
for i, tag in enumerate(['u', 'n']):
    with tabs[i]:
        items = []
        for k, logs in db.items():
            if logs and logs[-1]['type'] == tag:
                m_s = k.split(" | ")
                items.append({'M': m_s[0], 'S': m_s[1], 'P': logs[-1]['price'], 'C': logs[-1]['cat']})
        
        df = pd.DataFrame(items)
        if not df.empty:
            cats = sorted(df['C'].unique())
            sel_c = st.selectbox("Категория", cats, key=f"v_{tag}")
            
            view = df[df['C'] == sel_c].copy()
            if not view.empty:
                view['Val'] = view['P'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/cur):,} $</span>')
                # Формируем таблицу без лишних имен осей
                piv = view.pivot_table(index='M', columns='S', values='Val', aggfunc='first').fillna('—')
                piv.index.name = None
                piv.columns.name = None
                st.markdown(piv.to_html(escape=False), unsafe_allow_html=True)

with st.expander("Отладка (ключи)"):
    st.write(list(db.keys()))
