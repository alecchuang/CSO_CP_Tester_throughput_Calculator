import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import re

# ==========================================
# 🔧 輔助函數區
# ==========================================
def split_and_distribute(df, target_col, hours_col):
    df = df.copy()
    if target_col not in df.columns:
        return df
    df[target_col] = df[target_col].astype(str).replace(['nan', 'None', ''], 'Unknown')
    def safe_split(val):
        if val == 'Unknown': return ['Unknown']
        parts = re.split(r'[/,;\n\r]+', str(val))
        parts = [p.strip() for p in parts if p.strip()]
        return parts if parts else ['Unknown']
    df['__split_list'] = df[target_col].apply(safe_split)
    df['__split_count'] = df['__split_list'].apply(len)
    df[hours_col] = df[hours_col] / df['__split_count']
    df = df.explode('__split_list')
    df[target_col] = df['__split_list']
    df = df.drop(columns=['__split_list', '__split_count'])
    return df

def get_actual_col(df, aliases):
    """從 DataFrame 中自動尋找最匹配的標頭名稱 (不分大小寫、去空白)"""
    for alias in aliases:
        if alias in df.columns: return alias
        for col in df.columns:
            if str(col).strip().lower() == str(alias).strip().lower():
                return col
    return None

# ==========================================
# 🌟 聚合函數
# ==========================================
def aggregate_data(df, group_by_cols, hours_col, show_breakdown=True, is_eng=False):
    if isinstance(group_by_cols, str): group_by_cols = [group_by_cols]
    
    # 檢查必要欄位是否存在
    for col in group_by_cols:
        if col not in df.columns: return pd.DataFrame()
        
    txt_click_expand = "(Click to expand)" if is_eng else "(點擊展開)"
    txt_total = "Total" if is_eng else "總計"
    txt_no_detail = "No details provided (N/A)" if is_eng else "無詳細說明 (N/A)"
    txt_team_detail_prefix = "🏢 [{team}] Task Details:\n" if is_eng else "🏢 【{team}】 任務明細：\n"
    
    breakdown_col = f"⏱️ {hours_col} {txt_click_expand}"
    
    columns_to_return = group_by_cols + [hours_col, 'Task Details']
    if show_breakdown:
        columns_to_return.insert(-1, breakdown_col)
        
    if df.empty: 
        return pd.DataFrame(columns=columns_to_return)
        
    res_hours = df.groupby(group_by_cols)[hours_col].sum().reset_index()
    res = res_hours
    
    if show_breakdown:
        def format_hours(g):
            total = g[hours_col].sum()
            if 'Team' not in g.columns:
                return f"{txt_total}: {total:.2f} hrs"
            cso_hrs = g[g['Team'] == 'CSO'][hours_col].sum()
            gchip_hrs = g[g['Team'] == 'Gchip'][hours_col].sum()
            other_hrs = g[g['Team'] == 'Other / Unassigned'][hours_col].sum()
            details = [f"{txt_total}: {total:.2f} hrs"]
            if cso_hrs > 0: details.append(f"  ├ CSO: {cso_hrs:.2f} hrs")
            if gchip_hrs > 0: details.append(f"  ├ Gchip: {gchip_hrs:.2f} hrs")
            if other_hrs > 0: details.append(f"  └ Other: {other_hrs:.2f} hrs")
            return '\n'.join(details)
        res_breakdown = df.groupby(group_by_cols).apply(format_hours).reset_index(name=breakdown_col)
        res = pd.merge(res_hours, res_breakdown, on=group_by_cols)

    def format_details(g):
        details_str = []
        if 'Team' not in g.columns:
            tasks = g['Task Details'].unique()
            valid_items = [str(i).strip() for i in tasks if pd.notna(i) and str(i).strip() != '']
            return '\n'.join([f"  • {item}" for item in valid_items]) if valid_items else txt_no_detail
        for team_name in ['CSO', 'Gchip', 'Other / Unassigned']:
            team_rows = g[g['Team'] == team_name]
            if team_rows.empty: continue
            tasks = team_rows['Task Details'].unique()
            valid_items = [str(i).strip() for i in tasks if pd.notna(i) and str(i).strip() != '']
            if valid_items:
                team_str = txt_team_detail_prefix.format(team=team_name) + '\n'.join([f"  • {item}" for item in valid_items])
                details_str.append(team_str)
        return '\n\n----------------------------------------\n\n'.join(details_str) if details_str else txt_no_detail
        
    res_details = df.groupby(group_by_cols).apply(format_details).reset_index(name='Task Details')
    res = pd.merge(res, res_details, on=group_by_cols)
    res[hours_col] = res[hours_col].round(2)
    if 'Month' not in group_by_cols: res = res.sort_values(hours_col, ascending=False)
    return res

