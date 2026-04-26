import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

# ==========================================
# 🔧 核心防禦函數區
# ==========================================
def split_and_distribute(df, target_col, hours_col):
    """安全地均分時數，若欄位不存在則跳過"""
    df = df.copy()
    # 安全檢查：若目標欄位或時數欄位不存在，直接回傳
    if target_col not in df.columns or hours_col not in df.columns:
        return df
    
    df[target_col] = df[target_col].astype(str).replace(['nan', 'None', ''], 'Unknown')
    
    def safe_split(val):
        if val == 'Unknown': return ['Unknown']
        # 支援多種分隔符號
        parts = re.split(r'[/,;\n\r]+', str(val))
        parts = [p.strip() for p in parts if p.strip()]
        return parts if parts else ['Unknown']
    
    df['__split_list'] = df[target_col].apply(safe_split)
    df['__split_count'] = df['__split_list'].apply(len)
    
    # 執行均分
    df[hours_col] = df[hours_col] / df['__split_count']
    df = df.explode('__split_list')
    df[target_col] = df['__split_list']
    
    df = df.drop(columns=['__split_list', '__split_count'])
    return df

def get_actual_col(df, aliases):
    """自動偵測最接近的標頭 (不分大小寫、去空格)"""
    for alias in aliases:
        # 1. 完全匹配
        if alias in df.columns: return alias
        # 2. 模糊匹配 (去空格後比對)
        for col in df.columns:
            if str(col).strip().lower() == str(alias).strip().lower():
                return col
    return None

# ==========================================
# 🌟 數據聚合函數
# ==========================================
def aggregate_data(df, group_by_cols, hours_col, show_breakdown=True, is_eng=False):
    if isinstance(group_by_cols, str): group_by_cols = [group_by_cols]
    
    # 確保所有需要的欄位都存在於 DataFrame
    for col in group_by_cols + [hours_col]:
        if col not in df.columns:
            return pd.DataFrame()
        
    txt_click_expand = "(Click to expand)" if is_eng else "(點擊展開)"
    txt_total = "Total" if is_eng else "總計"
    txt_no_detail = "No details provided" if is_eng else "無詳細說明"
    
    breakdown_col = f"⏱️ {hours_col} {txt_click_expand}"
    
    if df.empty: return pd.DataFrame()
        
    res_hours = df.groupby(group_by_cols)[hours_col].sum().reset_index()
    
    if show_breakdown:
        def format_hours(g):
            total = g[hours_col].sum()
            details = [f"{txt_total}: {total:.2f} hrs"]
            if 'Team' in g.columns:
                for team in ['CSO', 'Gchip', 'Other / Unassigned']:
                    t_hrs = g[g['Team'] == team][hours_col].sum()
                    if t_hrs > 0: details.append(f"  ├ {team}: {t_hrs:.2f} hrs")
            return '\n'.join(details)
        
        res_breakdown = df.groupby(group_by_cols).apply(format_hours).reset_index(name=breakdown_col)
        res_hours = pd.merge(res_hours, res_breakdown, on=group_by_cols)

    # 處理任務細節
    def format_details(g):
        if 'Task Details' not in g.columns: return txt_no_detail
        tasks = g['Task Details'].unique()
        valid = [str(i).strip() for i in tasks if pd.notna(i) and str(i).strip() != '']
        return '\n'.join([f"• {item}" for item in valid]) if valid else txt_no_detail
        
    res_details = df.groupby(group_by_cols).apply(format_details).reset_index(name='Task Details')
    res = pd.merge(res_hours, res_details, on=group_by_cols)
    res[hours_col] = res[hours_col].round(2)
    return res

# ==========================================
# 🚀 Streamlit UI
# ==========================================
st.set_page_config(page_title="Hours Analysis Dashboard", layout="wide")

# 標頭映射定義 (關鍵修改：加入更多 Example 可能的寫法)
TESTER_COL_MAP = {
    'Date': ['Date', '日期'],
    'Tester #': ['Tester #', 'Tester No.', '機台編號', 'Tester'],
    'Tester Total Hours': ['Tester Total Hours', 'Tester Hours', '總時數', '時數', 'Tester Usage'],
    'TEMP': ['TEMP', '溫度', 'Temperature'],
    'Customer Requestor': ['Customer Requestor', 'Requestor', '需求者', '客戶'],
    'Task Details': ['Lot #wafer / Purpose /Description', '任務說明', 'Description', 'Task Details']
}

ENG_COL_MAP = {
    'Date': ['Date', '日期'],
    'Name': ['Name', '工程師姓名', 'Engineer', '姓名'],
    'Engineering Support Hours': ['Engineering Support Hours', 'Eng Hours', '工程支援時數', '支援時數', '時數'],
    'Tester': ['Tester', '機台', 'Tester #', '機台編號'],
    'Customer Requestor': ['Customer Requestor', 'Requestor', '需求者', '客戶'],
    'Task Details': ['Lot #wafer / Purpose /Description', '任務說明', 'Description', 'Task Details']
}

st.title("📊 Tester & Engineer Hours Dashboard")
is_eng = st.sidebar.toggle("🌐 English", value=False)

