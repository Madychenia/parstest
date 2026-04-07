import streamlit as st
import pandas as pd
import requests
import re
import json
import os
import sys
import time
import pytz
from datetime import datetime
from bs4 import BeautifulSoup

# --- НАСТРОЙКИ (Актуальные данные) ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
TELEGRAM_CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

# Функция логирования посещений
def send_tg_log():
    try:
        headers = st.context.headers
        
        # 1. Пытаемся вытащить реальный IP (перебираем все возможные заголовки)
        forwarded_for = headers.get("X-Forwarded-For")
        real_ip = headers.get("X-Real-IP")
        
        if forwarded_for:
            user_ip = forwarded_for.split(',')[0].strip()
        elif real_ip:
            user_ip = real_ip.strip()
        else:
            # Если в облаке не нашлось, берем через внешний сервис (запасной вариант)
            user_ip = requests.get('https://api.ipify.org', timeout=5).text

        # 2. Получаем геопозицию
        ip_data = requests.get(f'https://ipapi.co/{user_ip}/json/', timeout=5).json()
        city = ip_data.get('city', 'Unknown')
        country = ip_data.get('country_name', 'Unknown')
        org = ip_data.get('org', 'Unknown')

        # 3. Определяем девайс
        ua = headers.get("User-Agent", "Unknown")
        if "iPhone" in ua: device = "📱 iPhone"
        elif "Android" in ua: device = "🤖 Android"
        else: device = "💻 PC"
        
        time_now = datetime.now(KIEV_TZ).strftime("%Y-%m-%d %H:%M:%S")

        # 4. Формируем сообщение (убрал лишние пробелы, чтобы не "съезжало")
        text = (
            f"🚀 *Реальный визит*\n"
            f"📍 {city}, {country}\n"
            f"🌐 IP: `{user_ip}`\n"
            f"📶 Сеть: `{org}`\n"
            f"🖥 {device}\n"
            f"📅 `{time_now}`"
        )
        
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception:
        pass
# Проверка сессии (срабатывает 1 раз при заходе пользователя)
if 'visitor_logged' not in st.session_state:
    send_tg_log()
    st.session_state['visitor_logged'] = True

# --- КОНЕЦ БЛОКА НАСТРОЕК (Далее твой основной код) ---
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import pytz
import json
import os
import sys
import time  # ДОБАВЛЕН ИМПОРТ ДЛЯ ПАУЗ

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = "8673005085:AAG-vDGUu4buhPHmMYoJt1a7UueVIywvAyQ"
TELEGRAM_CHAT_ID = "258388401"
HISTORY_FILE = 'price_history.json'
LAST_RUN_FILE = 'last_run.json'
KIEV_TZ = pytz.timezone('Europe/Kyiv')

# Реалистичный заголовок браузера
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
}

def send_telegram(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=10)
    except: pass