# ==========================================
# 網頁主程式開始
# ==========================================
st.set_page_config(page_title="Hours Analysis Dashboard", layout="wide")

st.markdown("""
<style>
    div.row-widget.stRadio > div { flex-direction: row; gap: 20px; padding: 10px 0; }
    div.row-widget.stRadio label { font-size: 1.1rem !important; font-weight: 600 !important; cursor: pointer; }
</style>
""", unsafe_allow_html=True)

is_eng = st.sidebar.toggle("🌐 Switch to English (全英文介面)", value=False)

# --- 標題與說明文字 ---
TXT_APP_TITLE = "📊 Tester & Engineer Hours Advanced Dashboard" if is_eng else "📊 機台與工程師時數進階分析儀表板"
TXT_REL_NOTES_TITLE = "🚀 Release Notes (Click to Expand)" if is_eng else "🚀 版本更新紀錄 / Release Notes (點擊展開)"
TXT_REL_NOTES_CONTENT = "* **v30**: 修正標頭映射邏輯，支援範例檔案彈性讀取。"
TXT_SIDEBAR_CTRL = "⚙️ Control Panel" if is_eng else "⚙️ 控制面板"
TXT_UPLOAD_FILE = "📂 Upload Excel File(s)" if is_eng else "📂 上傳 Excel 紀錄表 (支援多選)"
TXT_MONTH_FILTER = "📅 Select Months to Analyze" if is_eng else "📅 選擇統計月份"
TXT_KPI_SETTING = "🎯 KPI Target Settings" if is_eng else "🎯 KPI 目標設定"
TXT_TESTER_COUNT_LABEL = "Set total testers" if is_eng else "設定機台總數量"
TXT_TEAM_DEF = "👥 Team Members Definition" if is_eng else "👥 團隊成員定義"
TXT_DEF_CSO = "Define CSO Members" if is_eng else "定義 CSO 成員"
TXT_DEF_GCHIP = "Define Gchip Members" if is_eng else "定義 Gchip 成員"
TXT_KPI_SUMMARY = "📌 Executive Summary" if is_eng else "📌 核心數據總覽"
TXT_KPI_TOTAL_TESTER = "🖥️ Total Tester Hours" if is_eng else "🖥️ 總機台使用時數"
TXT_KPI_TOTAL_ENG = "🧑‍🔧 Total Eng Hours" if is_eng else "🧑‍🔧 總工程支援時數"
TXT_KPI_TOP_TESTER = "🔥 Top Usage Tester" if is_eng else "🔥 最高用量機台"
TXT_SELECT_DIM = "Select Analysis Dimension" if is_eng else "選擇分析維度"
TXT_NAV_TEAM = "🏢 Team Analysis" if is_eng else "🏢 團隊歸屬分析"
TXT_NAV_MONTHLY = "📅 Monthly Trends" if is_eng else "📅 每月趨勢分析"
TXT_NAV_TEMP = "🌡️ Advanced (TEMP/ENG)" if is_eng else "🌡️ 進階維度分析"
TXT_NAV_REQ = "👤 Requestor Analysis" if is_eng else "👤 客戶需求者分析"
TXT_NO_FILE = "👈 Please upload Excel file(s) to begin." if is_eng else "👈 請上傳 Excel 檔案以開始分析。"

