import streamlit as st
import pandas as pd
import plotly.express as px
import config
import utils

# --- 页面配置 ---
st.set_page_config(page_title="Customer Search", page_icon="🔍", layout="wide")

st.title("🔍 Customer Intelligence (客户深度画像)")

# --- 1. 数据守门员 ---
if 'analysis_df' not in st.session_state or st.session_state['analysis_df'].empty:
    st.warning("⚠️ 请先在【首页 (Timber Intel Core)】加载数据。")
    st.stop() 

# 复制数据
df_full = st.session_state['analysis_df'].copy()

# ==========================================
# 🎨 [NEW] 高对比度配色方案 (High Contrast & Distinct)
# ==========================================
CORP_PALETTE = ['#3498db', '#e74c3c', '#2ecc71', '#f1c40f', '#9b59b6', '#e67e22', '#1abc9c', '#34495e']
COOL_DISTINCT = ['#2980b9', '#1abc9c', '#8e44ad', '#27ae60', '#3498db', '#16a085']
WARM_DISTINCT = ['#c0392b', '#f39c12', '#d35400', '#e84393', '#ff7675', '#e17055']

# ==========================================
# 🛠️ [修复核心]：补全缺失的国家名称列
# ==========================================
def get_name_safe(code):
    if not code: return "Unknown"
    name = config.COUNTRY_NAME_MAP.get(code, code)
    return name.split(' (')[0] if '(' in name else name

if 'origin_name' not in df_full.columns:
    df_full['origin_name'] = df_full['origin_country_code'].apply(get_name_safe)

if 'dest_name' not in df_full.columns:
    df_full['dest_name'] = df_full['dest_country_code'].apply(get_name_safe)
# ==========================================

# ==========================================
# 📊 侧边栏：全局数据范围 (Data Scope)
# ==========================================
with st.sidebar:
    st.header("📂 Data Scope")
    
    available_cats_global = set()
    present_hs = df_full['hs_code'].astype(str).unique()
    
    for cat_name, code_list in config.HS_CODES_MAP.items():
        for code in code_list:
            if any(str(ph).startswith(str(code)) for ph in present_hs):
                available_cats_global.add(cat_name)
                break
    
    sorted_cats_global = sorted(list(available_cats_global))
    
    selected_cat_sidebar = st.selectbox("Product Group (全局产品分类)", ["All (全部)"] + sorted_cats_global)
    st.info(f"💡 提示：此处筛选仅用于缩小下方搜索框的公司列表。")
    st.divider()
    if 'token_expiry' in st.session_state:
        remaining_min = int((st.session_state['token_expiry'] - pd.Timestamp.now().timestamp()) / 60)
        if remaining_min > 0: st.caption(f"✅ API Token Active ({remaining_min} min)")
        else: st.caption("⚠️ API Token Expired")

# ==========================================
# 🧹 应用侧边栏过滤 -> 生成 df_scope
# ==========================================
if selected_cat_sidebar != "All (全部)":
    target_codes = config.HS_CODES_MAP[selected_cat_sidebar]
    df_scope = df_full[df_full['hs_code'].astype(str).apply(lambda x: any(x.startswith(c) for c in target_codes))].copy()
else:
    df_scope = df_full.copy()

if df_scope.empty:
    st.warning(f"⚠️ 分类 '{selected_cat_sidebar}' 下无数据。")
    st.stop()

# --- 2. 搜索逻辑 (基于 df_scope) ---
importers = df_scope['importer_name'].fillna('Unknown').unique().tolist()
exporters = df_scope['exporter_name'].fillna('Unknown').unique().tolist()
all_companies = sorted(list(set([x for x in importers + exporters if x and x != 'Unknown'])))

st.markdown("### 🎯 Find Companies (查找/合并公司)")
c_search, c_kpi_role = st.columns([2, 1])

with c_search:
    target_companies = st.multiselect(
        "输入或选择公司名称 (支持多选合并):", 
        all_companies,
        placeholder=f"可选择多个别名 (e.g. ABC Ltd, ABC Limited)...",
        help="选中多个名字后，系统会自动将它们的数据合并在一起进行分析。"
    )

if not target_companies:
    st.info("👈 请在左侧至少选择一个公司查看详情。")
    st.stop()

# --- 3. 提取特定公司数据 (多选逻辑) ---
df_target_raw = df_scope[
    (df_scope['importer_name'].isin(target_companies)) | 
    (df_scope['exporter_name'].isin(target_companies))
].copy()

if 'Species' not in df_target_raw.columns:
    df_target_raw['Species'] = df_target_raw['product_desc_text'].apply(utils.identify_species)

# --- 4. 增强筛选工具栏 (Analysis Filters) ---
st.divider()
st.markdown("#### 🛠️ Analysis Filters (分析筛选)")

c_f1, c_f2, c_f3, c_f4 = st.columns(4)

# Filter 1: Unit
unique_units = df_target_raw['quantity_unit'].unique().tolist()
default_unit_idx = 0
for i, u in enumerate(unique_units):
    if str(u).upper() in ['M3', 'MTQ', 'CBM']: default_unit_idx = i; break

