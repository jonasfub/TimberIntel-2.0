import streamlit as st
import plotly.express as px
import pandas as pd
import datetime
from logic import load_data_from_db, process_financials
from ui_style import apply_alpaca_style, kpi_card 

# ==========================================
# 1. 页面配置
# ==========================================
st.set_page_config(
    page_title="LogicSync OS", 
    page_icon="🌲", 
    layout="wide",
    initial_sidebar_state="expanded"
)

apply_alpaca_style()

st.markdown("### 🌲 LogicSync Dashboard") 
st.markdown("---")

# ==========================================
# 2. 数据加载
# ==========================================
df_std, df_s, df_b = load_data_from_db()

if df_std is None:
    st.warning("正在连接数据库或数据为空... 请检查 Secrets 配置。")
    st.stop()

# --- 辅助函数：智能查找列名 ---
def find_col(df, candidates):
    if df.empty: return None
    cols_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in cols_lower:
            return cols_lower[cand.lower()]
    return None

# ==========================================
# 3. 侧边栏筛选 (已更新)
# ==========================================
with st.sidebar:
    st.header("Filters")
    
    # --- 📅 智能周期选择器 ---
    st.subheader("📅 Time Period")
    
    period_options = [
        "All Time (Up to Date)", # 🔥 新增：从一开始到现在
        "This Year (YTD)",       # 本年度至今
        "Last Year",             # 上一年度
        "This Quarter",          # 本季度
        "Last Quarter",          # 上季度
        "Q1 (Jan-Mar)",          # 固定 Q1
        "Q2 (Apr-Jun)",          # 固定 Q2
        "Q3 (Jul-Sep)",          # 固定 Q3
        "Q4 (Oct-Dec)",          # 固定 Q4
        "Custom Range"           # 自定义
    ]
    
    selected_period = st.selectbox("Select Period / 选择周期", period_options, index=0)
    
    # 获取当前日期
    today = datetime.date.today()
    current_year = today.year
    
    # 初始化起止日期
    start_d, end_d = today, today

    # --- 日期计算逻辑 ---
    if selected_period == "All Time (Up to Date)":
        # 设置一个足够早的日期 (例如 2020-01-01)
        start_d = datetime.date(2020, 1, 1)
        end_d = today

    elif selected_period == "This Year (YTD)":
        start_d = datetime.date(current_year, 1, 1)
        end_d = today
        
    elif selected_period == "Last Year":
        start_d = datetime.date(current_year - 1, 1, 1)
        end_d = datetime.date(current_year - 1, 12, 31)
        
    elif selected_period == "This Quarter":
        curr_q = (today.month - 1) // 3 + 1
        start_month = (curr_q - 1) * 3 + 1
        start_d = datetime.date(current_year, start_month, 1)
        end_d = today
        
    elif selected_period == "Last Quarter":
        curr_q = (today.month - 1) // 3 + 1
        if curr_q == 1: 
            start_d = datetime.date(current_year - 1, 10, 1)
            end_d = datetime.date(current_year - 1, 12, 31)
        else:
            prev_q = curr_q - 1
            start_month = (prev_q - 1) * 3 + 1
            end_month = start_month + 2
            next_month_first = datetime.date(current_year, end_month + 1, 1) if end_month < 12 else datetime.date(current_year + 1, 1, 1)
            end_d = next_month_first - datetime.timedelta(days=1)
            start_d = datetime.date(current_year, start_month, 1)

    elif "Q1" in selected_period:
        start_d = datetime.date(current_year, 1, 1); end_d = datetime.date(current_year, 3, 31)
    elif "Q2" in selected_period:
        start_d = datetime.date(current_year, 4, 1); end_d = datetime.date(current_year, 6, 30)
    elif "Q3" in selected_period:
        start_d = datetime.date(current_year, 7, 1); end_d = datetime.date(current_year, 9, 30)
    elif "Q4" in selected_period:
        start_d = datetime.date(current_year, 10, 1); end_d = datetime.date(current_year, 12, 31)
        
    elif selected_period == "Custom Range":
        c_dates = st.date_input("Custom Range", (datetime.date(current_year, 1, 1), today))
        if isinstance(c_dates, tuple) and len(c_dates) == 2:
            start_d, end_d = c_dates
        else:
            start_d, end_d = datetime.date(current_year, 1, 1), today

    st.caption(f"Active: {start_d} ~ {end_d}")
    st.markdown("---")