# ==========================================
# 📂 標頭映射定義 (對應 Example 輸入檔案)
# ==========================================
TESTER_COL_MAP = {
    'Date': ['Date', '日期'],
    'Tester #': ['Tester #', 'Tester No.', '機台編號', 'Tester'],
    'Tester Total Hours': ['Tester Total Hours', 'Tester Hours', '總時數', '時數'],
    'TEMP': ['TEMP', '溫度', 'Temperature'],
    'Customer Requestor': ['Customer Requestor', 'Requestor', '需求者', '客戶'],
    'Task Details': ['Lot #wafer / Purpose /Description', '任務說明', 'Description', 'Task Details']
}

ENG_COL_MAP = {
    'Date': ['Date', '日期'],
    'Name': ['Name', '工程師姓名', 'Engineer'],
    'Engineering Support Hours': ['Engineering Support Hours', 'Eng Hours', '工程支援時數', '時數'],
    'Tester': ['Tester', '機台', 'Tester #'],
    'Customer Requestor': ['Customer Requestor', 'Requestor', '需求者', '客戶'],
    'Task Details': ['Lot #wafer / Purpose /Description', '任務說明', 'Description', 'Task Details']
}

st.title(TXT_APP_TITLE)
with st.expander(TXT_REL_NOTES_TITLE): st.markdown(TXT_REL_NOTES_CONTENT)

with st.sidebar:
    st.header(TXT_SIDEBAR_CTRL)
    uploaded_files = st.file_uploader(TXT_UPLOAD_FILE, type=["xlsx", "xls"], accept_multiple_files=True)

