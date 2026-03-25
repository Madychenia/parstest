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
import plotly.graph_objects as go

# --- КОНФИГ ---
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)

def clean_price(text):
    res = re.sub(r'[^\d]', '', text)
    return int(res) if res else None

def run_parsing():
    history = load_data(HISTORY_FILE)
    now = datetime.now(KIEV_TZ).strftime('%d.%m %H:%M')
    mapping = {'links.csv': 'u', 'links_new.csv': 'n'}
    
    for f_name, tag in mapping.items():
        if os.path.exists(f_name):
            try:
                df = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
                df.columns = [c.strip().lower() for c in df.columns]
                for idx, row in df.iterrows():
                    m, s, u, sel, c = [str(row.get(k, '')).strip() for k in ['модель','магазин','ссылка','селектор','категория']]
                    if u.startswith('http') and sel and sel != 'nan':
                        try:
                            r = requests.get(u, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                            soup = BeautifulSoup(r.text, 'html.parser')
                            el = soup.select_one(sel)
                            if el:
                                price_val = clean_price(el.text)
                                if price_val:
                                    key = f"{m} | {s} | {tag}"
                                    if key not in history: history[key] = []
                                    history[key].append({'time': now, 'price': price_val, 'cat': c, 'type': tag, 'order': idx})
                                    if len(history[key]) > 50: history[key] = history[key][-50:]
                        except: pass
            except: pass
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': now})

if "--parse" in sys.argv:
    run_parsing()
    sys.exit(0)

st.set_page_config(page_title="Мониторинг", layout="wide")
st.markdown("""<style>
    .block-container { padding: 1rem !important; max-width: 1100px !important; margin: 0 auto !important; }
    .table-container { overflow-x: auto; width: 100%; border: none; margin-bottom: 20px; text-align: center; }
    
    table { margin: 0 auto; border-collapse: collapse; width: auto !important; }
    th, td { padding: 4px 10px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    
    tbody tr th { 
        background-color: #f8f9fa !important; 
        font-weight: bold; 
        text-align: left !important;
        border-right: 2px solid #ddd !important;
    }
    
    thead tr:nth-child(2) { display: none; }
    thead tr:first-child th:first-child { 
        background-color: #f8f9fa !important;
        color: transparent !important;
    }

    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    .hist-box { padding: 10px; border: 1px solid #eee; border-radius: 5px; background: #fafafa; margin-top: 20px; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = 44.15 
db = load_data(HISTORY_FILE)
last_run = load_data(LAST_RUN_FILE)

c1, c2, c3, c4 = st.columns([1,1.5,1,1])
with c1: user_rate = st.number_input("", value=44.55, label_visibility="collapsed") 
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.write(f"Курс Минфина: **{minfin_rate}**")
with c3: 
    if st.button("♻️ ОБНОВИТЬ"): 
        run_parsing()
        st.rerun()
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
                items.append({'M': p[0], 'S': p[1], 'Цена': logs[-1]['price'], 'Категория': logs[-1]['cat'], 'order': logs[-1].get('order', 999)})
        
        if items:
            df_tab = pd.DataFrame(items)
            cats = sorted(df_tab['Категория'].unique())
            sel_cat = st.selectbox("Выбор категории:", cats, key=f"s_{tag_key}")
            
            f_df = df_tab[df_tab['Категория'] == sel_cat].copy().sort_values('order')
            
            if not f_df.empty:
                f_df['Display'] = f_df['Цена'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=False).fillna('—')
                pivot.index.name = None
                pivot.columns.name = None
                st.markdown(f'<div class="table-container">{pivot.to_html(escape=False)}</div>', unsafe_allow_html=True)

                # --- БЛОК ИСТОРИИ И ГРАФИКОВ ---
                st.markdown("---")
                models_in_cat = sorted(f_df['M'].unique())
                sel_model = st.selectbox("История цены для модели:", models_in_cat, key=f"m_{tag_key}")
                
                fig = go.Figure()
                has_plot = False
                
                col_hist1, col_hist2 = st.columns([1, 2])
                
                with col_hist2:
                    for shop in f_df['S'].unique():
                        key = f"{sel_model} | {shop} | {tag_key}"
                        if key in db:
                            h_df = pd.DataFrame(db[key])
                            if not h_df.empty:
                                fig.add_trace(go.Scatter(x=h_df['time'], y=h_df['price'], name=shop, mode='lines+markers'))
                                has_plot = True
                    
                    if has_plot:
                        fig.update_layout(height=350, margin=dict(l=0,r=0,t=20,b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02))
                        st.plotly_chart(fig, use_container_width=True)

                with col_hist1:
                    st.write(f"**Последние изменения ({sel_model}):**")
                    for shop in f_df['S'].unique():
                        key = f"{sel_model} | {shop} | {tag_key}"
                        if key in db and db[key]:
                            last_p = db[key][-1]['price']
                            st.write(f"{shop}: **{last_p:,} ₴** ({int(last_p/user_rate)} $)")
