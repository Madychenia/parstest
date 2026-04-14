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
        # Официальный открытый API ПриватБанка (курс в отделениях)
        url = "https://api.privatbank.ua/p24api/pubinfo?exchange&coursid=5"
        
        r = requests.get(url, timeout=10)
        data = r.json()
        
        for item in data:
            if item['ccy'] == 'USD':
                # Берем курс продажи
                new_rate = float(item['sale'])
                print(f"✅ Курс USD (ПриватБанк) успешно получен: {new_rate}")
                return new_rate
                
    except Exception as e:
        print(f"❌ Ошибка получения курса: {e}")
    
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
    
    history = {k: v for k, v in history.items() if k in current_keys}
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
    
    /* НОВЫЕ СТИЛИ ДЛЯ ЛУЧШЕЙ ЦЕНЫ */
    td:has(.best-price) { background-color: #f0fdf4 !important; border: 2px solid #22c55e !important; }
</style>""", unsafe_allow_html=True)

st.title("📱 Мониторинг")
minfin_rate = get_minfin_rate()
db, last_run = load_data(HISTORY_FILE), load_data(LAST_RUN_FILE)

c1, c2, c3, c4 = st.columns([1,1.5,1,1])
with c1: user_rate = st.number_input("", value=minfin_rate, step=0.1, label_visibility="collapsed")
with c2: 
    st.write(f"Обновлено: **{last_run.get('time', '—')}**")
    st.write(f"Минфин (продажа): **{minfin_rate}**")
with c3:
    # Вот эта новая строчка!
    st.markdown("💡 Предложить поставщика:<br>[**@madychenia**](http://t.me/madychenia)", unsafe_allow_html=True)
    
#with c4:
#    if st.button("🗑 СБРОСИТЬ"):
#        if os.path.exists(HISTORY_FILE): os.remove(HISTORY_FILE)
#        st.rerun()

# Распаковываем вкладки в отдельные переменные
t_used, t_new, t_analytics = st.tabs(["Used (Б/У)", "New (Новые)", "📊 Аналитика"])
tags = ['u', 'n']

for i, tab_ui in enumerate([t_used, t_new]):
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
                # 1. Находим минимальную цену для каждой модели
                min_prices = f_df.groupby('M')['Цена'].transform('min')
                f_df['is_min'] = f_df['Цена'] == min_prices
                
                # 2. Формируем ячейки (добавляем класс best-price для минимума)
                def format_cell(row):
                    uah = f"{row['Цена']:,} ₴"
                    usd = f"{int(row['Цена'] / user_rate):,} $"
                    if row['is_min']:
                        return f'<div class="best-price"><span class="uah">{uah}</span><span class="usd">{usd}</span></div>'
                    else:
                        return f'<div><span class="uah">{uah}</span><span class="usd">{usd}</span></div>'

                f_df['Display'] = f_df.apply(format_cell, axis=1)
                
                # 3. Собираем таблицу
                # Читаем эталонный порядок моделей напрямую из твоих CSV файлов
                master_order = []
                for file in ['links.csv', 'links_new.csv']:
                    if os.path.exists(file):
                        with open(file, 'r', encoding='utf-8') as f:
                            for line in f:
                                parts = line.split(';')
                                if len(parts) > 0:
                                    m = parts[0].strip()
                                    # Добавляем название модели, если его еще нет в списке
                                    if m and m != 'Модель' and m not in master_order:
                                        master_order.append(m)
                
                # Оставляем в списке только те модели, которые есть в текущей выбранной категории
                cat_models = [m for m in master_order if m in f_df['M'].values]
                
                # Принудительно задаем порядок строк
                f_df['M'] = pd.Categorical(f_df['M'], categories=cat_models, ordered=True)
                
                # Генерируем таблицу (sort=True теперь будет использовать наш порядок из Categorical)
                pivot = f_df.pivot_table(index='M', columns='S', values='Display', aggfunc='first', sort=True).fillna('—')
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
                            
# --- Вкладка 3: АНАЛИТИКА ---
with t_analytics:
    st.markdown("### 📈 Динамика рынка и скидки")
    
    stat_data = []
    for k, logs in db.items():
        parts = k.split(' | ')
        if len(parts) >= 2:
            model, store = parts[0], parts[1]
            curr_p = logs[-1]['price']
            start_p = logs[0]['price']
            prev_p = logs[-2]['price'] if len(logs) > 1 else curr_p
            
            stat_data.append({
                'Модель': model,
                'Магазин': store,
                'Цена ₴': curr_p,
                'Цена $': int(curr_p / minfin_rate),
                'Всего ₴': curr_p - start_p,
                'Всего $': int((curr_p - start_p) / minfin_rate),
                'Изменение ₴': curr_p - prev_p
            })

    if stat_data:
        df_stat = pd.DataFrame(stat_data)

        # --- БЛОК 1: Метрики (уплотненные) ---
        total_drops = len(df_stat[df_stat['Всего ₴'] < 0])
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("📉 Подешевело", f"{total_drops} шт.")
        
        if total_drops > 0:
            best = df_stat.loc[df_stat['Всего ₴'].idxmin()]
            c2.metric(f"🔥 Рекорд ({best['Магазин']})", f"{best['Всего ₴']:,} ₴", f"{best['Всего $']} $", delta_color="inverse")
            
            store_drops = df_stat[df_stat['Всего ₴'] < 0].groupby('Магазин')['Всего ₴'].sum()
            c3.metric("👑 Агрессор", store_drops.idxmin(), f"{store_drops.min():,.0f} ₴", delta_color="inverse")
            
            avg_d = df_stat[df_stat['Всего ₴'] < 0]['Всего ₴'].mean()
            c4.metric("📊 Средний чек", f"{avg_d:,.0f} ₴")
        
        st.divider()

        # --- БЛОК 2: Таблицы рейтинга ---
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### 🛒 Рейтинг щедрости")
            # Меняем 🏷 на латинское слово Count
            store_agg = df_stat[df_stat['Всего ₴'] < 0].groupby('Магазин').agg(
                Count=('Всего ₴', 'count'), 
                Сумма_uah=('Всего ₴', 'sum')
            ).reset_index().sort_values('Сумма_uah')
            
            store_agg['Сумма_usd'] = (store_agg['Сумма_uah'] / minfin_rate).astype(int)
            
            st.dataframe(store_agg, column_config={
                "Магазин": "🏪 Магазин", 
                "Count": "🏷 Скидок", # А вот тут уже возвращаем эмодзи для красоты
                "Сумма_uah": st.column_config.NumberColumn("💸 Всего ₴", format="%d ₴"),
                "Сумма_usd": st.column_config.NumberColumn("🏦 Всего $", format="%d $")
            }, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("#### 🚀 Топ-10 падений")
            top_10 = df_stat[df_stat['Всего ₴'] < 0].sort_values('Всего ₴').head(10)
            st.dataframe(top_10[['Модель', 'Магазин', 'Всего ₴', 'Всего $']], column_config={
                "Всего ₴": st.column_config.NumberColumn("📉 Скидка ₴", format="%d ₴"),
                "Всего $": st.column_config.NumberColumn("📉 Скидка $", format="%d $")
            }, hide_index=True, use_container_width=True)

        st.divider()

        # --- БЛОК 3: ПОЛНАЯ ДИНАМИКА С ПОДСВЕТКОЙ ---
        st.markdown("#### 📋 Полная динамика рынка")
        
        # Функция для раскраски
        def style_dynamic(row):
            styles = [''] * len(row)
            # Подсветка падения (Всего ₴ - индекс 4, Изменение ₴ - индекс 6)
            if row['Всего ₴'] < 0: styles[4] = 'color: #22c55e; font-weight: bold'
            elif row['Всего ₴'] > 0: styles[4] = 'color: #ef4444; font-weight: bold'
            
            if row['Изменение ₴'] < 0: styles[6] = 'background-color: #f0fdf4; color: #22c55e; font-weight: bold'
            elif row['Изменение ₴'] > 0: styles[6] = 'background-color: #fef2f2; color: #ef4444; font-weight: bold'
            
            return styles

        # Находим лучшие цены для каждой модели
        min_prices = df_stat.groupby('Модель')['Цена ₴'].transform('min')
        df_stat['is_best'] = df_stat['Цена ₴'] == min_prices

        def highlight_best_price(s):
            return ['background-color: #dcfce7' if s.is_best and (name in ['Цена ₴', 'Цена $']) else '' for name in s.index]

        styled_df = df_stat.drop(columns=['is_best']).style\
            .apply(style_dynamic, axis=1)\
            .apply(highlight_best_price, axis=1)

        st.dataframe(styled_df, column_config={
            "Модель": "📱 Модель", "Магазин": "🏪 Магазин",
            "Цена ₴": st.column_config.NumberColumn("💰 Цена ₴", format="%d ₴"),
            "Цена $": st.column_config.NumberColumn("💵 Цена $", format="%d $"),
            "Всего ₴": st.column_config.NumberColumn("🏁 Весь срок", format="%d ₴"),
            "Всего $": st.column_config.NumberColumn("🏦 Весь срок $", format="%d $"),
            "Изменение ₴": st.column_config.NumberColumn("🔄 Последнее", format="%d ₴"),
        }, hide_index=True, use_container_width=True)
        
    else:
        st.info("Пока нет истории для аналитики.")
