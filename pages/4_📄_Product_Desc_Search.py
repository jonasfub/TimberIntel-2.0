import streamlit as st
import pandas as pd
import plotly.express as px
import config
import utils

# --- 1. 页面配置 ---
st.set_page_config(page_title="Product Desc Search", page_icon="📄", layout="wide")

st.title("📄 Product Description Search (产品描述深度搜索)")
st.caption("基于报关单原始产品描述 (product_desc_text) 的自由文本检索引擎。")

# --- 2. 数据守门员 ---
if 'analysis_df' not in st.session_state or st.session_state['analysis_df'].empty:
    st.warning("⚠️ 请先在【首页 (Timber Intel Core)】加载数据。")
    st.info("💡 提示：本页面搜索范围为首页已加载并缓存的本地数据，无需消耗 API 额度。")
    st.stop()

# 获取数据副本
df_raw = st.session_state['analysis_df'].copy()

# 基础清洗：补全名称和树种
def get_name_safe(code):
    if not code: return "Unknown"
    name = config.COUNTRY_NAME_MAP.get(code, code)
    return str(name).split(' (')[0] if '(' in str(name) else str(name)

# 动态映射 HS Code 到产品分类
def map_hs_to_category(hs_code):
    hs_str = str(hs_code)
    if hasattr(config, 'HS_CODES_MAP'):
        for category, codes in config.HS_CODES_MAP.items():
            for c in codes:
                if hs_str.startswith(c):
                    return category
    return "Other Products"

if 'origin_name' not in df_raw.columns:
    df_raw['origin_name'] = df_raw['origin_country_code'].apply(get_name_safe)
if 'dest_name' not in df_raw.columns:
    df_raw['dest_name'] = df_raw['dest_country_code'].apply(get_name_safe)
if 'Species' not in df_raw.columns:
    df_raw['Species'] = df_raw['product_desc_text'].apply(utils.identify_species)
if 'Product_Category' not in df_raw.columns:
    df_raw['Product_Category'] = df_raw['hs_code'].apply(map_hs_to_category)

# --- 3. 侧边栏：全局数据过滤 ---
with st.sidebar:
    st.header("🛠️ Global Filters")
    
    # 1. 单位过滤
    df_raw['quantity_unit'] = df_raw['quantity_unit'].fillna('Unknown')
    available_units = df_raw['quantity_unit'].unique().tolist()
    default_ix = 0
    for i, u in enumerate(available_units):
        if str(u).upper() in ['CBM', 'M3', 'MTQ', 'M3 ']: default_ix = i; break
    
    target_unit = st.selectbox("📏 统计单位 (Unit):", available_units, index=default_ix)
    
    st.divider()
    
    # 2. 产品与 HS Code 过滤 (联动逻辑)
    all_categories = sorted(df_raw['Product_Category'].astype(str).unique())
    sel_categories = st.multiselect("📦 产品分类 (Category):", all_categories, placeholder="留空为全部")
    
    # 动态获取当前选中分类下的 HS Code
    if sel_categories:
        temp_hs_df = df_raw[df_raw['Product_Category'].isin(sel_categories)]
    else:
        temp_hs_df = df_raw
        
    all_hs_codes = sorted(temp_hs_df['hs_code'].astype(str).unique())
    sel_hs_codes = st.multiselect("🔢 海关编码 (HS Code):", all_hs_codes, placeholder="留空为全部")

    st.divider()

    # 3. 国家过滤
    all_origins = sorted(df_raw['origin_name'].astype(str).unique())
    all_dests = sorted(df_raw['dest_name'].astype(str).unique())
    
    sel_origins = st.multiselect("🛫 出口国 (Origin):", all_origins, placeholder="留空为全部")
    sel_dests = st.multiselect("🛬 进口国 (Dest):", all_dests, placeholder="留空为全部")

# 先进行基础过滤
df_filtered = df_raw[df_raw['quantity_unit'] == target_unit].copy()

# 应用新增的产品与编码过滤
if sel_categories: 
    df_filtered = df_filtered[df_filtered['Product_Category'].isin(sel_categories)]
if sel_hs_codes: 
    df_filtered = df_filtered[df_filtered['hs_code'].astype(str).isin(sel_hs_codes)]
    
# 应用国家过滤
if sel_origins: 
    df_filtered = df_filtered[df_filtered['origin_name'].isin(sel_origins)]
if sel_dests: 
    df_filtered = df_filtered[df_filtered['dest_name'].isin(sel_dests)]

# --- 4. 核心功能：文本检索引擎 ---
st.markdown("### 🔍 规格与描述检索 (Description Engine)")

c_search, c_logic = st.columns([3, 1])

with c_search:
    search_query = st.text_input(
        "输入产品描述关键词 (支持多关键词空格分隔):", 
        placeholder="例如: KD S4S PINE 1220...",
        help="不区分大小写。多个关键词请用空格隔开。"
    )

with c_logic:
    st.write("") # 占位对齐
    search_mode = st.radio(
        "多关键词匹配逻辑:", 
        ["AND (包含所有)", "OR (包含任意)"], 
        horizontal=True,
        help="AND: 描述中必须同时包含所有关键词。\nOR: 描述中包含任意一个关键词即可。"
    )

