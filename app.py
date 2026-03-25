import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'

st.set_page_config(page_title="Мониторинг цен PRO", layout="wide", initial_sidebar_state="collapsed")

# Финальный CSS для жесткой структуры
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: #1a1a1a; font-weight: 800; font-size: 1.1em; display: block; margin-bottom: 2px; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.95em; }
    .price-up { color: #d32f2f; font-weight: bold; font-size: 0.85em; }
    .price-down { color: #388e3c; font-weight: bold; font-size: 0.85em; }
    
    table { width: 100% !important; border-collapse: collapse; table-layout: fixed; border: 2px solid #e0e0e0 !important; }
    th { background-color: #f1f3f5 !important; color: #444; text-align: center !important; padding: 12px !important; border: 1px solid #dee2e6 !important; font-size: 0.9em; }
    td { text-align: center !important; padding: 10px 5px !important; border: 1px solid #dee2e6 !important; height: 65px; vertical-align: middle !important; word-wrap: break-word; }
    
    /* Первая колонка - Модель */
    td:first-child { text-align: left !important; padding-left: 15px !important; font-weight: 700; background-color: #fdfdfd; width: 220px; color: #2c3e50; }
    
    /* Полоски для читаемости */
    tr:nth-child(even) { background-color: #f8f9fa; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен PRO")

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=5)
    except: pass

# --- ПАНЕЛЬ УПРАВЛЕНИЯ ---
col_rate, col_btn, col_test = st.columns([2, 1.5, 1.5])
with col_rate:
    user_rate = st.number_input("Курс ($):", value=44.55, step=0.01)
with col_btn:
    if st.button("♻️ ОБНОВИТЬ ВСЁ", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
with col_test:
    if st.button("🔔 ТЕСТ ТГ", use_container_width=True):
        send_telegram("✅ <b>Связь установлена!</b>\nБот готов мониторить цены.")
        st.toast("Сообщение отправлено!")

# --- ГЛАВНЫЙ ПРОЦЕСС ---
@st.cache_data(ttl=3600)
def fetch_and_track(file_name):
    history = load_history()
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        kiev_tz = pytz.timezone('Europe/Kyiv')
        now_str = datetime.now(kiev_tz).strftime('%d.%m %H:%M')
        
        for _, row in df.iterrows():
            p_uah = None
            model = str(row.get('модель', '—')).strip()
            shop = str(row.get('магазин', '—')).strip()
            cat = str(row.get('категория', 'Без категории')).strip()
            item_id = f"{model} | {shop}"
            
            url = str(row.get('ссылка', '')).strip()
            sel = str(row.get('селектор', '')).strip()
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    if el:
                        digits = re.sub(r'\D', '', el.text.strip())
                        if digits: p_uah = int(digits)
                except: pass

            # Обновляем историю и принудительно ставим категорию
            if item_id not in history: history[item_id] = []
            
            # Всегда обновляем категорию в последней записи лога, чтобы фильтр работал
            if p_uah:
                last = history[item_id][-1] if history[item_id] else None
                if not last or last['price'] != p_uah:
                    if last:
                        diff = p_uah - last['price']
                        icon = "📈 Дороже" if diff > 0 else "📉 Дешевле"
                        msg = f"🔔 <b>Изменение!</b>\n\n🔹 {model}\n🏪 {shop}\n💰 Цена: <b>{p_uah:,} ₴</b>"
                        send_telegram(msg)
                    history[item_id].append({'time': now_str, 'price': p_uah, 'cat': cat})
                else:
                    # Если цена не менялась, просто убедимся что категория верная
                    last['cat'] = cat
            
            results.append({'Модель': model, 'Магазин': shop, 'Цена_ГРН': p_uah, 'Категория': cat})
            
        save_history(history)
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- ТАБЫ ---
tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
csv_files = ['links.csv', 'links_new.csv']

for i, tab in enumerate(tabs):
    with tab:
        data = fetch_and_track(csv_files[i])
        if not data.empty:
            # Рендер таблицы
            all_cats = data['Категория'].unique().tolist()
            sel_cat = st.selectbox("Серия iPhone:", all_cats, key=f"sel_cat_{i}")
            
            f_df = data[data['Категория'] == sel_cat]
            mod_order = f_df['Модель'].unique().tolist()
            
            def cell_fmt(v):
                if pd.notnull(v) and v > 0:
                    return f'<span class="uah">{int(v):,} ₴</span><span class="usd">{int(round(v/user_rate)):,} $</span>'
                return '<span style="color:#ccc">—</span>'

            disp = f_df.copy()
            disp['Цена'] = disp['Цена_ГРН'].apply(cell_fmt)
            
            pivot = disp.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
                index='Модель', columns='Магазин', values='Цена'
            ).fillna('<span style="color:#ccc">—</span>').reindex(mod_order)
            
            st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
            
            # --- ИСТОРИЯ (ФИЛЬТРЫ) ---
            st.markdown("<br><br>", unsafe_allow_html=True)
            st.subheader("📜 История изменений по фильтрам")
            h_db = load_history()
            
            h_c1, h_c2, h_c3 = st.columns(3)
            
            # Фильтр 1: Категория (берем из текущего CSV, чтобы было актуально)
            with h_c1:
                hist_cat = st.selectbox("1. Категория:", all_cats, key=f"h_c1_{i}")
            
            # Фильтр 2: Модели только из этой категории
            models_in_cat = data[data['Категория'] == hist_cat]['Модель'].unique().tolist()
            with h_c2:
                hist_mod = st.selectbox("2. Модель:", sorted(models_in_cat), key=f"h_c2_{i}")
            
            # Фильтр 3: Магазины для этой модели
            shops_for_mod = data[data['Модель'] == hist_mod]['Магазин'].unique().tolist()
            with h_c3:
                hist_shop = st.selectbox("3. Магазин:", sorted(shops_for_mod), key=f"h_c3_{i}")
            
            target = f"{hist_mod} | {hist_shop}"
            if target in h_db and h_db[target]:
                logs = h_db[target]
                for j in range(len(logs)-1, -1, -1):
                    cur = logs[j]
                    prev = logs[j-1] if j > 0 else None
                    diff_info = ""
                    if prev:
                        d = cur['price'] - prev['price']
                        p_c = (d / prev['price']) * 100
                        if d > 0: diff_info = f'<span class="price-up"> ↑ {p_c:.1f}% (+{d:,} ₴)</span>'
                        elif d < 0: diff_info = f'<span class="price-down"> ↓ {abs(p_c):.1f}% ({d:,} ₴)</span>'
                    st.markdown(f"📅 **{cur['time']}** — **{cur['price']:,} ₴** {diff_info}", unsafe_allow_html=True)
            else:
                st.info("По этой позиции записей в истории еще нет.")
