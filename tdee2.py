import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import date
import re
from streamlit_gsheets import GSheetsConnection

st.set_page_config(page_title="Meal Tracker + BMR/TDEE", page_icon="🍚", layout="wide")

# --- สร้างการเชื่อมต่อ Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        # ดึงข้อมูลจากแท็บ Daily_Log โดยไม่แคช (ttl=0 เพื่อให้ได้ข้อมูลล่าสุดเสมอ)
        df = conn.read(worksheet="Daily_Log", ttl=0)
        return df.dropna(how="all")
    except Exception:
        return pd.DataFrame(columns=["วันที่", "มื้ออาหาร", "รายการอาหาร", "คาร์บ (g)", "โปรตีน (g)", "ไขมัน (g)", "แคลอรี (kcal)"])

def save_all_data(df):
    # อัปเดตข้อมูลกลับไปยัง Google Sheets
    conn.update(worksheet="Daily_Log", data=df)

def append_entry(meal, item, weight, carbs, protein, fat, calories):
    df = load_data()
    new_entry = pd.DataFrame([{
        "วันที่": str(date.today()),
        "มื้ออาหาร": meal,
        "รายการอาหาร": f"{item} ({weight}g)",
        "คาร์บ (g)": float(carbs),
        "โปรตีน (g)": float(protein),
        "ไขมัน (g)": float(fat),
        "แคลอรี (kcal)": float(calories)
    }])
    updated_df = pd.concat([df, new_entry], ignore_index=True)
    save_all_data(updated_df)

# --- ฟังก์ชันดึงข้อมูลจาก CALFORLIFE ---
@st.cache_data(ttl=3600)
def fetch_nutrition_from_calforlife(food_slug):
    url = f"https://www.calforlife.com/th/calories/{food_slug.strip()}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        res = requests.get(url, headers=headers, timeout=5)
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

# --- หน้าระบบหลัก ---
st.title("🍚 บันทึกโภชนาการ (ฐานข้อมูล Google Sheets)")

tab1, tab2 = st.tabs(["➕ บันทึกอาหารใหม่", "⚙️ จัดการ / แก้ไข / ลบข้อมูล"])

with tab1:
    col_left, col_right = st.columns([1, 1])
    with col_left:
        st.subheader("1. ค้นหาคุณค่าอาหาร (CalForLife)")
        default_foods = {
            "ข้าวสวยสุก (Rice)": {"path": "riec", "c": 28.2, "p": 2.7, "f": 0.3, "cal": 130.0},
            "ข้าวกล้องสุก": {"path": "brown-rice", "c": 23.5, "p": 2.6, "f": 0.9, "cal": 112.0},
            "อกไก่สุก (ลอกหนัง)": {"path": "chicken-breast", "c": 0.0, "p": 31.0, "f": 3.6, "cal": 165.0},
            "ปลาแซลมอนย่าง": {"path": "salmon", "c": 0.0, "p": 22.0, "f": 12.0, "cal": 200.0},
        }
        selected_item = st.selectbox("เลือกรายการยอดนิยม", list(default_foods.keys()))
        custom_slug = st.text_input("หรือระบุ Path CalForLife (เช่น riec)", value=default_foods[selected_item]["path"])
        
        c_100 = default_foods[selected_item]["c"]
        p_100 = default_foods[selected_item]["p"]
        f_100 = default_foods[selected_item]["f"]
        cal_100 = default_foods[selected_item]["cal"]

        if st.button("🔄 ดึงข้อมูลสดจาก CalForLife"):
            res = fetch_nutrition_from_calforlife(custom_slug)
            if res and (res["calories"] > 0 or res["carbs"] > 0):
                c_100, p_100, f_100, cal_100 = res["carbs"], res["protein"], res["fat"], res["calories"]
                st.success(f"ดึงข้อมูลสำเร็จ (ต่อ 100g): คาร์บ {c_100}g | โปรตีน {p_100}g | ไขมัน {f_100}g | {cal_100} kcal")
            else:
                st.warning("ไม่สามารถดึงข้อมูลสดได้ ใช้ค่ามาตรฐานสำรองแทน")

    with col_right:
        st.subheader("2. คำนวณตามน้ำหนักและบันทึก")
        with st.form("add_meal_form", clear_on_submit=True):
            meal_type = st.selectbox("มื้ออาหาร", ["มื้อเช้า", "มื้อกลางวัน", "มื้อเย็น", "ก่อนนอน"])
            food_name = st.text_input("ชื่ออาหาร", value=selected_item)
            weight = st.number_input("น้ำหนักอาหาร (กรัม)", min_value=1.0, value=150.0, step=10.0)

            ratio = weight / 100.0
            calc_c = round(c_100 * ratio, 1)
            calc_p = round(p_100 * ratio, 1)
            calc_f = round(f_100 * ratio, 1)
            calc_cal = round(cal_100 * ratio, 1)

            st.caption(f"สารอาหาร: คาร์บ **{calc_c}g** | โปรตีน **{calc_p}g** | ไขมัน **{calc_f}g** | พลังงาน **{calc_cal} kcal**")
            
            if st.form_submit_button("บันทึกลง Google Sheets"):
                append_entry(meal_type, food_name, weight, calc_c, calc_p, calc_f, calc_cal)
                st.success(f"บันทึกสำเร็จ: {food_name} ({weight}g)")
                st.rerun()

