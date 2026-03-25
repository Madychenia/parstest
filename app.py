import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os
import io

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг цен", layout="wide")

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
    .log-usd { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- ФУНКЦИИ ---
@st.cache_data(ttl=3600)
def get_minfin_sell_rate():
    try:
        url = "https://minfin.com.ua/currency/"
        r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        rates = soup.find_all('div', {'class': 'sc-1x32wa2-9'})
        if len(rates) >= 2:
            rate_text = rates[1].text.replace(',', '.')
            val = float(re.findall(r"\d+\.\d+", rate_text)[0])
            return val
        return 44.55
    except:
        return 44.55

def send_excel_to_tg(df_pivot, cat_name, user_rate, minfin_rate):
    """Создает Excel и отправляет в Телеграм"""
    try:
        output = io.BytesIO()
        # Убираем HTML-теги перед сохранением в Excel
        clean_df = df_pivot.copy()
        for col in clean_df.columns:
            clean_df[col] = clean_df[col].apply(lambda x: re.sub('<[^<]+?>', ' ', str(x)) if x != '—' else x)
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            clean_df.to_excel(writer, sheet_name='Цены')
        
        output.seek(0)
        
        now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
        caption = f"📄 Таблица: {cat_name}\n📅 Дата: {now}\n👤 Ваш курс: {user_rate}\n🏦 Минфин: {minfin_rate}"
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
        files = {'document': (f"prices_{cat_name}_{now}.xlsx", output)}
        data = {'chat_id': CHAT_ID, 'caption': caption}
        requests.post(url, files=files, data=data)
        st.success("✅ Файл отправлен в Telegram!")
    except Exception as e:
        st.error(f"Ошибка отправки файла: {e}")

def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

# --- ИНТЕРФЕЙС ---
st.title("📱 Мониторинг")

minfin_rate = get_minfin_sell_rate()

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    user_rate = st.number_input("Ваш курс $:", value=44.55, step=0.01)
with c2:
    st.write(f"Обновлено: **{load_data(LAST_RUN_FILE).get('time', '—')}**")
    st.caption(f"Курс Минфина (продажа): {minfin_rate}")
with c3:
    st.write("") # Просто отступ

db = load_data(HISTORY_FILE)

if db:
    tab_names = ["Used (Б/У)", "New (Новые)"]
    tabs = st.tabs(tab_names)
    tags = ['u', 'n']
    
    for i, t_tag in enumerate(tags):
        with tabs[i]:
            rows = []
            for k, logs in db.items():
                if logs and logs[-1].get('type') == t_tag:
                    m, s = k.split(" | ")
                    rows.append({'Модель': m, 'Магазин': s, 'Цена_ГРН': logs[-1]['price'], 'Кат': logs[-1].get('cat', '1')})
            df_tab = pd.DataFrame(rows)
            
            if not df_tab.empty:
                col_sel, col_btn = st.columns([3, 1])
                with col_sel:
                    sel_cat = st.selectbox("Категория:", sorted(df_tab['Кат'].unique()), key=f"main_cat_{t_tag}")
                
                f_df = df_tab[df_tab['Кат'] == sel_cat]
                f_df['Цена'] = f_df['Цена_ГРН'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first').fillna('—')
                
                with col_btn:
                    st.write("") 
                    if st.button("📊 Отправить таблицу в ТГ", key=f"file_{t_tag}"):
                        send_excel_to_tg(pivot, sel_cat, user_rate, minfin_rate)

                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
                
                # ИСТОРИЯ
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"📜 История изменений ({tab_names[i]})", expanded=True):
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        l_cat = st.selectbox("1. Категория поиска", sorted(df_tab['Кат'].unique()), key=f"log_cat_{t_tag}")
                    with f2:
                        models_in_cat = df_tab[df_tab['Кат'] == l_cat]['Модель'].unique()
                        l_mod = st.selectbox("2. Модель", sorted(models_in_cat), key=f"log_mod_{t_tag}")
                    with f3:
                        shops_for_mod = df_tab[(df_tab['Кат'] == l_cat) & (df_tab['Модель'] == l_mod)]['Магазин'].unique()
                        l_shop = st.selectbox("3. Поставщик", sorted(shops_for_mod), key=f"log_shop_{t_tag}")
                    
                    final_key = f"{l_mod} | {l_shop}"
                    if final_key in db:
                        st.divider()
                        for e in reversed(db[final_key]):
                            p_uah = e['price']
                            p_usd_minfin = int(p_uah / minfin_rate)
                            st.markdown(f"{e['time']} — **{p_uah:,} ₴** <span class='log-usd'>({p_usd_minfin:,} $)</span>", unsafe_allow_html=True)
            else:
                st.info("Нет данных")
else:
    st.warning("База пуста.")
