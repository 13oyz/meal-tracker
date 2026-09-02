import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time

# --- Google Apps Script Web App URL ---
APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzl_SLzqcTmWCLtDFtyIBKRS4m8LYOOoAozlIwqKp-ArKHCIw0IvfgM0HYvZXVI28vjZA/exec"

st.set_page_config(page_title="Meal Tracker + BMR/TDEE", page_icon="🍚", layout="wide")

# --- ฟังก์ชันจัดการข้อมูลผ่าน Google Apps Script ---
def load_data():
    try:
        url = f"{APPS_SCRIPT_URL}?t={int(time.time())}"
        res = requests.get(url, allow_redirects=True, timeout=12)
        if res.status_code == 200:
            data = res.json()
            if data and isinstance(data, list):
                df = pd.DataFrame(data)
                num_cols = ["คาร์บ (g)", "โปรตีน (g)", "ไขมัน (g)", "แคลอรี (kcal)"]
                for col in num_cols:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
                return df
    except Exception as e:
        st.warning(f"ยังเชื่อมต่อดึงข้อมูลจากชีตไม่ได้: {e}")
        
    return pd.DataFrame(columns=["วันที่", "มื้ออาหาร", "รายการอาหาร", "คาร์บ (g)", "โปรตีน (g)", "ไขมัน (g)", "แคลอรี (kcal)"])

def append_entry(meal, item, weight, carbs, protein, fat, calories):
    bkk_now_str = pd.Timestamp.now(tz="Asia/Bangkok").strftime("%Y-%m-%d %H:%M")
    payload = {
        "action": "append",
        "date": bkk_now_str,
        "meal": meal,
        "item": f"{item} ({weight}g)",
        "carbs": float(carbs),
        "protein": float(protein),
        "fat": float(fat),
        "calories": float(calories)
    }
    try:
        res = requests.post(APPS_SCRIPT_URL, json=payload, allow_redirects=True, timeout=12)
        if res.status_code == 200:
            st.success(f"✅ บันทึกสำเร็จ: {item} ({weight}g)")
        else:
            st.error("บันทึกไม่สำเร็จ ตรวจสอบสิทธิ์ Apps Script")
    except Exception as e:
        st.error(f"เกิดข้อผิดพลาดในการส่งข้อมูล: {e}")

# --- ฟังก์ชันดึงข้อมูลจาก CALFORLIFE ---
@st.cache_data(ttl=3600)
def fetch_nutrition_from_calforlife(food_slug):
    url = f"https://www.calforlife.com/th/calories/{food_slug.strip()}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=6)
        if res.status_code != 200:
            return None
        soup = BeautifulSoup(res.text, "html.parser")
        text = soup.get_text()
        
        base = {"calories": 0.0, "carbs": 0.0, "protein": 0.0, "fat": 0.0}
        cal = re.search(r"(\d+(\.\d+)?)\s*(กิโลแคลอรี่|กิโลแคลอรี|kcal)", text, re.IGNORECASE)
        c = re.search(r"คาร์โบไฮเดรต\s*[:\-]?\s*(\d+(\.\d+)?)\s*ก", text)
        p = re.search(r"โปรตีน\s*[:\-]?\s*(\d+(\.\d+)?)\s*ก", text)
        f = re.search(r"ไขมัน\s*[:\-]?\s*(\d+(\.\d+)?)\s*ก", text)
        
        if cal: base["calories"] = float(cal.group(1))
        if c: base["carbs"] = float(c.group(1))
        if p: base["protein"] = float(p.group(1))
        if f: base["fat"] = float(f.group(1))
        return base
    except Exception:
        return None

