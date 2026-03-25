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
import sys

# --- КОНФИГ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

st.set_page_config(page_title="Мониторинг", layout="wide")

# Стили (скрываем заголовки Модель/Магазин)
st.markdown("""
    <style>
    .block-container { padding: 1rem !important; }
    .table-container { overflow-x: auto; width: 100%; border: 1px solid #eee; }
    th, td { padding: 8px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    .blank, .index_name { display: none !important; }
    td:first-child, th:first-child { 
        position: sticky; left: 0; background: #f8f9fa; z-index: 2; 
        font-weight: bold; border-right: 2px solid #ddd !important; 
    }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    .log-usd { color: #FF4B4B; font-weight: bold; }
    .status-error { color: #ff4b4b; font-size: 0.8em; }
    </style>
    """, unsafe_allow_html=True)

# --- ФУНКЦИИ ---
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
        return 44.15 #
    except:
        return 44.15

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
    errors = []
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    mapping = {'links.csv': 'u', 'links_new.csv': 'n'}
    
    for f_name, tag in mapping.items():
        if not os.path.exists(f_name): continue
        # Читаем CSV с авто-определением разделителя
        df = pd.read_csv(f_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [c.strip().lower() for c in df.columns]
        
        for _, row in df.iterrows():
            m = str(row.get('модель', '—')).strip()
            s = str(row.get('магазин', '—')).strip()
            u = str(row.get('ссылка', '')).strip()
            sel = str(row.get('селектор', '')).strip()
            c = str(row.get('категория', '1')).strip() # Берем категорию из файла
            key = f"{m} | {s}"
            
            if u.startswith('http'):
                try:
                    r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(sel)
                    price = clean_price(el.text.strip()) if el else None
                    
                    if price:
                        if key not in history: history[key] = []
                        last = history[key][-1] if history[key] else None
                        if not last or last['price'] != price:
                            if last:
                                msg = f"🔔 <b>{m}</b>\n{s}: <b>{price:,} ₴</b>"
                                requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", 
                                              data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
                            history[key].append({'time': now, 'price': price, 'cat': c, 'type': tag})
                    else:
                        errors.append(f"❌ {key}: Цена не найдена")
                except Exception as e:
                    errors.append(f"❌ {key}: {str(e)[:40]}")
                    
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': datetime.now(KIEV_TZ).strftime('%d.%m %H:%M:%S'), 'errors': errors})

# --- ИНТЕРФЕЙС ---
st.title("📱 Мониторинг")

minfin_rate = get_minfin_sell_rate()
last_run = load_data(LAST_RUN_FILE) # Читаем без кэша

c1, c2, c3 = st.columns([1, 1, 1])
with c1:
    user_rate = st.number_input("Ваш курс $:", value=44.55, step=0.01)
with c2:
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.caption(f"Курс Минфина: {minfin_rate}")
with c3:
    if st.button("♻️ ОБНОВИТЬ ВСЁ"):
        with st.spinner("Синхронизация..."):
            run_parsing()
            st.rerun()

if last_run.get('errors'):
    with st.expander("⚠️ Проблемы"):
        for err in last_run['errors']:
            st.markdown(f'<p class="status-error">{err}</p>', unsafe_allow_html=True)

db = load_data(HISTORY_FILE)

if db:
    tab_names = ["Used (Б/У)", "New (Новые)"]
    tabs = st.tabs(tab_names)
    tags = ['u', 'n']
    
    for i, t_tag in enumerate(tags):
        with tabs[i]:
            rows = []
            for k, logs in db.items():
                if logs:
                    last_entry = logs[-1]
                    if last_entry.get('type') == t_tag:
                        parts = k.split(" | ")
                        rows.append({
                            'Модель': parts[0].strip(), 
                            'Магазин': parts[1].strip(), 
                            'Цена_ГРН': last_entry['price'], 
                            'Кат': str(last_entry.get('cat', '1')).strip()
                        })
            
            df_tab = pd.DataFrame(rows)
            
            if not df_tab.empty:
                cat_list = sorted(df_tab['Кат'].unique())
                col_sel, _ = st.columns([3, 1])
                with col_sel:
                    sel_cat = st.selectbox("Категория:", cat_list, key=f"s_{t_tag}")
                
                f_df = df_tab[df_tab['Кат'] == sel_cat].copy()
                
                if not f_df.empty:
                    # ТВОЙ КУРС ДЛЯ ТАБЛИЦЫ
                    f_df['Цена'] = f_df['Цена_ГРН'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                    pivot = f_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first').fillna('—')
                    pivot.index.name = None
                    pivot.columns.name = None
                    st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)
                
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander(f"📜 История изменений", expanded=True):
                    f1, f2, f3 = st.columns(3)
                    with f1:
                        l_cat = st.selectbox("1. Категория", cat_list, key=f"lc_{t_tag}")
                    with f2:
                        mods = sorted(df_tab[df_tab['Kat'] == l_cat]['Модель'].unique()) if 'Kat' in df_tab else sorted(df_tab[df_tab['Кат'] == l_cat]['Модель'].unique())
                        l_mod = st.selectbox("2. Модель", mods, key=f"lm_{t_tag}")
                    with f3:
                        shps = sorted(df_tab[(df_tab['Кат'] == l_cat) & (df_tab['Модель'] == l_mod)]['Магазин'].unique())
                        l_shop = st.selectbox("3. Поставщик", shps, key=f"ls_{t_tag}")
                    
                    final_key = f"{l_mod} | {l_shop}"
                    if final_key in db:
                        for e in reversed(db[final_key]):
                            p_uah = e['price']
                            # КУРС МИНФИНА ДЛЯ ИСТОРИИ
                            p_usd_mf = int(p_uah / minfin_rate)
                            st.markdown(f"{e['time']} — **{p_uah:,} ₴** <span class='log-usd'>({p_usd_mf:,} $)</span>", unsafe_allow_html=True)
            else:
                st.info("Пусто")

# Отладка видна, чтобы мы проверили 13 128
with st.expander("🛠 База данных (ключи)"):
    st.write(list(db.keys()))

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == '--parse':
        run_parsing()