# ==========================================
# 4. 核心逻辑处理 (Time-Aware Inventory)
# ==========================================
try:
    # A. 获取基础 P&L 数据 (Logic.py 处理全量数据)
    df_pnl, df_inv_original, df_bills_unmatched, metrics_all = process_financials(df_std, df_s, df_b)
    
    if isinstance(metrics_all, str):
        st.info("👋 欢迎使用 LogicSync。暂无数据，请先录入订单。")
        st.stop()

    # B. 增强列名匹配 (加入带空格的候选)
    col_date_b = find_col(df_b, ['bill date', 'bill_date', 'date'])
    if col_date_b: df_b[col_date_b] = pd.to_datetime(df_b[col_date_b])
    
    col_date_s = find_col(df_s, ['order date', 'order_date', 'date'])
    if col_date_s: df_s[col_date_s] = pd.to_datetime(df_s[col_date_s])

    # C. 库存快照计算 (基于 end_d)
    cutoff_date = pd.Timestamp(end_d) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

    # 1. 过滤数据用于库存计算
    df_b_snapshot = df_b[df_b[col_date_b] <= cutoff_date].copy() if col_date_b else df_b.copy()
    df_s_snapshot = df_s[df_s[col_date_s] <= cutoff_date].copy() if col_date_s else df_s.copy()

    # 2. 识别列名
    item_candidates = ['item_name', 'item name', 'item', 'product_name', 'product', 'description']
    col_item_b = find_col(df_b, item_candidates)
    col_item_s = find_col(df_s, item_candidates)
    col_qty_b = find_col(df_b, ['quantity', 'qty', 'units'])
    col_amt_b = find_col(df_b, ['amount_nzd', 'amount', 'total'])
    col_qty_s = find_col(df_s, ['quantity', 'qty', 'units'])
    col_port_b = find_col(df_b, ['port_of_loading', 'port', 'pol'])
    col_port_s = find_col(df_s, ['port_of_loading', 'port', 'pol'])
    col_item_std = find_col(df_std, item_candidates)

    df_live_inv = pd.DataFrame()
    total_inventory_value = 0
    
    if not df_b.empty and not df_s.empty and col_item_b and col_qty_b and col_amt_b and col_item_s and col_qty_s:
        # 确定有效 Item 列表
        if not df_std.empty and col_item_std:
            valid_items = df_std[col_item_std].unique()
        else:
            valid_items = df_b[col_item_b].unique()
            
        # 3. 计算入库 (Filtered)
        df_b_clean = df_b_snapshot[df_b_snapshot[col_item_b].isin(valid_items)].copy()
        df_b_clean['Port_Std'] = df_b_clean[col_port_b].fillna('Unknown').astype(str).str.strip() if col_port_b else 'Unknown'
        df_b_clean = df_b_clean.rename(columns={col_item_b: 'Item', col_qty_b: 'Qty', col_amt_b: 'Amt'})
        grp_in = df_b_clean.groupby(['Item', 'Port_Std'])[['Qty', 'Amt']].sum()
        
        # 4. 计算出库 (Filtered)
        df_s_clean = df_s_snapshot[df_s_snapshot[col_item_s].isin(valid_items)].copy()
        df_s_clean['Port_Std'] = df_s_clean[col_port_s].fillna('Unknown').astype(str).str.strip() if col_port_s else 'Unknown'
        df_s_clean = df_s_clean.rename(columns={col_item_s: 'Item', col_qty_s: 'Qty'})
        grp_out = df_s_clean.groupby(['Item', 'Port_Std'])['Qty'].sum()
        
        # 5. 合并计算库存
        df_calc = grp_in.join(grp_out, rsuffix='_out', how='left').fillna(0)
        df_calc['Qty_out'] = df_calc['Qty_out'] if 'Qty_out' in df_calc.columns else 0
        df_calc['On_Hand'] = df_calc['Qty'] - df_calc['Qty_out']
        
        # 加权平均成本
        df_calc['Avg_Cost'] = df_calc.apply(lambda x: x['Amt'] / x['Qty'] if x['Qty'] > 0 else 0, axis=1)
        df_calc['Total_Value'] = df_calc['On_Hand'] * df_calc['Avg_Cost']
        
        df_live_inv = df_calc.reset_index()
        df_live_inv = df_live_inv[['Item', 'Port_Std', 'On_Hand', 'Avg_Cost', 'Total_Value']]
        df_live_inv.columns = ['Item Name', 'Port of Loading', 'On Hand (CBM)', 'Avg Cost (NZD)', 'Total Value (NZD)']
        
        # 过滤微小误差
        df_live_inv = df_live_inv[abs(df_live_inv['On Hand (CBM)']) > 0.001]
        
        total_inventory_value = df_live_inv['Total Value (NZD)'].sum()

    # D. 智能匹配系统
    col_inv_pnl = find_col(df_pnl, ['invoice_no', 'invoice'])
    col_inv_s = find_col(df_s, ['invoice_no', 'invoice'])
    
    if col_inv_pnl and col_inv_s and col_port_s:
        temp = df_s.copy()
        temp['k'] = temp[col_inv_s].astype(str).str.strip().str.upper()
        pmap = temp.set_index('k')[col_port_s].to_dict()
        keys = df_pnl[col_inv_pnl].astype(str).str.strip().str.upper()
        df_pnl['Port'] = keys.map(pmap).fillna('Unknown')
    else:
        df_pnl['Port'] = 'Unknown'

