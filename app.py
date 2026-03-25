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

# CSS для фиксации колонки и компактности
st.markdown("""
    <style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    th, td { padding: 8px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    td:first-child, th:first-child { 
        position: sticky; left: 0; background: #f8f9fa; z-index: 2; 
        font-weight: bold; border-right: 2px solid #ddd !important; 
    }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
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

def send_tg(msg):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                       data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}, timeout=5)
    except: pass

def clean_price(text):
    if not text: return None
    # Очистка от мусора: оставляем только цифры до первой точки/запятой
    res = re.sub(r'[^\d.,]', '', text).replace(',', '.')
    if '.' in res: res = res.split('.')[0]
    try:
        val = int(res)
        return val if val > 1000 else None # Игнорируем подозрительно низкие цены (ошибки парсинга)
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
            m, s = str(row.get('модель', '—')), str(row.get('магазин', '—'))
            u, sel = str(row.get('ссылка', '')), str(row.get('селектор', ''))
            c = str(row.get('категория', '1'))
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
                                diff = price - last['price']
                                sign = "📈" if diff > 0 else "📉"
                                send_tg(f"{sign} <b>{m}</b>\n{s}: <b>{price:,} ₴</b> (было {last['price']:,})")
                            history[key].append({'time': now, 'price': price, 'cat': c, 'type': tag})
                        else:
                            history[key][-1].update({'cat': c, 'type': tag})
                except: continue
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': datetime.now(KIEV_TZ).strftime('%d.%m %H:%M:%S')})

# --- ИНТЕРФЕЙС ---
st.title("📱 Мониторинг")

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    rate = st.number_input("$:", value=44.55, step=0.01, label_visibility="collapsed")
with c2:
    st.write(f"Обновлено: **{load_data(LAST_RUN_FILE).get('time', '—')}**")
with c3:
    if st.button("♻️ ОБНОВИТЬ"):
        with st.spinner("Парсим..."):
            run_parsing()
            st.rerun()

db = load_data(HISTORY_FILE)
if db:
    tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
    for i, t_tag in enumerate(['u', 'n']):
        with tabs[i]:
            rows = []
            for k, logs in db.items():
                if logs and logs[-1].get('type') == t_tag:
                    m, s = k.split(" | ")
                    rows.append({'Модель': m, 'Магазин': s, 'Цена_ГРН': logs[-1]['price'], 'Кат': logs[-1].get('cat', '1')})
            
            df = pd.DataFrame(rows)
            if not df.empty:
                cat = st.selectbox("Категория:", sorted(df['Кат'].unique()), key=f"tab_{i}")
                f_df = df[df['Кат'] == cat]
                f_df['Цена'] = f_df['Цена_ГРН'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/rate):,} $</span>')
                
                # Создаем таблицу
                res_table = f_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first').fillna('—')
                st.markdown(f'<div class="table-container">{res_table.to_html(escape=False)}</div>', unsafe_allow_html=True)
            else:
                st.info("Нет данных")
else:
    st.warning("База пуста. Нажми 'ОБНОВИТЬ' или подожди робота.")

with st.expander("📜 Логи"):
    if db:
        target = st.selectbox("Девайс:", sorted(db.keys()))
        for e in reversed(db[target]): st.write(f"{e['time']} — **{e['price']:,} ₴**")

if __name__ == "__main__":
    # Это для запуска через GitHub Actions
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--parse':
        run_parsing()
