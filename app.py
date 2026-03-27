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
import time

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = "7708518961:AAH8rY9Xq-Fv_m_iUjL-4u_GkC-JjI0eMFE"
TELEGRAM_CHAT_ID = "1107530654"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

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

def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Мониторинг", layout="wide")
st.markdown("""<style>
    .block-container { padding: 1rem !important; max-width: 1000px !important; margin: 0 auto !important; }
    .table-container { overflow-x: auto; width: 100%; text-align: center; margin-bottom: 20px; }
    table { margin: 0 auto; border-collapse: collapse; width: auto !important; }
    th, td { padding: 4px 10px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    .uah { color: #1a1a1a; font-weight: 800; display: block; text-decoration: underline; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; text-decoration: none !important; }
    a { text-decoration: none !important; }
    .log-line { font-family: monospace; font-size: 0.95em; margin: 2px 0; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = get_minfin_rate()
db, last_run = load_data(HISTORY_FILE), load_data(LAST_RUN_FILE)

# Убрали лишнюю колонку c3 (Обновить)
c1, c2, c4 = st.columns([1, 1.5, 1])
with c1: user_rate = st.number_input("", value=44.55, label_visibility="collapsed") 
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.write(f"Минфин (продажа): **{minfin_rate}**")
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
                items.append({
                    'M': p[0], 
                    'S': p[1], 
                    'Цена': logs[-1]['price'], 
                    'Категория': logs[-1]['cat'], 
                    'order': logs[-1].get('order', 999)
                })
        
        if items:
            df_tab = pd.DataFrame(items)
            cats = df_tab['Категория'].unique() 
            sel_cat = st.selectbox("Категория:", cats, key=f"cat_{tag_key}")
            f_df = df_tab[df_tab['Категория'] == sel_cat].copy().sort_values('order')
            
            if not f_df.empty:
                # Функция создания кликабельной цены со ссылкой в TG
                def make_tg_link(row):
                    p_val = row['Цена']
                    m_name = row['M']
                    s_name = row['S']
                    
                    # Формируем текст сообщения для ТГ
                    msg = f"Заказ: {m_name} за {p_val:,} грн в {s_name}"
                    # Ссылка для пересылки в ТГ
                    tg_url = f"https://t.me/share/url?url={msg}"
                    
                    return f'''
                        <a href="{tg_url}" target="_blank">
                            <span class="uah">{p_val:,} ₴</span>
                            <span class="usd">{int(p_val/user_rate):,} $</span>
                        </a>
                    '''

                f_df['Display'] = f_df.apply(make_tg_link, axis=1)
                f_df['M'] = pd.Categorical(f_df['M'], categories=f_df['M'].unique(), ordered=True)
                
                # Создаем финальную таблицу
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=False).fillna('—')
                pivot.index.name = pivot.columns.name = None
                
                # Выводим через HTML
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)

                st.markdown("---")
                with st.expander("Отслеживание цены"):
                    hc1, hc2, hc3 = st.columns(3)
                    with hc1: h_cat = st.selectbox("Категория:", cats, key=f"hc_{tag_key}")
                    h_mod_df = df_tab[df_tab['Категория'] == h_cat].sort_values('order')
                    with hc2: h_mod = st.selectbox("Модель:", h_mod_df['M'].unique(), key=f"hm_{tag_key}")
                    with hc3:
                        h_shop_list = df_tab[(df_tab['Категория'] == h_cat) & (df_tab['M'] == h_mod)]['S'].unique()
                        h_shop = st.selectbox("Продавец:", h_shop_list, key=f"hs_{tag_key}")
                    
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