except Exception as e:
    st.error(f"数据处理错误: {e}")
    st.stop()

# ==========================================
# 5. 更多筛选 & KPI 计算
# ==========================================
with st.sidebar:
    st.subheader("🔎 Filters")
    status_opts = df_pnl['Status'].unique() if 'Status' in df_pnl.columns else []
    selected_status = st.multiselect("Status", options=status_opts, default=status_opts)
    
    pnl_ports = df_pnl['Port'].unique() if 'Port' in df_pnl.columns else []
    inv_ports = df_live_inv['Port of Loading'].unique() if not df_live_inv.empty else []
    all_ports = list(set([str(p) for p in list(pnl_ports) + list(inv_ports) if str(p).lower() != 'nan']))
    selected_ports = st.multiselect("Ports", options=all_ports, default=all_ports)

# --- KPI 计算 ---
df_pnl['Date'] = pd.to_datetime(df_pnl['Date'], errors='coerce')
if col_date_b:
    df_b[col_date_b] = pd.to_datetime(df_b[col_date_b], errors='coerce')

# 收入/支出：计算周期内的发生额
mask_rev = (df_pnl['Date'].dt.date >= start_d) & (df_pnl['Date'].dt.date <= end_d)
kpi_revenue = df_pnl[mask_rev]['Revenue_NZD'].sum()

if col_date_b:
    mask_exp = (df_b[col_date_b].dt.date >= start_d) & (df_b[col_date_b].dt.date <= end_d)
    kpi_expense = df_b[mask_exp]['Amount_NZD'].sum()
else:
    kpi_expense = 0

kpi_inventory = total_inventory_value 
kpi_profit = kpi_revenue - kpi_expense + kpi_inventory

filtered_df = df_pnl[
    (df_pnl['Status'].isin(selected_status)) & 
    (df_pnl['Port'].isin(selected_ports)) 
]

if not df_live_inv.empty:
    filtered_inv = df_live_inv[df_live_inv['Port of Loading'].isin(selected_ports)]
else:
    filtered_inv = pd.DataFrame()