def get_minfin_rate():
    try:
        # Прямая ссылка на аукцион (Киев, Доллар, Продажа)
        url = "https://minfin.com.ua/currency/auction/usd/sell/kiev/"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Ищем через регулярку или более стабильный класс
        # На Минфине курс часто лежит в span внутри определенных блоков
        rate_el = soup.find('span', class_=re.compile(r'Typography.*Headline.*'))
        
        if not rate_el:
            # Запасной поиск по специфическому селектору, если первый не сработал
            rate_el = soup.select_one('.sc-1x32wa2-9') 

        if rate_el:
            # Очищаем текст от мусора, оставляем только цифры и точку
            val = re.sub(r'[^\d.]', '', rate_el.text.replace(',', '.'))
            new_rate = float(val)
            print(f"✅ Курс Минфина успешно спарсен: {new_rate}")
            return new_rate
            
    except Exception as e:
        print(f"❌ Ошибка парсинга Минфина: {e}")
    
    # Если всё упало, пусть вернет 0.0, чтобы ты сразу увидел ошибку в интерфейсе, 
    # а не думал, что всё работает (вместо старых 44.15)
    return 0.0

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
    current_keys = set()
    all_tasks = []

    for f_name, tag in mapping.items():
        if os.path.exists(f_name):
            try:
                df = pd.read_csv(f_name, sep=';', engine='python', encoding='utf-8-sig')
                df.columns = [c.strip().lower() for c in df.columns]
                for idx, row in df.iterrows():
                    m_val, s_val = str(row.get('модель','')).strip(), str(row.get('магазин','')).strip()
                    all_tasks.append((row, tag, idx))
                    current_keys.add(f"{m_val} | {s_val} | {tag}")
            except: pass

    if not all_tasks: return
    is_ui = not ("--parse" in sys.argv)
    if is_ui:
        prog_bar = st.progress(0)
        st_text = st.empty()

    for i, (row, tag, idx) in enumerate(all_tasks):
        m, s, u, sel, c = [str(row.get(k, '')).strip() for k in ['модель','магазин','ссылка','селектор','категория']]
        if is_ui: st_text.text(f"Обновление: {m} ({s})")
        
        if u.startswith('http') and sel and sel != 'nan':
            key = f"{m} | {s} | {tag}"
            try:
                r = requests.get(u, headers=HEADERS, timeout=15)
                soup = BeautifulSoup(r.text, 'lxml')
                el = soup.select_one(sel)
                
                if el:
                    p_val = clean_price(el.text)
                    if p_val:
                        if key not in history: history[key] = []
                        last_p = history[key][-1]['price'] if history[key] else None
                        if last_p != p_val:
                            if last_p is not None:
                                diff = ((p_val - last_p) / last_p) * 100
                                trend = "📈" if p_val > last_p else "📉"
                                send_telegram(f"{trend} <b>Изменение цены!</b>\n\n📱 {m}\n🏪 {s}\n💰 {last_p:,} ₴ → <b>{p_val:,} ₴</b> ({diff:+.1f}%)")
                            history[key].append({'time': now, 'price': p_val, 'cat': c, 'type': tag, 'order': idx})
                            if len(history[key]) > 50: history[key] = history[key][-50:]
                else:
                    # Если селектор не найден (например, сайт выдал капчу)
                    print(f"⚠️ НЕ НАЙДЕН СЕЛЕКТОР: {s} - {m} ({u})")
                    
            except Exception as e:
                # Если сайт не ответил (таймаут или сброс соединения)
                print(f"❌ ОШИБКА ЗАПРОСА: {s} - {m} | Ошибка: {e}")
            
            # ПАУЗА 3.5 секунды, чтобы магазины не банили нас за спам
            time.sleep(3.5)

        if is_ui: prog_bar.progress((i + 1) / len(all_tasks))
    
   # history = {k: v for k, v in history.items() if k in current_keys}
    save_data(HISTORY_FILE, history)
    save_data(LAST_RUN_FILE, {'time': now})
    if is_ui: st_text.empty(); prog_bar.empty()

if "--parse" in sys.argv:
    run_parsing()
    sys.exit(0)

# --- ИНТЕРФЕЙС ---
st.set_page_config(page_title="Мониторинг", layout="wide")
st.markdown("""<style>
    .block-container { padding: 1rem !important; max-width: 1000px !important; margin: 0 auto !important; }
    .table-container { overflow-x: auto; width: 100%; text-align: center; margin-bottom: 20px; }
    table { margin: 0 auto; border-collapse: collapse; width: auto !important; }
    th, td { padding: 4px 10px !important; border: 1px solid #eee !important; font-size: 0.85em; text-align: center !important; }
    tbody tr th { background-color: #f8f9fa !important; font-weight: bold; text-align: left !important; border-right: 2px solid #ddd !important; }
    .uah { color: #1a1a1a; font-weight: 800; display: block; }
    .usd { color: #FF4B4B; font-weight: 700; font-size: 0.9em; }
    .log-line { font-family: monospace; font-size: 0.95em; margin: 2px 0; }
    .log-usd { color: #FF4B4B; font-weight: bold; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = get_minfin_rate()
db, last_run = load_data(HISTORY_FILE), load_data(LAST_RUN_FILE)

c1, c2, c3, c4 = st.columns([1,1.5,1,1])
with c1: user_rate = st.number_input("", value=44.3, label_visibility="collapsed") 
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.write(f"Минфин (продажа): **{minfin_rate}**")
#with c4:
#    if st.button("🗑 СБРОСИТЬ"):
#        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
#        st.rerun()

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
            cats = df_tab['Категория'].unique() 
            sel_cat = st.selectbox("Категория:", cats, key=f"cat_{tag_key}")
            f_df = df_tab[df_tab['Категория'] == sel_cat].copy().sort_values('order')
            
            if not f_df.empty:
                f_df['Display'] = f_df['Цена'].apply(lambda x: f'<span class="uah">{x:,} ₴</span><span class="usd">{int(x/user_rate):,} $</span>')
                f_df['M'] = pd.Categorical(f_df['M'], categories=f_df['M'].unique(), ordered=True)
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=False).fillna('—')
                pivot.index.name = pivot.columns.name = None
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
