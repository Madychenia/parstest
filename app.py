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

def get_minfin_rate():
    try:
        url = "https://minfin.com.ua/currency/auction/usd/buy/kiev/"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        rate_el = soup.select_one('.sc-1x32wa2-9') 
        if rate_el:
            val = re.sub(r'[^\d.]', '', rate_el.text.replace(',', '.'))
            return float(val)
    except: pass
    return 44.15

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
    
    # Сначала считаем общее кол-во задач для прогресс-бара
    all_tasks = []
    current_keys = set()
    for f_name, tag in mapping.items():
        if os.path.exists(f_name):
            df = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
            df.columns = [c.strip().lower() for c in df.columns]
            for idx, row in df.iterrows():
                all_tasks.append((row, tag, idx))
                current_keys.add(f"{str(row.get('модель','')).strip()} | {str(row.get('магазин','')).strip()} | {tag}")

    if not all_tasks: return

    # Создаем прогресс-бар в интерфейсе
    progress_bar = st.progress(0)
    status_text = st.empty()
    total = len(all_tasks)

    for i, (row, tag, idx) in enumerate(all_tasks):
        m, s, u, sel, c = [str(row.get(k, '')).strip() for k in ['модель','магазин','ссылка','селектор','категория']]
        status_text.text(f"Обновление: {m} ({s})")
        
        if u.startswith('http') and sel and sel != 'nan':
            key = f"{m} | {s} | {tag}"
            try:
                r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                soup = BeautifulSoup(r.text, 'html.parser')
                el = soup.select_one(sel)
                if el:
                    price_val = clean_price(el.text)
                    if price_val:
                        if key not in history: history[key] = []
                        if not history[key] or history[key][-1]['price'] != price_val:
                            history[key].append({'time': now, 'price': price_val, 'cat': c, 'type': tag, 'order': idx})
                            if len(history[key]) > 50: history[key] = history[key][-50:]
            except: pass
        
        # Обновляем полоску
        progress_bar.progress((i + 1) / total)
    
    # Очистка мусора
    history = {k: v for k, v in history.items() if k in current_keys}
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': now})
    status_text.empty()
    progress_bar.empty()

if "--parse" in sys.argv:
    # Для фонового запуска прогресс-бар не нужен
    run_parsing()
    sys.exit(0)

st.set_page_config(page_title="Мониторинг", layout="wide")

st.markdown("""<style>
    .block-container { padding: 1rem !important; max-width: 1000px !important; margin: 0 auto !important; }
    .table-container { overflow-x: auto; width: 100%; text-align: center; margin-bottom: 20px; }
    table { margin: 0 auto; border-collapse: collapse; width: auto !important; }
    th, td { padding: 4px 10px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    tbody tr th { background-color: #f8f9fa !important; font-weight: bold; text-align: left !important; border-right: 2px solid #ddd !important; }
    thead tr:nth-child(2) { display: none; }
    thead tr:first-child th:first-child { background-color: #f8f9fa !important; color: transparent !important; }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    .log-line { font-family: monospace; font-size: 0.95em; margin: 2px 0; }
    .log-usd { color: #FF4B4B; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = get_minfin_rate()
db = load_data(HISTORY_FILE)
last_run = load_data(LAST_RUN_FILE)

c1, c2, c3, c4 = st.columns([1,1.5,1,1])
with c1: user_rate = st.number_input("", value=44.55, label_visibility="collapsed") 
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.write(f"Минфин: **{minfin_rate}**")
with c3: 
    if st.button("♻️ ОБНОВИТЬ"): 
        run_parsing()
        st.rerun()
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
            cats = sorted(df_tab['Категория'].unique())
            sel_cat = st.selectbox("Категория:", cats, key=f"cat_{tag_key}")
            f_df = df_tab[df_tab['Категория'] == sel_cat].copy().sort_values('order')
            
            if not f_df.empty:
                f_df['Display'] = f_df['Цена'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=False).fillna('—')
                pivot.index.name = None; pivot.columns.name = None
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)

                st.markdown("---")
                with st.expander("Отслеживание цены"):
                    hc1, hc2, hc3 = st.columns(3)
                    with hc1: h_cat = st.selectbox("Категория", cats, key=f"hc_{tag_key}")
                    h_mod_df = df_tab[df_tab['Категория'] == h_cat].sort_values('order')
                    h_mod_list = h_mod_df['M'].unique()
                    with hc2: h_mod = st.selectbox("Модель", h_mod_list, key=f"hm_{tag_key}")
                    with hc3:
                        h_shop_list = sorted(df_tab[(df_tab['Категория'] == h_cat) & (df_tab['M'] == h_mod)]['S'].unique())
                        h_shop = st.selectbox("Продавец", h_shop_list, key=f"hs_{tag_key}")
                    
                    hist_key = f"{h_mod} | {h_shop} | {tag_key}"
                    if hist_key in db:
                        logs = db[hist_key]
                        for j in range(len(logs)-1, -1, -1):
                            entry = logs[j]
                            usd_min = int(entry['price'] / minfin_rate)
                            diff_str = ""
                            if j > 0:
                                old_p, new_p = logs[j-1]['price'], entry['price']
                                diff = ((new_p - old_p) / old_p) * 100
                                if diff != 0:
                                    color = "red" if diff > 0 else "green"
                                    diff_str = f' <span style="color:{color}; font-size:0.85em;">({"+" if diff>0 else ""}{diff:.1f}%)</span>'
                            st.markdown(f'<div class="log-line">└ {entry["time"]}: {entry["price"]:,} ₴ (<span class="log-usd">{usd_min:,} $</span>){diff_str}</div>', unsafe_allow_html=True)