with st.sidebar:
    st.header("⚙️ Control Panel")
    uploaded_files = st.file_uploader("📂 Upload Excel", type=["xlsx", "xls"], accept_multiple_files=True)

if uploaded_files:
    try:
        all_t_list = []
        all_e_list = []
        
        for file in uploaded_files:
            # 讀取分頁
            t_raw = pd.read_excel(file, sheet_name="Tester Hours", skiprows=3)
            e_raw = pd.read_excel(file, sheet_name="Engineering Hours")
            
            # --- 映射 Tester 欄位 ---
            t_renamed = {}
            for target, aliases in TESTER_COL_MAP.items():
                found = get_actual_col(t_raw, aliases)
                if found: t_renamed[found] = target
            df_t = t_raw.rename(columns=t_renamed)
            
            # --- 映射 Eng 欄位 ---
            e_renamed = {}
            for target, aliases in ENG_COL_MAP.items():
                found = get_actual_col(e_raw, aliases)
                if found: e_renamed[found] = target
            df_e = e_raw.rename(columns=e_renamed)

            # 強制補齊缺失欄位 (防止 Not in Index 錯誤)
            for col in TESTER_COL_MAP.keys():
                if col not in df_t.columns: df_t[col] = 0 if 'Hours' in col else "Unknown"
            for col in ENG_COL_MAP.keys():
                if col not in df_e.columns: df_e[col] = 0 if 'Hours' in col else "Unknown"
            
            all_t_list.append(df_t[list(TESTER_COL_MAP.keys())])
            all_e_list.append(df_e[list(ENG_COL_MAP.keys())])
            
        df_tester = pd.concat(all_t_list, ignore_index=True)
        df_eng = pd.concat(all_e_list, ignore_index=True)

        # 數據清理
        for df, h_col in [(df_tester, 'Tester Total Hours'), (df_eng, 'Engineering Support Hours')]:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df.dropna(subset=['Date'], inplace=True)
            df['Month'] = df['Date'].dt.to_period('M').astype(str)
            df[h_col] = pd.to_numeric(df[h_col], errors='coerce').fillna(0)

        # 側邊欄過濾器
        with st.sidebar:
            st.divider()
            months = sorted(list(set(df_tester['Month'].unique()) | set(df_eng['Month'].unique())))
            sel_months = st.multiselect("📅 Select Month", options=months, default=months)
            df_tester = df_tester[df_tester['Month'].isin(sel_months)]
            df_eng = df_eng[df_eng['Month'].isin(sel_months)]

        # 均分處理 (現在這部分更安全了)
        for c in ['Tester #', 'TEMP', 'Customer Requestor']:
            df_tester = split_and_distribute(df_tester, c, 'Tester Total Hours')
        for c in ['Name', 'Tester', 'Customer Requestor']:
            df_eng = split_and_distribute(df_eng, c, 'Engineering Support Hours')

        # 團隊定義
        with st.sidebar:
            st.subheader("👥 Team Setting")
            all_req = sorted(list(set(df_tester['Customer Requestor'].unique()) | set(df_eng['Customer Requestor'].unique())))
            cso_list = st.multiselect("CSO", options=all_req, default=[n for n in ['Alec'] if n in all_req])
            gchip_list = st.multiselect("Gchip", options=[x for x in all_req if x not in cso_list], default=[n for n in ['Rajesh', 'Louis'] if n in all_req])
            
            def get_team(x):
                if x in cso_list: return 'CSO'
                if x in gchip_list: return 'Gchip'
                return 'Other / Unassigned'
            df_tester['Team'] = df_tester['Customer Requestor'].apply(get_team)
            df_eng['Team'] = df_eng['Customer Requestor'].apply(get_team)

        # KPI 展示
        st.subheader("📌 Executive Summary")
        k1, k2, k3 = st.columns(3)
        k1.metric("Tester Hours", f"{df_tester['Tester Total Hours'].sum():,.1f}")
        k2.metric("Eng Hours", f"{df_eng['Engineering Support Hours'].sum():,.1f}")
        k3.metric("Top Tester", df_tester.groupby('Tester #')['Tester Total Hours'].sum().idxmax() if not df_tester.empty else "N/A")

        # 視覺化
        st.divider()
        view = st.radio("Switch View", ["Team Analysis", "Monthly Trends"], horizontal=True)
        
        if view == "Team Analysis":
            t_team = aggregate_data(df_tester, 'Team', 'Tester Total Hours', False, is_eng)
            st.write("### Tester by Team")
            st.dataframe(t_team, use_container_width=True)
            
            fig, ax = plt.subplots(figsize=(8, 4))
            sns.barplot(data=t_team, x='Team', y='Tester Total Hours', ax=ax)
            st.pyplot(fig)

        elif view == "Monthly Trends":
            t_month = aggregate_data(df_tester, ['Month', 'Tester #'], 'Tester Total Hours', True, is_eng)
            st.write("### Monthly Tester Usage")
            st.dataframe(t_month, use_container_width=True)

    except Exception as e:
        st.error(f"執行時發生錯誤: {e}")
else:
    st.info("👈 Waiting for Excel files...")
