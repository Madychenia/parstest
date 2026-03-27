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
TELEGRAM_TOKEN = "7708518961:AAH8rY9Xq-Fv_m_iUjL-4u_GkC-JjI0eMFE"
TELEGRAM_CHAT_ID = "1107530654"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# Функция "тихой" отправки ботом
def bot_order(model, price, shop, url):
    text = (
        f"🚀 **ЗАКАЗ ТОВАРА**\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📱 **Модель:** {model}\n"
        f"💰 **Цена:** {price:,} ₴\n"
        f"🏪 **Магазин:** {shop}\n"
        f"🔗 [Открыть сайт]({url})"
    )
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(api_url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except:
        pass

def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def get_minfin_rate():
    try:
        url = "https://minfin.com.ua/currency/auction/usd/buy/kiev/"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        rate_el = soup.select_one('.sc-1x32wa2-9') 
        if rate_el:
            val = re.sub(r'[^\d.]', '', rate_el.text.replace(',', '.'))
            return float(val)
    except: pass
    return 44.15

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Мониторинг", layout="wide")

# Стили для ровной сетки и красивых кнопок-цен
st.markdown("""<style>
    .block-container { padding: 1rem !important; max-width: 1100px !important; margin: 0 auto !important; }
    .stButton > button { 
        width: 100%; 
        border: 1px solid #ddd !important; 
        background: white !important; 
        color: black !important;
        padding: 5px !important;
        line-height: 1.2 !important;
        height: auto !important;
    }
    .stButton > button:hover { border-color: #FF4B4B !important; color: #FF4B4B !important; }
    .header-row { font-weight: bold; background: #f0f2f6; padding: 10px; border-radius: 5px; text-align: center; margin-bottom: 10px; }
    .model-name { font-weight: bold; font-size: 0.9em; display: flex; align-items: center; height: 100%; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")

minfin_rate = get_minfin_rate()
db, last_run = load_data(HISTORY_FILE), load_data(LAST_RUN_FILE)

# Шапка
c1, c2, c3 = st.columns([1, 2, 1])
with c1: user_rate = st.number_input("Курс $:", value=44.55) 
with c2: st.write(f"⌛ Обновлено: **{last_run.get('time', '—')}** \n📈 Минфин: **{minfin_rate}**")
with c3: 
    if st.button("🗑 СБРОСИТЬ БАЗУ"):
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
                items.append({
                    'M': p[0], 'S': p[1], 'Цена': logs[-1]['price'], 
                    'URL': logs[-1].get('url', '#'), 'Категория': logs[-1]['cat'], 
                    'order': logs[-1].get('order', 999)
                })
        
        if items:
            df_tab = pd.DataFrame(items)
            cats = sorted(df_tab['Категория'].unique())
            sel_cat = st.selectbox("Выберите категорию:", cats, key=f"cat_sel_{tag_key}")
            
            f_df = df_tab[df_tab['Категория'] == sel_cat].copy().sort_values('order')
            
            if not f_df.empty:
                shops = sorted(f_df['S'].unique())
                models = f_df['M'].unique()
                
                # Рисуем заголовок таблицы
                cols = st.columns([2] + [1] * len(shops))
                cols[0].markdown('<div class="header-row">Модель</div>', unsafe_allow_html=True)
                for idx, shop in enumerate(shops):
                    cols[idx+1].markdown(f'<div class="header-row">{shop}</div>', unsafe_allow_html=True)
                
                # Рисуем строки
                for model in models:
                    row_cols = st.columns([2] + [1] * len(shops))
                    row_cols[0].markdown(f'<div class="model-name">{model}</div>', unsafe_allow_html=True)
                    
                    for idx, shop in enumerate(shops):
                        target = f_df[(f_df['M'] == model) & (f_df['S'] == shop)]
                        with row_cols[idx+1]:
                            if not target.empty:
                                price = target.iloc[0]['Цена']
                                url = target.iloc[0]['URL']
                                usd_price = int(price / user_rate)
                                
                                # Кнопка-цена: при клике летит в ТГ без перезагрузки
                                btn_label = f"{price:,} ₴\n{usd_price:,} $"
                                if st.button(btn_label, key=f"btn_{tag_key}_{model}_{shop}"):
                                    bot_order(model, price, shop, url)
                                    st.toast(f"✅ Заказ отправлен: {model}")
                            else:
                                st.write("—")
