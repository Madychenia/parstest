import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os
import sys

# --- КОНФИГ ---
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

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
        if os.path.exists(f_name):
            try:
                df = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
                df.columns = [c.strip().lower() for c in df.columns]
                for idx, row in df.iterrows():
                    m, s, u, sel, c = [str(row.get(k, '')).strip() for k in ['модель','магазин','ссылка','селектор','категория']]
                    if u.startswith('http') and sel and sel != 'nan':
                        try:
                            r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                            soup = BeautifulSoup(r.text, 'html.parser')
                            el = soup.select_one(sel)
                            if el:
                                price_val = clean_price(el.text)
                                if price_val:
                                    key = f"{m} | {s} | {tag}"
                                    if key not in history: history[key] = []
                                    history[key].append({'time': now, 'price': price_val, 'cat': c, 'type': tag, 'order': idx})
                                    if len(history[key]) > 50: history[key] = history[key][-50:]
                        except: pass
            except: pass
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': now})

if "--parse" in sys.argv:
    run_parsing()
    sys.exit(0)

st.set_page_config(page_title="Мониторинг", layout="wide")

# CSS: Убираем всё лишнее
st.markdown("""<style>
    .block-container { padding: 1rem !important; max-width: 1000px !important; margin: 0 auto !important; }
    .table-container { overflow-x: auto; width: 100%; text-align: center; margin-bottom: 20px; }
    table { margin: 0 auto; border-collapse: collapse; width: auto !important; }
    th, td { padding: 4px 10px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    tbody tr th { background-color: #f8f9fa !important; font-weight: bold; text-align: left !important; border-right: 2px solid #ddd !important; }
    thead tr:nth-child(2) { display: none; }
    thead tr:first-child th:first-child { background-color: #f8f9fa !important; color: transparent !important; border: 1px solid #eee !important; }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    .log-line { font-family: monospace; font-size: 0.95em; margin: 2px 0; }
    .log-usd { color: #FF4B4B; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = 44.15 
db = load_data(HISTORY_FILE)
last_run = load_data(LAST_RUN_FILE)

c1, c2, c3, c4 = st.columns([1,1.5,1,1])
with c1: 
    # ЧИСТОЕ ПОЛЕ БЕЗ ТЕКСТА
    user_rate = st.number_input("", value=44.55, label_visibility="collapsed") 
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.write(f"Минфин: **{minfin_rate}**")
with c3: 
    if st.button("♻️ ОБНОВИТЬ"): run_parsing(); st.rerun()
with c4:
    if st.button("🗑 СБРОСИТЬ"):
        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
        st.rerun()

tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
tags = ['u', 'n']

for i, tab_ui in enumerate(tabs):
    tag_key = tags[i]
    with tab_ui:
        items = []
        for k, logs in db.items():
            if logs and logs[-1].get('type') == tag_key:
                p = k.split(" | ")
                items.append({'M': p[0], 'S': p[1], 'Цена': logs[-1]['price'], 'Категория': logs[-1]['cat'], 'order': logs[-1].get('order', 999)})
        
        if items:
            df_tab = pd.DataFrame(items)
            sel_cat = st.selectbox("Категория:", sorted(df_tab['Категория'].unique()), key=f"cat_{tag_key}")
            f_df = df_tab[df_tab['Категория'] == sel_cat].copy().sort_values('order')
            
            if not f_df.empty:
                f_df['Display'] = f_df['Цена'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=False).fillna('—')
                pivot.index.name = None; pivot.columns.name = None
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)

                # ИСТОРИЯ ЦЕН В ВЫПАДАЮЩЕМ МЕНЮ
                with st.expander("Отслеживание цены"):
                    h_cat = st.selectbox("Выбор категории:", sorted(df_tab['Категория'].unique()), key=f"hc_{tag_key}")
                    h_mod_list = sorted(df_tab[df_tab['Категория'] == h_cat]['M'].unique())
                    h_mod = st.selectbox("Выбор модели:", h_mod_list, key=f"hm_{tag_key}")
                    h_shop_list = sorted(df_tab[(df_tab['Категория'] == h_cat) & (df_tab['M'] == h_mod)]['S'].unique())
                    h_shop = st.selectbox("Выбор продавца:", h_shop_list, key=f"hs_{tag_key}")
                    
                    hist_key = f"{h_mod} | {h_shop} | {tag_key}"
                    if hist_key in db:
                        for entry in reversed(db[hist_key]):
                            usd_val = int(entry['price'] / user_rate)
                            st.markdown(f'<div class="log-line">└ {entry["time"]}: {entry["price"]:,} ₴ (<span class="log-usd">{usd_val:,} $</span>)</div>', unsafe_allow_html=True)