if uploaded_files:
    try:
        list_df_tester_raw = []
        list_df_eng_raw = []
        
        for file in uploaded_files:
            # 讀取 Excel
            df_t_raw = pd.read_excel(file, sheet_name="Tester Hours", skiprows=3)
            df_e_raw = pd.read_excel(file, sheet_name="Engineering Hours")
            
            # --- Tester Hours 欄位映射與重新命名 ---
            t_rename = {}
            for target, aliases in TESTER_COL_MAP.items():
                actual = get_actual_col(df_t_raw, aliases)
                if actual: t_rename[actual] = target
            df_t = df_t_raw.rename(columns=t_rename)
            needed_t = [c for c in TESTER_COL_MAP.keys() if c in df_t.columns]
            list_df_tester_raw.append(df_t[needed_t])

            # --- Engineering Hours 欄位映射與重新命名 ---
            e_rename = {}
            for target, aliases in ENG_COL_MAP.items():
                actual = get_actual_col(df_e_raw, aliases)
                if actual: e_rename[actual] = target
            df_e = df_e_raw.rename(columns=e_rename)
            needed_e = [c for c in ENG_COL_MAP.keys() if c in df_e.columns]
            list_df_eng_raw.append(df_e[needed_e])
            
        df_tester = pd.concat(list_df_tester_raw, ignore_index=True)
        df_eng = pd.concat(list_df_eng_raw, ignore_index=True)
        
        # 資料清洗
        for df, h_col in [(df_tester, 'Tester Total Hours'), (df_eng, 'Engineering Support Hours')]:
            df.dropna(subset=['Date', h_col], how='any', inplace=True)
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df.dropna(subset=['Date'], inplace=True)
            df['Month'] = df['Date'].dt.to_period('M').astype(str)
            df[h_col] = pd.to_numeric(df[h_col], errors='coerce').fillna(0)

        # 側邊欄：月份篩選
        with st.sidebar:
            st.divider()
            all_months = sorted(list(set(df_tester['Month'].unique()) | set(df_eng['Month'].unique())))
            selected_months = st.multiselect(TXT_MONTH_FILTER, options=all_months, default=all_months)
            df_tester = df_tester[df_tester['Month'].isin(selected_months)]
            df_eng = df_eng[df_eng['Month'].isin(selected_months)]

        # 時數均分處理
        for col in ['Tester #', 'TEMP', 'Customer Requestor']:
            df_tester = split_and_distribute(df_tester, col, 'Tester Total Hours')
        for col in ['Name', 'Tester', 'Customer Requestor']:
            df_eng = split_and_distribute(df_eng, col, 'Engineering Support Hours')

        # 側邊欄：團隊定義
        with st.sidebar:
            st.divider()
            st.subheader(TXT_KPI_SETTING)
            tester_count = st.number_input(TXT_TESTER_COUNT_LABEL, min_value=1, value=10)
            st.subheader(TXT_TEAM_DEF)
            all_req = sorted(list(set(df_tester['Customer Requestor'].unique()) | set(df_eng['Customer Requestor'].unique())))
            cso_members = st.multiselect(TXT_DEF_CSO, options=all_req, default=[n for n in ['Alec'] if n in all_req])
            gchip_members = st.multiselect(TXT_DEF_GCHIP, options=[x for x in all_req if x not in cso_members], default=[n for n in ['Rajesh', 'Louis'] if n in all_req])
            
            def map_team(name):
                if name in cso_members: return 'CSO'
                elif name in gchip_members: return 'Gchip'
                else: return 'Other / Unassigned'
            df_tester['Team'] = df_tester['Customer Requestor'].apply(map_team)
            df_eng['Team'] = df_eng['Customer Requestor'].apply(map_team)

        # KPI 顯示
        st.subheader(TXT_KPI_SUMMARY)
        total_days = sum([pd.Period(m).days_in_month for m in selected_months]) if selected_months else 30
        min_hrs = total_days * 24 * tester_count * 0.5
        total_t_hrs = df_tester['Tester Total Hours'].sum()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(TXT_KPI_TOTAL_TESTER, f"{total_t_hrs:,.1f} h")
        k2.metric(f"🎯 Target ({tester_count} units)", f"{min_hrs:,.0f} h", delta=f"{total_t_hrs-min_hrs:,.1f}")
        k3.metric(TXT_KPI_TOTAL_ENG, f"{df_eng['Engineering Support Hours'].sum():,.1f} h")
        top_t = df_tester.groupby('Tester #')['Tester Total Hours'].sum().idxmax() if not df_tester.empty else "N/A"
        k4.metric(TXT_KPI_TOP_TESTER, top_t)
        st.divider()

        # 視覺化邏輯 (共用繪圖函數)
        def render_view(ui_t, ch_t, df, x, y, hue=None, pal='deep'):
            st.markdown(f"#### {ui_t}")
            c1, c2 = st.columns([1, 2])
            with c1: st.dataframe(df, use_container_width=True, hide_index=True)
            with c2:
                if df.empty: st.warning("No data")
                else:
                    fig, ax = plt.subplots(figsize=(10, 4.5))
                    sns.barplot(data=df, x=x, y=y, hue=hue, ax=ax, palette=pal)
                    plt.xticks(rotation=45); st.pyplot(fig)

        # 導覽與渲染
        view = st.radio(TXT_SELECT_DIM, [TXT_NAV_TEAM, TXT_NAV_MONTHLY, TXT_NAV_TEMP, TXT_NAV_REQ], horizontal=True, label_visibility="collapsed")
        
        if view == TXT_NAV_TEAM:
            render_view("🟦 Tester by Team", "Team Stats", aggregate_data(df_tester, 'Team', 'Tester Total Hours', False, is_eng), 'Team', 'Tester Total Hours')
            render_view("🟧 Eng by Team", "Team Stats", aggregate_data(df_eng, 'Team', 'Engineering Support Hours', False, is_eng), 'Team', 'Engineering Support Hours')
        elif view == TXT_NAV_MONTHLY:
            render_view("🟦 Monthly Tester", "Monthly", aggregate_data(df_tester, ['Month', 'Tester #'], 'Tester Total Hours', True, is_eng), 'Month', 'Tester Total Hours', 'Tester #')
        elif view == TXT_NAV_TEMP:
            render_view("🟦 Tester by TEMP", "TEMP", aggregate_data(df_tester, 'TEMP', 'Tester Total Hours', True, is_eng), 'TEMP', 'Tester Total Hours')
        elif view == TXT_NAV_REQ:
            render_view("🟦 Tester by Req", "Requestor", aggregate_data(df_tester, 'Customer Requestor', 'Tester Total Hours', False, is_eng), 'Customer Requestor', 'Tester Total Hours')

    except Exception as e: st.error(f"Error: {e}")
else: st.info(TXT_NO_FILE)