# --- ฟังก์ชันดึงข้อมูลจาก OPEN FOOD FACTS API ---
@st.cache_data(ttl=3600)
def fetch_nutrition_from_openfoodfacts(query):
    query = query.strip()
    headers = {"User-Agent": "MealTrackerApp - Streamlit - Version1.0"}
    try:
        if query.isdigit():
            url = f"https://world.openfoodfacts.org/api/v0/product/{query}.json"
            res = requests.get(url, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") == 1:
                    product = data.get("product", {})
                    nutriments = product.get("nutriments", {})
                    name = product.get("product_name_th") or product.get("product_name") or query
                    cal = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal") or 0.0
                    c = nutriments.get("carbohydrates_100g") or 0.0
                    p = nutriments.get("proteins_100g") or 0.0
                    f = nutriments.get("fat_100g") or 0.0
                    return [{"name": name, "calories": float(cal), "carbs": float(c), "protein": float(p), "fat": float(f)}]
        else:
            url = "https://world.openfoodfacts.org/cgi/search.pl"
            params = {
                "search_terms": query,
                "search_simple": 1,
                "action": "process",
                "json": 1,
                "page_size": 5
            }
            res = requests.get(url, params=params, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                products = data.get("products", [])
                results = []
                for p in products:
                    name = p.get("product_name_th") or p.get("product_name") or p.get("brands") or "ไม่ทราบชื่อ"
                    nutriments = p.get("nutriments", {})
                    cal = nutriments.get("energy-kcal_100g") or nutriments.get("energy-kcal") or 0.0
                    c = nutriments.get("carbohydrates_100g") or 0.0
                    prot = nutriments.get("proteins_100g") or 0.0
                    fat = nutriments.get("fat_100g") or 0.0
                    if cal > 0 or prot > 0 or c > 0:
                        results.append({
                            "name": name,
                            "calories": float(cal),
                            "carbs": float(c),
                            "protein": float(prot),
                            "fat": float(fat)
                        })
                return results
    except Exception:
        pass
    return None

# --- SIDEBAR: คำนวณ BMR & TDEE ---
with st.sidebar:
    st.header("⚙️ คำนวณ BMR / TDEE")
    gender = st.radio("เพศ", ["ชาย", "หญิง"], horizontal=True)
    age = st.number_input("อายุ (ปี)", min_value=15, max_value=100, value=30, step=1)
    height = st.number_input("ส่วนสูง (ซม.)", min_value=100, max_value=230, value=180, step=1)
    weight_body = st.number_input("น้ำหนักตัว (กก.)", min_value=30.0, max_value=200.0, value=74.0, step=0.5)
    
    activity_levels = {
        "นั่งทำงานอยู่กับที่ (แทบไม่ออกกำลังกาย)": 1.2,
        "ออกกำลังกายเบา (1–3 วัน/สัปดาห์)": 1.375,
        "ออกกำลังกายปานกลาง (3–5 วัน/สัปดาห์)": 1.55,
        "ออกกำลังกายหนัก (6–7 วัน/สัปดาห์)": 1.725,
        "ออกกำลังกายหนักมาก / ใช้แรงงาน": 1.9
    }
    activity = st.selectbox("ระดับกิจกรรมประจำวัน", list(activity_levels.keys()), index=2)
    multiplier = activity_levels[activity]
    
    if gender == "ชาย":
        bmr = (10 * weight_body) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight_body) + (6.25 * height) - (5 * age) - 161
        
    tdee = bmr * multiplier
    
    goal = st.selectbox("เป้าหมาย", [
        "เพิ่มน้ำหนัก / กล้ามเนื้อ (Lean Bulk +10-15%)",
        "รักษาน้ำหนัก (Maintenance)",
        "ลดไขมัน (Deficit -15-20%)"
    ])
    
    if "Lean Bulk" in goal:
        target_calories = round(tdee * 1.12)
    elif "ลดไขมัน" in goal:
        target_calories = round(tdee * 0.82)
    else:
        target_calories = round(tdee)
        
    st.divider()
    st.metric("BMR (เผาผลาญพื้นฐาน)", f"{bmr:.0f} kcal")
    st.metric("TDEE (ใช้จริงต่อวัน)", f"{tdee:.0f} kcal")
    st.success(f"🎯 **เป้าหมาย: {target_calories} kcal/วัน**")

# --- หน้าต่างหลัก ---
st.title("🍚 บันทึกโภชนาการ (Google Sheets Sync)")

df = load_data()

tab1, tab2 = st.tabs(["➕ บันทึกอาหารใหม่", "📊 รายการทั้งหมดในชีต"])

# กำหนด Session State เริ่มต้นสำหรับจัดเก็บอาหารที่เลือก
if "food_name" not in st.session_state:
    st.session_state["food_name"] = "ข้าวสวยสุก (Rice)"
if "c_100" not in st.session_state:
    st.session_state["c_100"] = 28.2
if "p_100" not in st.session_state:
    st.session_state["p_100"] = 2.7
if "f_100" not in st.session_state:
    st.session_state["f_100"] = 0.3
if "cal_100" not in st.session_state:
    st.session_state["cal_100"] = 130.0

with tab1:
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. ค้นหาคุณค่าอาหาร")
        source = st.radio("เลือกแหล่งข้อมูล", ["เมนูยอดนิยม / CalForLife", "Open Food Facts (นม/ของ 7-11/บาร์โค้ด)"], horizontal=True)
        
        if source == "เมนูยอดนิยม / CalForLife":
            default_foods = {
                "ข้าวสวยสุก (Rice)": {"path": "riec", "c": 28.2, "p": 2.7, "f": 0.3, "cal": 130.0},
                "ข้าวกล้องสุก": {"path": "brown-rice", "c": 23.5, "p": 2.6, "f": 0.9, "cal": 112.0},
                "อกไก่สุก (ลอกหนัง)": {"path": "chicken-breast", "c": 0.0, "p": 31.0, "f": 3.6, "cal": 165.0},
                "ไข่ต้ม (1 ฟอง ~50g)": {"path": "boiled-egg", "c": 0.6, "p": 6.3, "f": 5.3, "cal": 77.0},
                "ไข่ดาว (1 ฟอง)": {"path": "fried-egg", "c": 0.4, "p": 6.3, "f": 14.8, "cal": 160.0},
                "ปลาแซลมอนย่าง": {"path": "salmon", "c": 0.0, "p": 22.0, "f": 12.0, "cal": 200.0},
                "กำหนดเอง / ระบุ Path เอง": {"path": "", "c": 0.0, "p": 0.0, "f": 0.0, "cal": 0.0}
            }
            
            selected_item = st.selectbox("เลือกรายการอาหารยอดนิยม", list(default_foods.keys()))
            
            if selected_item != "กำหนดเอง / ระบุ Path เอง":
                default_slug = default_foods[selected_item]["path"]
                st.session_state["food_name"] = selected_item
                st.session_state["c_100"] = default_foods[selected_item]["c"]
                st.session_state["p_100"] = default_foods[selected_item]["p"]
                st.session_state["f_100"] = default_foods[selected_item]["f"]
                st.session_state["cal_100"] = default_foods[selected_item]["cal"]
            else:
                default_slug = ""

            custom_slug = st.text_input("ระบุ Path ภาษาอังกฤษจาก calforlife.com/th/calories/[ชื่อตรงนี้]", value=default_slug)
            
            if st.button("🔄 ดึงข้อมูลสดจาก CalForLife"):
                if custom_slug:
                    res = fetch_nutrition_from_calforlife(custom_slug)
                    if res and (res["calories"] > 0 or res["carbs"] > 0 or res["protein"] > 0):
                        st.session_state["food_name"] = custom_slug
                        st.session_state["c_100"] = res["carbs"]
                        st.session_state["p_100"] = res["protein"]
                        st.session_state["f_100"] = res["fat"]
                        st.session_state["cal_100"] = res["calories"]
                        st.success(f"ดึงสำเร็จ (ต่อ 100g): คาร์บ {res['carbs']}g | โปรตีน {res['protein']}g | ไขมัน {res['fat']}g | {res['calories']} kcal")
                    else:
                        st.warning("ดึงข้อมูลไม่สำเร็จ กรุณาตรวจสอบชื่อ Path บนเว็บ calforlife.com")
                else:
                    st.warning("กรุณาระบุ Path ก่อนกดค้นหา")
                    
        else:
            off_query = st.text_input("พิมพ์ชื่อสินค้า หรือเลขบาร์โค้ด (เช่น meiji protein, dutch mill, นมสด)", value="")
            if st.button("🔍 ค้นหา Open Food Facts"):
                if off_query:
                    off_results = fetch_nutrition_from_openfoodfacts(off_query)
                    if off_results:
                        st.session_state["off_results"] = off_results
                    else:
                        st.warning("ไม่พบสินค้าใน Open Food Facts")
                else:
                    st.warning("กรุณากรอกคำค้นหา")

            if "off_results" in st.session_state and st.session_state["off_results"]:
                options = {f"{item['name']} ({item['calories']:.0f} kcal / 100g)": item for item in st.session_state["off_results"]}
                chosen_label = st.selectbox("เลือกสินค้าที่ตรงกัน:", list(options.keys()))
                chosen_item = options[chosen_label]
                
                st.session_state["food_name"] = chosen_item["name"]
                st.session_state["c_100"] = chosen_item["carbs"]
                st.session_state["p_100"] = chosen_item["protein"]
                st.session_state["f_100"] = chosen_item["fat"]
                st.session_state["cal_100"] = chosen_item["calories"]
                st.info(f"คุณค่าต่อ 100g: คาร์บ {chosen_item['carbs']}g | โปรตีน {chosen_item['protein']}g | ไขมัน {chosen_item['fat']}g | {chosen_item['calories']} kcal")

    with col_right:
        st.subheader("2. คำนวณตามน้ำหนักและบันทึก")
        
        c_100 = st.session_state["c_100"]
        p_100 = st.session_state["p_100"]
        f_100 = st.session_state["f_100"]
        cal_100 = st.session_state["cal_100"]
        
        with st.form("add_meal_form", clear_on_submit=True):
            meal_type = st.selectbox("มื้ออาหาร", ["มื้อเช้า", "มื้อกลางวัน", "มื้อเย็น", "ก่อนนอน"])
            food_name = st.text_input("ชื่ออาหาร", value=st.session_state["food_name"])
            weight = st.number_input("ปริมาณอาหาร/เครื่องดื่ม (กรัม หรือ มล.)", min_value=1.0, value=100.0, step=10.0)

            ratio = weight / 100.0
            calc_c = round(c_100 * ratio, 1)
            calc_p = round(p_100 * ratio, 1)
            calc_f = round(f_100 * ratio, 1)
            calc_cal = round(cal_100 * ratio, 1)

            st.caption(f"สารอาหาร: คาร์บ **{calc_c}g** | โปรตีน **{calc_p}g** | ไขมัน **{calc_f}g** | พลังงาน **{calc_cal} kcal**")
            
            if st.form_submit_button("บันทึกลง Google Sheets"):
                append_entry(meal_type, food_name, weight, calc_c, calc_p, calc_f, calc_cal)
                time.sleep(1)
                st.rerun()

with tab2:
    col_t2_head, col_t2_btn = st.columns([5, 1])
    with col_t2_head:
        st.subheader("ตารางข้อมูลทั้งหมดจาก Google Sheets")
    with col_t2_btn:
        if st.button("🔄 รีเฟรชชีต"):
            st.rerun()

    if df.empty or len(df) == 0:
        st.info("ยังไม่พบข้อมูลจาก Google Sheets (กรุณาตรวจชื่อแท็บชีตด้านล่างว่าชื่อ Daily_Log หรือไม่)")
    else:
        st.dataframe(df, use_container_width=True)

# --- สรุปภาพรวมประจำวันเทียบเป้าหมาย ---
st.divider()
st.subheader("📊 สรุปภาพรวมประจำวันเทียบเป้าหมาย")

if not df.empty and len(df) > 0 and "วันที่" in df.columns:
    dates_dt = pd.to_datetime(df["วันที่"], errors="coerce")
    if dates_dt.dt.tz is not None:
        dates_bkk = dates_dt.dt.tz_convert("Asia/Bangkok")
    else:
        dates_bkk = dates_dt.dt.tz_localize("UTC", ambiguous='NaT', nonexistent='NaT').dt.tz_convert("Asia/Bangkok")
        
    df["clean_date"] = dates_bkk.dt.strftime("%Y-%m-%d")
    df["เวลา"] = dates_bkk.dt.strftime("%H:%M น.")
    
    today_bkk = pd.Timestamp.now(tz="Asia/Bangkok").strftime("%Y-%m-%d")
    today_df = df[df["clean_date"] == today_bkk]
    
    if not today_df.empty:
        t_cal = today_df["แคลอรี (kcal)"].sum()
        t_c = today_df["คาร์บ (g)"].sum()
        t_p = today_df["โปรตีน (g)"].sum()
        t_f = today_df["ไขมัน (g)"].sum()
        
        remaining_cal = target_calories - t_cal
        
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("กินไปแล้ววันนี้", f"{t_cal:.0f} kcal")
        c2.metric("ยังกินได้อีก (คงเหลือ)", f"{remaining_cal:.0f} kcal", f"เป้าหมาย {target_calories} kcal")
        c3.metric("คาร์บรวม", f"{t_c:.1f} g")
        c4.metric("โปรตีนรวม", f"{t_p:.1f} g")
        c5.metric("ไขมันรวม", f"{t_f:.1f} g")
        
        st.write("📋 **รายการอาหารที่กินไปแล้ววันนี้:**")
        cols_order = ["เวลา", "มื้ออาหาร", "รายการอาหาร", "คาร์บ (g)", "โปรตีน (g)", "ไขมัน (g)", "แคลอรี (kcal)"]
        show_cols = [c for c in cols_order if c in today_df.columns]
        st.dataframe(today_df[show_cols], use_container_width=True)
    else:
        st.write(f"ยังไม่มีรายการอาหารที่บันทึกสำหรับวันที่วันนี้ ({today_bkk})")
        st.caption("ข้อมูลล่าสุดที่พบล่าสุดในชีต:")
        st.dataframe(df.tail(5), use_container_width=True)
else:
    st.write("ยังไม่มีข้อมูลจากชีต")
