import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re

st.set_page_config(page_title="Price Monitor PRO", layout="wide")

# --- СТИЛИЗАЦИЯ ---
st.markdown("""
    <style>
    .uah-price { color: black; font-weight: bold; }
    .usd-price { color: #FF4B4B; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

st.title("📱 Оптовый монитор цен")

# --- БЛОК КУРСА ---
user_rate = st.number_input("Установите ваш курс ($):", value=44.55, step=0.05)

# --- ФУНКЦИЯ ПАРСИНГА ---
def get_price(url, selector):
    if not url or pd.isna(url) or str(url).strip() == "" or str(url) == "ручной ввод":
        return None
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        element = soup.select_one(selector)
        if element:
            clean_price = re.sub(r'\D', '', element.text.strip())
            return int(clean_price)
    except:
        pass
    return None

# --- ГЛАВНАЯ ЛОГИКА ---
tabs = st.tabs(["📦 ОПТ", "🛍️ РОЗНИЦА"])

def run_monitor(file_name):
    # Загружаем данные
    try:
        df = pd.read_csv(file_name, sep=None, engine='python')
    except:
        # Если файла нет, создаем пустой шаблон
        df = pd.DataFrame(columns=['модель', 'магазин', 'ссылка', 'селектор', 'ручная_цена'])

    st.subheader(f"Редактор данных ({file_name})")
    st.write("💡 *Здесь можно менять ссылки или вводить цену вручную в колонку 'ручная_цена'*")
    
    # ИНТЕРФЕЙС РЕДАКТИРОВАНИЯ ТАБЛИЦЫ
    edited_df = st.data_editor(df, num_rows="dynamic", key=file_name, use_container_width=True)
    
    # Кнопка сохранения правок (пока в рамках текущей сессии)
    if st.button(f"💾 Сохранить изменения в {file_name}"):
        edited_df.to_csv(file_name, index=False)
        st.success("Файл обновлен!")

    if st.button(f'🚀 ОБНОВИТЬ И ПЕРЕСЧИТАТЬ {file_name}'):
        results = []
        bar = st.progress(0)
        
        for i, row in edited_df.iterrows():
            # 1. Пробуем взять цену из парсера
            price_uah = get_price(row.get('ссылка'), row.get('селектор'))
            
            # 2. Если парсер не нашел, берем из колонки ручного ввода
            if not price_uah and 'ручная_цена' in edited_df.columns:
                try:
                    price_uah = int(row['ручная_цена'])
                except:
                    price_uah = None

            if price_uah:
                price_usd = round(price_uah / user_rate, 1)
                display_val = f'<span class="uah-price">{price_uah:,} ₴</span> / <span class="usd-price">{price_usd}$</span>'
            else:
                display_val = "—"

            results.append({
                'Модель': row.get('модель', 'Не указано'),
                'Магазин': row.get('магазин', 'Не указано'),
                'Цена': display_val
            })
            bar.progress((i + 1) / len(edited_df))
        
        final_df = pd.DataFrame(results)
        pivot = final_df.pivot_table(index='Модель', columns='Магазин', values='Цена', aggfunc='first')
        st.write("### Результаты мониторинга")
        st.write(pivot.to_html(escape=False), unsafe_allow_html=True)

# Запуск вкладок
with tabs[0]: run_monitor('links.csv')
with tabs[1]: run_monitor('links_r.csv')