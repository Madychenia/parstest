import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os

# --- НАСТРОЙКИ TELEGRAM (Данные применены) ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"

st.set_page_config(page_title="Мониторинг цен PRO", layout="wide", initial_sidebar_state="collapsed")

# Стили оформления
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; font-size: 1.1em; }
    .usd { color: #FF4B4B; font-weight: bold; }
    .price-up { color: #d32f2f; font-weight: bold; }
    .price-down { color: #388e3c; font-weight: bold; }
    td { text-align: center !important; padding: 12px !important; }
    th { background-color: #f8f9fb !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен PRO")

# --- РАБОТА С ИСТОРИЕЙ (JSON) ---
HISTORY_FILE = 'price_history.json'

def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
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
col1, col2, col3 = st.columns([2, 2, 6])
with col1:
    user_rate = st.number_input("Рабочий курс ($):", value=44.55, step=0.01)
with col2:
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        st.cache_data.clear()
        st.rerun()

# --- ОСНОВНОЙ ПРОЦЕСС ---
@st.cache_data(ttl=3600)
def fetch_and_track(file_name):
    history = load_history()
    try:
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        results = []
        headers = {'User-Agent': 'Mozilla/5.0'}
        
        kiev_tz = pytz.timezone('Europe/Kyiv')
        now_str = datetime.now(kiev_tz).strftime('%d.%m %H:%M:%S')
        
        for _, row in df.iterrows():
            p_uah = None
            model = str(row.get('модель', '—')).strip()
            shop = str(row.get('магазин', '—')).strip()
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
                
                # Проверяем последнее изменение
                last_entry = history[item_id][-1] if history[item_id] else None
                
                if not last_entry or last_entry['price'] != p_uah:
                    change_text = ""
                    if last_entry:
                        diff = p_uah - last_entry['price']
                        perc = (diff / last_entry['price']) * 100
                        icon = "📈 Дороже" if diff > 0 else "📉 Дешевле"
                        change_text = f"\n\n{icon} на <b>{abs(perc):.1f}%</b> ({diff:,} ₴)"
                    
                    # Пишем в лог
                    history[item_id].append({'time': now_str, 'price': p_uah})
                    
                    # Шлем в ТГ только если это не первая запись в истории
                    if last_entry:
                        msg = f"🔔 <b>Изменение цены!</b>\n\n🔹 {model}\n🏪 Магазин: {shop}\n💰 Новая цена: <b>{p_uah:,} ₴</b>{change_text}"
                        send_telegram(msg)

            results.append({
                'Модель': model, 
                'Магазин': shop, 
                'Цена_ГРН': p_uah,
                'Категория': row.get('категория', 'Без категории') 
            })
            
        save_history(history)
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка файла: {e}")
        return pd.DataFrame()

# --- ВКЛАДКИ ---
tab_used, tab_new = st.tabs(["Used (Б/У)", "New (Новые)"])

def render_content(file_name):
    raw_data = fetch_and_track(file_name)
    if not raw_data.empty:
        # Быстрый пересчет валюты
        def format_prices(val):
            if pd.notnull(val):
                p_usd = int(round(val / user_rate))
                return f'<span class="uah">{int(val):,} ₴</span><br><span class="usd">{p_usd:,} $</span>'
            return "—"
        
        display_df = raw_data.copy()
        display_df['Цена'] = display_df['Цена_ГРН'].apply(format_prices)
        
        cats = display_df['Категория'].unique().tolist()
        sel_cat = st.selectbox(f"Серия iPhone:", cats, key=f"sel_{file_name}")
        
        filtered = display_df[display_df['Категория'] == sel_cat]
        order = filtered['Модель'].unique().tolist()
        
        pivot = filtered.drop_duplicates(subset=['Модель', 'Магазин']).pivot(
            index='Модель', columns='Магазин', values='Цена'
        ).fillna("—").reindex(order)
        
        st.write(pivot.to_html(escape=False), unsafe_allow_html=True)
        
        # --- СЕКЦИЯ ЛОГОВ ПО КЛИКУ ---
        st.divider()
        st.subheader("📊 История изменений (лог)")
        hist = load_history()
        
        available_items = [k for k in hist.keys() if k.split(' | ')[0] in order]
        if available_items:
            target = st.selectbox("Выбери позицию для проверки истории:", sorted(available_items), key=f"log_{file_name}")
            
            log_list = hist[target]
            for i in range(len(log_list)-1, -1, -1):
                c = log_list[i]
                p = log_list[i-1] if i > 0 else None
                diff_label = ""
                if p:
                    d = c['price'] - p['price']
                    pc = (d / p['price']) * 100
                    if d > 0: diff_label = f'<span class="price-up"> ↑ {pc:.1f}% (+{d:,} ₴)</span>'
                    elif d < 0: diff_label = f'<span class="price-down"> ↓ {abs(pc):.1f}% ({d:,} ₴)</span>'
                
                st.markdown(f"📅 **{c['time']}** — **{c['price']:,} ₴** {diff_label}", unsafe_allow_html=True)
    else:
        st.info(f"Файл {file_name} не загружен или пуст.")

with tab_used: render_content('links.csv')
with tab_new: render_content('links_new.csv')