# --- 5. 执行搜索逻辑 ---
df_result = df_filtered.copy()

if search_query.strip():
    keywords = [kw.strip() for kw in search_query.split() if kw.strip()]
    
    if "AND" in search_mode:
        # 必须包含所有关键词
        for kw in keywords:
            df_result = df_result[df_result['product_desc_text'].str.contains(kw, case=False, na=False)]
    else:
        # 包含任意一个即可
        mask = pd.Series(False, index=df_result.index)
        for kw in keywords:
            mask |= df_result['product_desc_text'].str.contains(kw, case=False, na=False)
        df_result = df_result[mask]

# --- 6. 结果呈现 ---
st.divider()

if df_result.empty:
    if search_query:
        st.warning(f"⚠️ 在当前范围内，未找到描述中包含 '{search_query}' 的记录。")
    else:
        st.info("👆 请在上方输入关键词开始检索。")
    st.stop()

# --- KPI 面板 ---
total_records = len(df_result)
total_vol = df_result['quantity'].sum()
total_val = df_result['total_value_usd'].sum()
avg_price = (total_val / total_vol) if total_vol > 0 else 0

st.markdown(f"#### 🎯 检索结果总览 (Results Overview)")
k1, k2, k3, k4 = st.columns(4)
k1.metric("匹配记录数 (Records)", f"{total_records:,}")
k2.metric(f"总货量 ({target_unit})", f"{total_vol:,.0f}")
k3.metric("总金额 (USD)", f"${total_val:,.0f}")
k4.metric(f"均价 (USD/{target_unit})", f"${avg_price:,.1f}")

st.divider()

# --- 宏观图表分析 ---
st.markdown("#### 📊 市场结构与趋势 (Market Structure & Trends)")
c_chart1, c_chart2 = st.columns(2)

with c_chart1:
    # 目的国分布
    dest_dist = df_result.groupby('dest_name')['quantity'].sum().nlargest(10).reset_index()
    fig_dest = px.pie(
        dest_dist, names='dest_name', values='quantity', hole=0.4,
        title=f"Top 10 目的国分布 (By Dest)",
        color_discrete_sequence=px.colors.sequential.Teal
    )
    fig_dest.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig_dest, use_container_width=True)

with c_chart2:
    # 月度趋势
    df_result['Month'] = pd.to_datetime(df_result['transaction_date']).dt.to_period('M').astype(str)
    trend_df = df_result.groupby(['Month', 'origin_name'])['quantity'].sum().reset_index()
    fig_trend = px.bar(
        trend_df, x='Month', y='quantity', color='origin_name',
        title=f"月度进口量趋势 (By Origin)",
        barmode='stack',
        color_discrete_sequence=px.colors.qualitative.Pastel
    )
    st.plotly_chart(fig_trend, use_container_width=True)

st.divider()

# --- 头部企业画像 ---
st.markdown("#### 🏢 头部企业画像 (Top Players)")
st.caption("基于检索结果自动聚合的采购与供应巨头。")

c_imp, c_exp = st.columns(2)

# 确保有名字字段且处理空值
df_result['importer_name'] = df_result['importer_name'].fillna('Unknown')
df_result['exporter_name'] = df_result['exporter_name'].fillna('Unknown')

with c_imp:
    # Top 10 Importers (采购商)
    top_imp = df_result.groupby('importer_name')['quantity'].sum().nlargest(10).sort_values(ascending=True).reset_index()
    fig_imp = px.bar(
        top_imp, x='quantity', y='importer_name', orientation='h',
        title=f"Top 10 采购商 (Importers)",
        color='quantity', color_continuous_scale='Blues',
        text_auto='.2s'
    )
    fig_imp.update_layout(yaxis_title="")
    st.plotly_chart(fig_imp, use_container_width=True)
    
with c_exp:
    # Top 10 Exporters (供应商)
    top_exp = df_result.groupby('exporter_name')['quantity'].sum().nlargest(10).sort_values(ascending=True).reset_index()
    fig_exp = px.bar(
        top_exp, x='quantity', y='exporter_name', orientation='h',
        title=f"Top 10 供应商 (Exporters)",
        color='quantity', color_continuous_scale='Reds',
        text_auto='.2s'
    )
    fig_exp.update_layout(yaxis_title="")
    st.plotly_chart(fig_exp, use_container_width=True)

st.divider()

# --- 详细数据表格 ---
st.markdown("#### 📋 匹配详情数据 (Matched Records)")
st.caption("你可以在这里直接检查对应的产品原始描述。")

display_cols = ['transaction_date', 'Product_Category', 'hs_code', 'product_desc_text', 'quantity', 'quantity_unit', 'total_value_usd', 'origin_name', 'dest_name', 'importer_name', 'exporter_name']
final_cols = [c for c in display_cols if c in df_result.columns]

st.dataframe(
    df_result[final_cols].sort_values('transaction_date', ascending=False),
    use_container_width=True,
    hide_index=True,
    height=400
)