with c_f1:
    target_unit = st.selectbox("1️⃣ 统计单位 (Unit):", unique_units, index=default_unit_idx)

# Filter 2: Role
with c_f2:
    role_options = ["All (全部)", "Import (As Buyer)", "Export (As Seller)"]
    selected_role = st.selectbox("2️⃣ 交易角色 (Trade Role):", role_options)

# Filter 3: Partner Country
def get_partner_country(row):
    if row['importer_name'] in target_companies: return row['origin_name'] 
    elif row['exporter_name'] in target_companies: return row['dest_name']
    return "Unknown"

df_target_raw['Partner_Country'] = df_target_raw.apply(get_partner_country, axis=1)
available_countries = sorted(df_target_raw['Partner_Country'].unique().tolist())

with c_f3:
    selected_countries = st.multiselect("3️⃣ 对手国家 (Partner Country):", available_countries, default=[])

# Filter 4: Product Category
available_sub_cats = set()
current_company_hs = df_target_raw['hs_code'].astype(str).unique()
for cat, codes in config.HS_CODES_MAP.items():
    if any(str(h).startswith(c) for h in current_company_hs for c in codes):
        available_sub_cats.add(cat)
sorted_sub_cats = sorted(list(available_sub_cats))

with c_f4:
    selected_prod_cat = st.selectbox("4️⃣ 产品类别 (Product Category):", ["All (全部)"] + sorted_sub_cats)

# --- 执行筛选 ---
df_clean = df_target_raw[df_target_raw['quantity_unit'] == target_unit].copy()

if "Import" in selected_role:
    df_clean = df_clean[df_clean['importer_name'].isin(target_companies)]
elif "Export" in selected_role:
    df_clean = df_clean[df_clean['exporter_name'].isin(target_companies)]

if selected_countries:
    df_clean = df_clean[df_clean['Partner_Country'].isin(selected_countries)]

if selected_prod_cat != "All (全部)":
    cat_codes = config.HS_CODES_MAP[selected_prod_cat]
    df_clean = df_clean[df_clean['hs_code'].astype(str).apply(lambda x: any(x.startswith(c) for c in cat_codes))]

# --- KPI ---
total_records = len(df_clean)
total_vol = df_clean['quantity'].sum()
total_val = df_clean['total_value_usd'].sum()
avg_price = (total_val / total_vol) if total_vol > 0 else 0

with c_kpi_role:
    st.info(f"**Selected:** {len(target_companies)} Companies | **Role:** {selected_role}")
    
k1, k2, k3, k4 = st.columns(4)
k1.metric("筛选后记录数", total_records)
k2.metric(f"总货量 ({target_unit})", f"{total_vol:,.0f}")
k3.metric("总金额 (USD)", f"${total_val:,.0f}")
k4.metric(f"加权均价", f"${avg_price:,.0f}")

st.divider()

if df_clean.empty:
    st.warning("⚠️ 当前筛选条件下无数据。")
    st.stop()

# ==========================================
# 📊 第一部分：贸易网络 (角色翻页)
# ==========================================
st.subheader("🤝 贸易网络 (Trade Network)")

has_buy_records = not df_clean[df_clean['importer_name'].isin(target_companies)].empty
has_sell_records = not df_clean[df_clean['exporter_name'].isin(target_companies)].empty

# [NEW] 改为按角色翻页，默认显示销售
tab_sell, tab_buy = st.tabs(["🏭 Sales (销售/出口)", "🛒 Purchase (采购/进口)"])