with tab2:
    st.subheader("จัดการรายการใน Google Sheets")
    df = load_data()
    
    if df.empty or len(df) == 0:
        st.info("ยังไม่มีข้อมูลในชีต")
    else:
        st.dataframe(df, use_container_width=True)
        col_opt1, col_opt2 = st.columns(2)

        with col_opt1:
            st.markdown("### ✏️ แก้ไขข้อมูล")
            row_to_edit = st.selectbox("เลือกแถว (Index) ที่ต้องการแก้ไข", df.index.tolist(), key="edit_selector")
            current_row = df.loc[row_to_edit]

            with st.form("edit_form"):
                new_date = st.text_input("วันที่", value=str(current_row["วันที่"]))
                meal_options = ["มื้อเช้า", "มื้อกลางวัน", "มื้อเย็น", "ก่อนนอน"]
                current_meal_idx = meal_options.index(current_row["มื้ออาหาร"]) if current_row["มื้ออาหาร"] in meal_options else 0
                new_meal = st.selectbox("มื้ออาหาร", meal_options, index=current_meal_idx)
                new_item = st.text_input("รายการอาหาร", value=str(current_row["รายการอาหาร"]))
                new_c = st.number_input("คาร์บ (g)", value=float(current_row["คาร์บ (g)"]), step=1.0)
                new_p = st.number_input("โปรตีน (g)", value=float(current_row["โปรตีน (g)"]), step=1.0)
                new_f = st.number_input("ไขมัน (g)", value=float(current_row["ไขมัน (g)"]), step=1.0)
                new_cal = st.number_input("แคลอรี (kcal)", value=float(current_row["แคลอรี (kcal)"]), step=1.0)

                if st.form_submit_button("บันทึกการแก้ไขไปยัง Google Sheets"):
                    df.loc[row_to_edit] = [new_date, new_meal, new_item, new_c, new_p, new_f, new_cal]
                    save_all_data(df)
                    st.success("อัปเดตข้อมูลเรียบร้อยแล้ว!")
                    st.rerun()

        with col_opt2:
            st.markdown("### 🗑️ ลบข้อมูล")
            row_to_delete = st.selectbox("เลือกแถว (Index) ที่ต้องการลบ", df.index.tolist(), key="del_selector")
            target_entry = df.loc[row_to_delete]
            st.write(f"รายการที่เลือก: **{target_entry['มื้ออาหาร']} - {target_entry['รายการอาหาร']}**")

            if st.button("ยืนยันการลบรายการนี้", type="primary"):
                df = df.drop(index=row_to_delete).reset_index(drop=True)
                save_all_data(df)
                st.success("ลบรายการออกจาก Google Sheets เรียบร้อยแล้ว!")
                st.rerun()

# --- สรุปภาพรวมประจำวัน ---
st.divider()
st.subheader("📊 สรุปภาพรวมประจำวันเทียบเป้าหมาย")
df = load_data()
if not df.empty and len(df) > 0:
    today_str = str(date.today())
    today_df = df[df["วันที่"] == today_str]
    if not today_df.empty:
        t_cal = pd.to_numeric(today_df["แคลอรี (kcal)"]).sum()
        t_c = pd.to_numeric(today_df["คาร์บ (g)"]).sum()
        t_p = pd.to_numeric(today_df["โปรตีน (g)"]).sum()
        t_f = pd.to_numeric(today_df["ไขมัน (g)"]).sum()
        
        diff = t_cal - target_calories
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("พลังงานรวมวันนี้", f"{t_cal:.0f} kcal", f"{diff:+.0f} จากเป้าหมาย {target_calories} kcal")
        c2.metric("คาร์บรวม", f"{t_c:.1f} g")
        c3.metric("โปรตีนรวม", f"{t_p:.1f} g")
        c4.metric("ไขมันรวม", f"{t_f:.1f} g")
    else:
        st.write("ยังไม่มีรายการอาหารที่บันทึกสำหรับวันนี้")
