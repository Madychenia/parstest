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

# Улучшенный CSS: фиксируем ширину колонок для идеальной ровности
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; font-size: 1.05em; line-height: 1.1; }
    .usd { color: #FF4B4B; font-weight: bold; font-size: 0.9em; }
    .price-up { color: #d32f2f; font-weight: bold; }
    .price-down { color: #388e3c; font-weight: bold; }
    
    table { width: 100% !important; border-collapse: collapse; table-layout: fixed; }
    th { background-color: #f8f9fb !important; text-align: center !important; padding: 12px !important; border: 1px solid #dee2e6 !important; }
    td { text-align: center !important; padding: 15px 5px !important; border: 1px solid #dee2e6 !important; height: 60px; vertical-align: middle !important; }
    
    /* Фиксируем первую колонку с названием модели */
    td:first-child { text-align: left !important; padding-left: 15px !important; font-weight: 600; background-color: #fcfcfc; width: 250px; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен PRO")

# --- ФУНКЦИИ ---
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
        send_telegram("✅ <b>Связь установлена!</b>\nБот готов присылать изменения цен.")
        st.toast("Тестовое сообщение отправлено!")

# --- ПАРСИНГ ---
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

            if p_uah:
                if item_id not in history: history[item_id] = []
                last = history[item_id][-1] if history[item_id] else None
                if not last or last['price'] != p_uah:
                    if last:
                        diff = p_uah - last['price']
                        perc = (diff / last['price']) * 100
                        icon = "📈 Дороже" if diff > 0 else "📉 Дешевле"
                        msg = f"🔔 <b>Изменение цены!</b>\n\n🔹 {model}\n🏪 {shop}\n💰 Новая: <b>{p_uah:,} ₴</b>\n\n{icon} на {abs(perc):.1f}%"
                        send_telegram(msg)
                    history[item_id].append({'time': now_str, 'price': p_uah, 'cat': cat})

            results.append({'Модель': model, 'Магазин': shop, 'Цена_ГРН': p_uah, 'Категория': cat})
            
        save_history(history)
        return pd.DataFrame(results)
    except: return pd.DataFrame()

# --- ВЫВОД ---
tabs = st.tabs(["Used (Б/У)", "New (Новые)"])
files = ['links.csv', 'links_new.csv']

for i, tab in enumerate(tabs):
    with tab:
        raw_data = fetch_and_track(files[i])
        if not raw_data.empty:
            def fmt(v):
                if pd.notnull(v) and v > 0:
                    return f'<span class="uah">{int(v):,} ₴</span><br><span class="usd">{int(round(v/user_rate)):,} $</span>'
                return "—"
            
            df_disp = raw_data.copy()
            df_disp['Цена'] = df_disp['Цена_ГРН'].apply(fmt)
            
            all_cats = raw_data['Категория'].unique().tolist()
            sel_cat = st.selectbox("Серия iPhone:", all_cats, key=f"cat_tab_{i}")
            
            filt = df_disp[df_disp['Категория'] == sel_cat]
            order = filt['Модель'].unique().tolist()
            
            pivot = filt.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
                index='Модель', columns='Магазин', values='Цена'
            ).fillna("—").reindex(order)
            
            st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
            
            # --- ИСТОРИЯ С ЗАЩИТОЙ ОТ KEYERROR ---
            st.divider()
            st.subheader("📜 Поиск по истории")
            hist_db = load_history()
            
            if hist_db:
                h_col1, h_col2, h_col3 = st.columns(3)
                
                # Безопасное получение категорий из истории
                available_cats = sorted(list(set(v[0].get('cat', 'Без категории') for v in hist_db.values() if v)))
                with h_col1:
                    h_cat = st.selectbox("Категория лога:", available_cats, key=f"hcat_{i}")
                
                # Фильтр моделей внутри категории
                models_in_cat = sorted(list(set(k.split(' | ')[0] for k, v in hist_db.items() if v and v[0].get('cat', 'Без категории') == h_cat)))
                with h_col2:
                    h_mod = st.selectbox("Модель:", models_in_cat, key=f"hmod_{i}")
                
                # Фильтр магазинов для выбранной модели
                shops_for_mod = sorted([k.split(' | ')[1] for k in hist_db.keys() if k.startswith(f"{h_mod} |")])
                with h_col3:
                    h_shop = st.selectbox("Магазин:", shops_for_mod, key=f"hshop_{i}")
                
                target_key = f"{h_mod} | {h_shop}"
                if target_key in hist_db:
                    logs = hist_db[target_key]
                    for j in range(len(logs)-1, -1, -1):
                        curr, prev = logs[j], (logs[j-1] if j > 0 else None)
                        diff_txt = ""
                        if prev:
                            d = curr['price'] - prev['price']
                            p_c = (d / prev['price']) * 100
                            if d > 0: diff_txt = f'<span class="price-up"> ↑ {p_c:.1f}% (+{d:,} ₴)</span>'
                            elif d < 0: diff_txt = f'<span class="price-down"> ↓ {abs(p_c):.1f}% ({d:,} ₴)</span>'
                        st.markdown(f"📅 **{curr['time']}** — **{curr['price']:,} ₴** {diff_txt}", unsafe_allow_html=True)
            else:
                st.info("История пока пуста. Нажми 'Обновить всё'.")
        else:
            st.info("Файл не найден.")
