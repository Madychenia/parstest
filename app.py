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

# Чистый интерфейс без лишних надписей
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
    is_first_start = len(history) == 0 # Проверяем, пустая ли база
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    files = {'links.csv': 'u', 'links_new.csv': 'n'}
    
    for f_name, tag in files.items():
        if not os.path.exists(f_name): continue
        try:
            df = pd.read_csv(f_name, sep=None, engine='python')
            df.columns = [c.strip().lower() for c in df.columns]
        except: continue
        
        for _, row in df.iterrows():
            # Берем данные, учитывая твои колонки
            model = str(row.get('модель', row.get('model', 'Unknown')))
            shop = str(row.get('магазин', row.get('shop', 'Shop')))
            url = str(row.get('ссылка', row.get('url', '')))
            sel = str(row.get('селектор', row.get('selector', '')))
            cat = str(row.get('категория', row.get('category', '1')))
            
            key = f"{model} | {shop}"
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        price = int(re.sub(r'\D', '', el.text.strip()))
                        
                        if key not in history:
                            history[key] = []
                            # Если это не самый первый запуск программы, маякуем о новой позиции
                            if not is_first_start:
                                send_tg(f"🆕 <b>{model}</b>\nДобавлена цена в {shop}: <b>{price:,} ₴</b>")
                        
                        last_entry = history[key][-1] if history[key] else None
                        
                        if not last_entry or last_entry['price'] != price:
                            if last_entry and not is_first_start:
                                diff = price - last_entry['price']
                                symbol = "📈" if diff > 0 else "📉"
                                send_tg(f"{symbol} <b>{model}</b> ({shop})\nСтало: <b>{price:,} ₴</b>\nБыло: {last_entry['price']:,} ₴")
                            
                            history[key].append({'time': now, 'price': price, 'cat': cat, 'type': tag})
                except: continue
    
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': datetime.now(KIEV_TZ).strftime('%d.%m %H:%M:%S')})

# --- ОСНОВНОЙ UI ---
st.title("📱 Мониторинг")

c1, c2, c3 = st.columns([1, 2, 1])
with c1:
    rate = st.number_input("Курс $:", value=44.55, label_visibility="collapsed")
with c2:
    last_t = load_data(LAST_RUN_FILE).get('time', 'Никогда')
    st.write(f"Обновлено: **{last_t}**")
with c3:
    if st.button("🔔 ТЕСТ ТГ"): send_tg("✅ Бот на связи!")

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
                sel_cat = st.selectbox("Категория:", cat_list, key=f"sel_{tag}")
                
                f_df = df[df['Кат'] == sel_cat]
                # Формируем красивый вывод
                f_df['Цена'] = f_df['Цена_ГРН'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/rate):,} $</span>')
                
                try:
                    pivot = f_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first').fillna('—')
                    st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
                except Exception as e:
                    st.error(f"Ошибка таблицы: {e}")
            else:
                st.info("В этой категории пока нет данных.")
else:
    st.warning("База пуста. Нажмите 'ОБНОВИТЬ ВСЁ', чтобы собрать данные.")

if st.button("♻️ ОБНОВИТЬ ВСЁ"):
    with st.spinner("Парсим..."):
        run_parsing()
        st.rerun()

with st.expander("📜 История изменений (Логи)"):
    if hist_db:
        sk = st.selectbox("Выберите модель для логов:", sorted(hist_db.keys()))
        for e in reversed(hist_db[sk]):
            st.write(f"{e['time']} — **{e['price']:,} ₴**")

if __name__ == "__main__":
    run_parsing()
