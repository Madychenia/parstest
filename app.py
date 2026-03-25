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
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг цен", layout="wide")

# Компактный стиль для мобильного
st.markdown("""
    <style>
    .block-container { padding: 0.5rem 1rem !important; }
    .price-row { 
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px; border-bottom: 1px solid #eee; background: white;
    }
    .model-name { font-weight: 600; font-size: 0.95em; color: #333; }
    .price-block { text-align: right; }
    .uah { font-weight: 800; color: #1a1a1a; display: block; font-size: 1.1em; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.85em; }
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
    if not text: return None
    res = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    if '.' in res: res = res.split('.')[0]
    try:
        val = int(res)
        return val if val > 1000 else None
    except: return None

def run_parsing():
    history = load_data(HISTORY_FILE)
    is_first = len(history) == 0
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    mapping = {'links.csv': 'u', 'links_new.csv': 'n'}
    for f_name, tag in mapping.items():
        if not os.path.exists(f_name): continue
        df = pd.read_csv(f_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [c.strip().lower() for c in df.columns]
        for _, row in df.iterrows():
            m, s = str(row.get('модель', '—')).strip(), str(row.get('магазин', '—')).strip()
            u, sel = str(row.get('ссылка', '')).strip(), str(row.get('селектор', '')).strip()
            c = str(row.get('категория', '1')).strip()
            key = f"{m} | {s}"
            if u.startswith('http'):
                try:
                    r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    price = clean_price(el.text.strip()) if el else None
                    if price:
                        if key not in history: history[key] = []
                        last = history[key][-1] if history[key] else None
                        if not last or last['price'] != price:
                            if last and not is_first:
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                              data={"chat_id": CHAT_ID, "text": f"🔔 <b>{m}</b>\n{s}: <b>{price:,} ₴</b>", "parse_mode": "HTML"})
                            history[key].append({'time': now, 'price': price, 'cat': c, 'type': tag})
                        else:
                            history[key][-1].update({'cat': c, 'type': tag})
                except: continue
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': datetime.now(KIEV_TZ).strftime('%d.%m %H:%M:%S')})

# --- ИНТЕРФЕЙС ---
c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    rate = st.number_input("$:", value=44.55, step=0.01, label_visibility="collapsed")
with c2:
    st.caption(f"Обновлено: {load_data(LAST_RUN_FILE).get('time', '—')}")
with c3:
    if st.button("♻️"):
        with st.spinner("..."):
            run_parsing()
            st.rerun()

db = load_data(HISTORY_FILE)
if db:
    tabs = st.tabs(["Used", "New"])
    tags = ['u', 'n']
    
    for i, t_tag in enumerate(tags):
        with tabs[i]:
            rows = []
            for k, logs in db.items():
                if logs and logs[-1].get('type') == t_tag:
                    m, s = k.split(" | ")
                    rows.append({'Модель': m, 'Поставщик': s, 'Цена_ГРН': logs[-1]['price'], 'Кат': logs[-1].get('cat', '1')})
            
            df = pd.DataFrame(rows)
            if not df.empty:
                col_a, col_b = st.columns(2)
                with col_a:
                    sel_cat = st.selectbox("Категория", sorted(df['Кат'].unique()), key=f"cat_{t_tag}")
                
                # Фильтруем поставщиков на основе выбранной категории
                df_cat = df[df['Кат'] == sel_cat]
                with col_b:
                    sel_prov = st.selectbox("Поставщик", sorted(df_cat['Поставщик'].unique()), key=f"prov_{t_tag}")
                
                # Финальный список моделей
                f_df = df_cat[df_cat['Поставщик'] == sel_prov].sort_values('Модель')
                
                for _, row in f_df.iterrows():
                    p_uah = row['Цена_ГРН']
                    p_usd = int(p_uah / rate)
                    st.markdown(f"""
                        <div class="price-row">
                            <div class="model-name">{row['Модель']}</div>
                            <div class="price-block">
                                <span class="uah">{p_uah:,} ₴</span>
                                <span class="usd">{p_usd:,} $</span>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Нет данных")

with st.expander("📜 Логи"):
    if db:
        target = st.selectbox("Девайс:", sorted(db.keys()))
        for e in reversed(db[target]): st.write(f"{e['time']} — **{e['price']:,} ₴**")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--parse':
        run_parsing()