# --- Tab 1: Sales ---
with tab_sell:
    if has_sell_records:
        df_sell = df_clean[df_clean['exporter_name'].isin(target_companies)]
        
        c1, c2 = st.columns(2)
        
        # Chart 1: Volume (Red Theme)
        with c1:
            top_cus_vol = df_sell.groupby('importer_name')['quantity'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_vol = px.bar(
                top_cus_vol, y='importer_name', x='quantity', orientation='h', 
                title=f"Top Customers by Volume ({target_unit})", 
                color='quantity', color_continuous_scale='Reds', text_auto='.2s'
            )
            st.plotly_chart(fig_vol, use_container_width=True)
            
        # Chart 2: Value (Red Theme)
        with c2:
            top_cus_val = df_sell.groupby('importer_name')['total_value_usd'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_val = px.bar(
                top_cus_val, y='importer_name', x='total_value_usd', orientation='h', 
                title=f"Top Customers by Value (USD)", 
                color='total_value_usd', color_continuous_scale='Reds', text_auto='.2s'
            )
            st.plotly_chart(fig_val, use_container_width=True)
    else:
        st.info("无销售数据 (No Sales Records)")

# --- Tab 2: Purchase ---
with tab_buy:
    if has_buy_records:
        df_buy = df_clean[df_clean['importer_name'].isin(target_companies)]
        
        c1, c2 = st.columns(2)
        
        # Chart 1: Volume (Blue Theme)
        with c1:
            top_sup_vol = df_buy.groupby('exporter_name')['quantity'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_vol = px.bar(
                top_sup_vol, y='exporter_name', x='quantity', orientation='h', 
                title=f"Top Suppliers by Volume ({target_unit})", 
                color='quantity', color_continuous_scale='Blues', text_auto='.2s'
            )
            st.plotly_chart(fig_vol, use_container_width=True)
            
        # Chart 2: Value (Blue Theme)
        with c2:
            top_sup_val = df_buy.groupby('exporter_name')['total_value_usd'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_val = px.bar(
                top_sup_val, y='exporter_name', x='total_value_usd', orientation='h', 
                title=f"Top Suppliers by Value (USD)", 
                color='total_value_usd', color_continuous_scale='Blues', text_auto='.2s'
            )
            st.plotly_chart(fig_val, use_container_width=True)
    else:
        st.info("无采购数据 (No Purchase Records)")

st.divider()

# ==========================================
# 📊 第二部分：产品与趋势 (使用 CORP_PALETTE)
# ==========================================
st.subheader("🌲 产品与趋势 (Product & Trend)")

c_prod1, c_prod2 = st.columns(2)
df_clean['Month'] = pd.to_datetime(df_clean['transaction_date']).dt.to_period('M').astype(str)

with c_prod1:
    species_chart = df_clean.groupby('Species')['quantity'].sum().reset_index()
    fig_pie = px.pie(
        species_chart, names='Species', values='quantity', hole=0.4, 
        title=f"树种结构 (Species Share - {target_unit})",
        color_discrete_sequence=CORP_PALETTE
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_pie, use_container_width=True)

with c_prod2:
    trend_df = df_clean.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
    fig_trend = px.bar(
        trend_df, x='Month', y='quantity', color='Species', 
        title=f"月度交易趋势 (Monthly Trend - {target_unit})", 
        barmode='stack',
        color_discrete_sequence=CORP_PALETTE
    )
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# ==========================================
# 📊 第三部分：供应链趋势 (使用 COOL/WARM DISTINCT)
# ==========================================
st.subheader("🚢 供应链趋势 (Supply Chain Trends)")
st.caption(f"分析 {target_companies} 的月度进出口流向变化 (by Origin & Dest)")

c_org_trend, c_dest_trend = st.columns(2)

with c_org_trend:
    # 原产国 - Cool Distinct
    trend_origin = df_clean.groupby(['Month', 'origin_name'])['quantity'].sum().reset_index()
    fig_org = px.bar(
        trend_origin, x='Month', y='quantity', color='origin_name', 
        title=f"月度原产国趋势 (Origin Trend - {target_unit})", 
        barmode='group', 
        color_discrete_sequence=COOL_DISTINCT
    )
    st.plotly_chart(fig_org, use_container_width=True)

with c_dest_trend:
    # 目的国 - Warm Distinct
    trend_dest = df_clean.groupby(['Month', 'dest_name'])['quantity'].sum().reset_index()
    fig_dest = px.bar(
        trend_dest, x='Month', y='quantity', color='dest_name', 
        title=f"月度目的国趋势 (Dest Trend - {target_unit})", 
        barmode='group', 
        color_discrete_sequence=WARM_DISTINCT
    )
    st.plotly_chart(fig_dest, use_container_width=True)

st.divider()

# ==========================================
# 📊 第四部分：价格趋势 (使用 CORP_PALETTE)
# ==========================================
st.subheader("💰 价格趋势 (Price Analysis)")
st.caption(f"月度加权平均单价趋势 (Weighted Avg Price - USD/{target_unit})")

price_group = df_clean.groupby(['Month', 'Species'])
price_trend_df = pd.DataFrame({
    'total_val': price_group['total_value_usd'].sum(),
    'total_qty': price_group['quantity'].sum()
}).reset_index()

price_trend_df['avg_price'] = price_trend_df.apply(
    lambda x: x['total_val'] / x['total_qty'] if x['total_qty'] > 0 else 0, axis=1
)

fig_price = px.bar(
    price_trend_df, 
    x='Month', 
    y='avg_price', 
    color='Species', 
    barmode='group',
    title=f"各树种单价对比 (Unit Price Comparison)",
    text_auto='.0f',
    color_discrete_sequence=CORP_PALETTE
)
fig_price.update_layout(yaxis_title=f"Price (USD/{target_unit})", hovermode="x unified")
st.plotly_chart(fig_price, use_container_width=True)

st.divider()

# ==========================================
# 📋 详细数据
# ==========================================
with st.expander(f"📄 查看筛选后的详细数据 ({len(df_clean)} records)"):
    display_cols = ['transaction_date', 'hs_code', 'Species', 'origin_name', 'dest_name', 'Partner_Country', 'quantity', 'quantity_unit', 'total_value_usd', 'exporter_name', 'importer_name']
    final_cols = [c for c in display_cols if c in df_clean.columns]
    st.dataframe(df_clean[final_cols].sort_values('transaction_date', ascending=False), use_container_width=True, hide_index=True)