# ==========================================
# 6. KPI 卡片展示
# ==========================================
c1, c2, c3, c4 = st.columns(4)
kpi_card(c1, "Total Revenue", f"${kpi_revenue:,.0f}")
kpi_card(c2, "Total Expenses", f"${kpi_expense:,.0f}", delta_color="inverse")
kpi_card(c3, "Inventory Asset", f"${kpi_inventory:,.0f}", delta=f"As of {end_d}")
kpi_card(c4, "Net Profit", f"${kpi_profit:,.0f}", delta="Realized + Asset", delta_color="normal")

st.markdown(" ") 

# ==========================================
# 7. 主要内容 Tabs
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Orders Detail", "Inventory", "Bills"])

with tab1:
    cc1, cc2 = st.columns(2)
    with cc1:
        if not filtered_df.empty:
            col_gp = find_col(filtered_df, ['gross_profit', 'gp', 'profit'])
            col_inv_plot = find_col(filtered_df, ['invoice_no', 'invoice'])
            if col_gp and col_inv_plot:
                fig1 = px.bar(
                    filtered_df, x=col_inv_plot, y=col_gp, color='Status', 
                    title="Profit per Shipment (NZD)",
                    color_discrete_map={'Finalized': '#333333', 'Partial': '#FCD535', 'Provisional': '#E0E0E0'}
                )
                fig1.update_layout(plot_bgcolor='white', paper_bgcolor='white', font={'family': 'Inter'})
                st.plotly_chart(fig1, use_container_width=True)
            
    with cc2:
        if not filtered_df.empty:
            col_rev = find_col(filtered_df, ['revenue_nzd', 'revenue', 'rev'])
            col_month = find_col(filtered_df, ['month'])
            col_gp = find_col(filtered_df, ['gross_profit', 'gp', 'profit'])

            if col_month and col_rev and col_gp:
                monthly = filtered_df.groupby(col_month)[[col_rev, col_gp]].sum().reset_index().sort_values(col_month)
                fig2 = px.bar(
                    monthly, x=col_month, y=[col_rev, col_gp], barmode='group', 
                    title="Monthly Performance",
                    color_discrete_sequence=['#E0E0E0', '#FCD535'] 
                )
                fig2.update_layout(plot_bgcolor='white', paper_bgcolor='white', font={'family': 'Inter'})
                st.plotly_chart(fig2, use_container_width=True)

    st.markdown("---")
    st.subheader("🚢 Port Profitability (Monthly Breakdown)")
    
    if not filtered_df.empty and 'Port' in filtered_df.columns:
        col_gp = find_col(filtered_df, ['gross_profit', 'gp', 'profit'])
        col_month = find_col(filtered_df, ['month'])
        
        if col_gp and col_month:
            port_profit = filtered_df.groupby([col_month, 'Port'])[col_gp].sum().reset_index().sort_values([col_month, 'Port'])
            color_map = {'Wellington': '#333333', 'Lyttelton': '#FCD535', 'Tauranga': '#555555', 'Napier': '#777777', 'Unknown': '#E0E0E0'}
            fig3 = px.bar(
                port_profit, x=col_month, y=col_gp, color='Port', barmode='group',
                title="Gross Profit by Port", text_auto='.2s', color_discrete_map=color_map 
            )
            fig3.update_layout(plot_bgcolor='white', paper_bgcolor='white', font={'family': 'Inter'}, xaxis_title=None)
            st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("No port data available.")

with tab2:
    st.subheader("Shipment P&L Detail")
    if not filtered_df.empty:
        df_display = filtered_df.copy()
        cols_to_drop = [c for c in df_display.columns if c.lower() in ['id', 'created_at']]
        df_display = df_display.drop(columns=cols_to_drop)
        st.dataframe(df_display, use_container_width=True)
    else:
        st.info("No data available.")

