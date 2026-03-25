import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

# Настройки страницы
st.set_page_config(page_title="iPhone Price Monitor", layout="wide", initial_sidebar_state="collapsed")

# Стили для таблицы
st.markdown("""
    <style>
    [data-testid="stSidebar"] { display: none; }
    .uah { color: black; font-weight: bold; }
    .usd { color: #FF4B4B; font-weight: bold; }
    td { text-align: center !important; padding: 12px !important; }
    th { background-color: #f0f2f6 !important; text-align: center !important; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Мониторинг цен: iPhone")

# --- УПРАВЛЕНИЕ ---
col_rate, col_time = st.columns([2, 3])
with col_rate:
    user_rate = st.number_input("Введите курс для расчета ($):", value=44.55, step=0.01)
with col_time:
    st.write(f"Последнее обновление: **{datetime.now().strftime('%H:%M:%S')}**")

# --- ФУНКЦИЯ ПАРСИНГА ТОВАРОВ ---
@st.cache_data(ttl=3600)
def fetch_prices(file_name, rate):
    try:
        # Читаем CSV и чистим названия колонок
        df = pd.read_csv(file_name, sep=None, engine='python', encoding='utf-8-sig')
        df.columns = [str(c).strip().lower() for c in df.columns]
        
        results = []
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        
        for _, row in df.iterrows():
            price_uah = None
            url = str(row.get('ссылка', '')).strip()
            selector = str(row.get('селектор', '')).strip()
            
            if url.startswith('http'):
                try:
                    r = requests.get(url, headers=headers, timeout=10)
                    soup = BeautifulSoup(r.text, 'html.parser')
                    el = soup.select_one(selector)
                    if el:
                        # Убираем всё, кроме цифр
                        digits = re.sub(r'\D', '', el.text.strip())
                        if digits:
                            price_uah = int(digits)
                except:
                    pass

            # Формируем отображение цены
            if price_uah:
                price_usd = round(price_uah / rate, 1)
                display_val = f'<span class="uah">{price_uah:,} ₴</span><br><span class="usd">{price_usd}$</span>'
            else:
                display_val = "—"
            
            results.append({
                'Модель': row.get('модель', 'Неизвестно'),
                'Магазин': row.get('магазин', '—'),
                'Цена': display_val
            })
            
        return pd.DataFrame(results)
    except Exception as e:
        st.error(f"Ошибка при чтении файла: {e}")
        return pd.DataFrame()

# --- ВЫВОД ДАННЫХ ---
data = fetch_prices('links.csv', user_rate)

if not data.empty:
    # Определяем серию (например, 14, 15, 16) для фильтра
    data['Серия'] = data['Модель'].apply(lambda x: re.search(r'\d+', str(x)).group() if re.search(r'\d+', str(x)) else "Прочее")
    series_list = sorted(data['Серия'].unique(), key=lambda x: int(x) if str(x).isdigit() else 999)
    
    selected_series = st.selectbox("Выберите серию iPhone:", series_list, index=len(series_list)-1)
    
    # Фильтруем и строим таблицу
    filtered = data[data['Серия'] == selected_series]
    
    # Убираем дубликаты перед сводной таблицей
    pivot_df = filtered.drop_duplicates(subset=['Модель', 'Магазин'])
    pivot_table = pivot_df.pivot(index='Модель', columns='Магазин', values='Цена').fillna("—")
    
    st.write(pivot_table.to_html(escape=False), unsafe_allow_html=True)
else:
    st.warning("Файл 'links.csv' пуст или не найден. Проверьте репозиторий.")

if st.button("♻️ ОБНОВИТЬ ЦЕНЫ"):
    st.cache_data.clear()
    st.rerun()
