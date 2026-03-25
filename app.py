import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os
import time
import sys

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
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

def send_telegram(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
    except: pass

def clean_price(text):
    res = re.sub(r'[^\d]', '', text)
    return int(res) if res else None

def run_parsing(is_silent=False):
    history = load_data(HISTORY_FILE)
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    mapping = {'links.csv': 'u', 'links_new.csv': 'n'}
    
    tasks = []
    for f_name, tag in mapping.items():
        if os.path.exists(f_name):
            try:
                tdf = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
                tasks.append((f_name, tag, tdf))
            except: pass

    if not tasks: return

    # Прогресс-бар только если запуск из интерфейса
    if not is_silent:
        progress_bar = st.progress(0)
        status_text = st.empty()
    
    total_steps = sum(len(t[2]) for t in tasks)
    current_step = 0

    for f_name, tag, df in tasks:
        df.columns = [c.strip().lower() for c in df.columns]
        for idx, row in df.iterrows():
            current_step += 1
            m, s, u, sel, c = [str(row.get(k, '')).strip() for k in ['модель','магазин','ссылка','селектор','категория']]
            
            if not is_silent:
                status_text.text(f"⏳ Проверяю: {m}")
                progress_bar.progress(current_step / total_steps)

            if u.startswith('http') and sel and sel != 'nan':
                try:
                    r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        price_val = clean_price(el.text)
                        if price_val:
                            key = f"{m} | {s} | {tag}"
                            
                            # УМНАЯ ЗАПИСЬ: Сохраняем только если цена изменилась
                            last_entry = history.get(key, [])[-1] if key in history and history[key] else None
                            
                            if not last_entry or last_entry['price'] != price_val:
                                if last_entry:
                                    diff = price_val - last_entry['price']
                                    send_telegram(f"{'📈' if diff > 0 else '📉'} *Изменение цены!*\n\n*{m}* ({s})\nБыло: {last_entry['price']:,} ₴\nСтало: {price_val:,} ₴\nРазница: {diff:+,} ₴")
                                
                                if key not in history: history[key] = []
                                history[key].append({'time': now, 'price': price_val, 'cat': c, 'type': tag, 'order': idx})
                                # Лимит истории - 50 записей на модель
                                if len(history[key]) > 50: history[key] = history[key][-50:]
                except: pass
    
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': now})
    if not is_silent:
        status_text.success(f"✅ Готово: {now}")
        time.sleep(1)
        status_text.empty()
        progress_bar.empty()

# --- ЛОГИКА ЗАПУСКА ИЗ GITHUB ---
if "--parse" in sys.argv:
    run_parsing(is_silent=True)
    sys.exit(0)

# --- ИНТЕРФЕЙС STREAMLIT ---
st.set_page_config(page_title="Мониторинг", layout="wide")
st.markdown("""<style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    th, td { padding: 8px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    .blank, .index_name { display: none !important; }
    td:first-child, th:first-child { position: sticky; left: 0; background-color: #f8f9fa !important; z-index: 3; font-weight: bold; border-right: 2px solid #ddd !important; }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = 44.15 
db = load_data(HISTORY_FILE)
last_run = load_data(LAST_RUN_FILE)

c1, c2, c3 = st.columns([1,1.5,1])
with c1: user_rate = st.number_input("Курс $:", value=44.55) 
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.caption(f"Курс Минфина (продажа): **{minfin_rate}**") 
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
                items.append({'M': p[0], 'S': p[1], 'P': logs[-1]['price'], 'C': logs[-1]['cat'], 'O': logs[-1].get('order', 999)})
        
        df_tab = pd.DataFrame(items)
        if not df_tab.empty:
            sel_cat = st.selectbox("Категория:", df_tab['C'].unique(), key=f"s_{t_tag}")
            f_df = df_tab[df_tab['C'] == sel_cat].copy().sort_values('O')
            if not f_df.empty:
                f_df['Display'] = f_df['P'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=False).fillna('—')
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