with tab3:
    st.subheader(f"Live Inventory Snapshot (As of {end_d})")
    
    if not filtered_inv.empty:
        # 1. 表格
        def highlight_negative(val):
            try:
                v = float(val.replace(',', '').replace('$', '')) if isinstance(val, str) else val
                return 'background-color: #ffcccb; color: #8b0000; font-weight: bold;' if v < 0 else ''
            except:
                return ''

        st.dataframe(
            filtered_inv.style.format({
                "On Hand (CBM)": "{:,.3f}", 
                "Avg Cost (NZD)": "${:,.2f}", 
                "Total Value (NZD)": "${:,.2f}"
            }).applymap(highlight_negative, subset=['On Hand (CBM)', 'Total Value (NZD)']), 
            use_container_width=True
        )
        
        st.markdown("---")
        
        # 2. 分港口/产品横向条形图
        st.subheader("📊 Inventory Breakdown by Port")
        fig_inv_bar = px.bar(
            filtered_inv,
            x='On Hand (CBM)',
            y='Item Name',
            color='Port of Loading',
            orientation='h',  # 横向
            barmode='group',  # 分组对比
            text_auto='.1f',
            title="Inventory Volume by Item & Port",
            color_discrete_map={'Wellington': '#333333', 'Lyttelton': '#FCD535', 'Tauranga': '#555555', 'Napier': '#777777', 'Unknown': '#E0E0E0'}
        )
        fig_inv_bar.update_layout(plot_bgcolor='white', paper_bgcolor='white', font={'family': 'Inter'}, xaxis_title="Volume (CBM)", yaxis_title=None)
        st.plotly_chart(fig_inv_bar, use_container_width=True)

        st.markdown("---")
        
        # 3. 库存趋势图 (增强健壮性)
        st.subheader("📈 Inventory Trend (Timeline)")
        try:
            # 安全构造数据
            df_trend_list = []
            
            # 构造入库流 (Purchase)
            if col_date_b and col_qty_b:
                in_flow = df_b[[col_date_b, col_qty_b]].copy()
                in_flow.columns = ['Date', 'Change']
                in_flow['Type'] = 'Purchase'
                df_trend_list.append(in_flow)
            
            # 构造出库流 (Sale)
            if col_date_s and col_qty_s:
                out_flow = df_s[[col_date_s, col_qty_s]].copy()
                out_flow.columns = ['Date', 'Change']
                out_flow['Change'] = -out_flow['Change'] # 变负数
                out_flow['Type'] = 'Sale'
                df_trend_list.append(out_flow)
            
            if df_trend_list:
                # 合并并计算累计
                df_trend = pd.concat(df_trend_list, ignore_index=True)
                df_trend['Date'] = pd.to_datetime(df_trend['Date']) # 再次确保是日期格式
                df_trend = df_trend.sort_values('Date')
                
                df_trend['Inventory Level'] = df_trend['Change'].cumsum()
                
                # 绘图 (只显示选定周期内的变化)
                df_trend_viz = df_trend[(df_trend['Date'].dt.date >= start_d) & (df_trend['Date'].dt.date <= end_d)]
                
                if not df_trend_viz.empty:
                    fig_trend = px.line(
                        df_trend_viz, x='Date', y='Inventory Level', 
                        title="Total Inventory Volume Over Time (CBM)", markers=True
                    )
                    fig_trend.update_layout(plot_bgcolor='white', paper_bgcolor='white', font={'family': 'Inter'})
                    st.plotly_chart(fig_trend, use_container_width=True)
                else:
                    st.info("No movements in selected period.")
            else:
                st.warning("Not enough data to generate trend chart.")

        except Exception as e:
            st.warning(f"Trend chart unavailable: {e}")
            
    else:
        st.info("No inventory on hand.")

with tab4:
    st.subheader("Unmatched Bills (Orphan)")
    if not df_bills_unmatched.empty:
        df_bills_display = df_bills_unmatched.copy()
        cols_to_drop_b = [c for c in df_bills_display.columns if c.lower() in ['id', 'created_at']]
        df_bills_display = df_bills_display.drop(columns=cols_to_drop_b)
        st.dataframe(df_bills_display, use_container_width=True)
    else:
        st.success("🎉 All bills are matched with shipments!")