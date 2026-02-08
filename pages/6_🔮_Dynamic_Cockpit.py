import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import sys
import os

# ==========================================
# 0. 路径设置 (为了能引用根目录的 config 和 utils)
# ==========================================
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import utils
import config

# ==========================================
# 1. 页面基础设置
# ==========================================
st.set_page_config(page_title="Timber Dynamic Cockpit", page_icon="🔮", layout="wide")

st.title("🔮 Timber Intel - Dynamic Cockpit")
st.markdown("""
<style>
    .block-container {padding-top: 1rem;}
</style>
""", unsafe_allow_html=True)
st.caption("Interactive visualization with real-time filtering. Data source: Shared from Home Page.")

# ==========================================
# 2. 守门员逻辑 (检查是否有数据)
# ==========================================
if 'analysis_df' not in st.session_state or st.session_state['analysis_df'].empty:
    st.warning("⚠️ No data loaded. Please go to the **Home Page**, select a date range, and click 'Load Analysis Report'.")
    st.info("👈 You can navigate back using the sidebar.")
    st.stop()  # 停止执行后续代码

# 获取原始数据副本
df_raw = st.session_state['analysis_df'].copy()

# ==========================================
# 3. 数据清洗与增强 (预处理)
# ==========================================
# 3.1 基础数值转换
df_raw['quantity'] = pd.to_numeric(df_raw['quantity'], errors='coerce').fillna(0)
df_raw['total_value_usd'] = pd.to_numeric(df_raw['total_value_usd'], errors='coerce').fillna(0)
# 过滤无效数据
df_raw = df_raw[df_raw['quantity'] > 0]
# 获取单位
target_unit = df_raw['quantity_unit'].mode()[0] if not df_raw['quantity_unit'].empty else "Unknown"

# 3.2 确保日期格式正确
df_raw['transaction_date'] = pd.to_datetime(df_raw['transaction_date'])
df_raw['Month'] = df_raw['transaction_date'].dt.to_period('M').astype(str)

# 3.3 补全 Species
if 'Species' not in df_raw.columns:
    if 'product_desc_text' in df_raw.columns:
        df_raw['Species'] = df_raw['product_desc_text'].apply(utils.identify_species)
    else:
        df_raw['Species'] = 'Unknown'

# 3.4 补全国家名
def get_country_name_en(code):
    if pd.isna(code) or code == "" or code is None: return "Unknown"
    full_name = config.COUNTRY_NAME_MAP.get(code, code)
    full_name_str = str(full_name)
    if '(' in full_name_str: return full_name_str.split(' (')[0]
    return full_name_str

if 'origin_name' not in df_raw.columns:
    df_raw['origin_name'] = df_raw['origin_country_code'].apply(get_country_name_en)
if 'dest_name' not in df_raw.columns:
    df_raw['dest_name'] = df_raw['dest_country_code'].apply(get_country_name_en)

# ==========================================
# 4. 侧边栏筛选器 (Sidebar Filters) 🔍
# ==========================================
with st.sidebar:
    st.header("🔍 Cockpit Filters")
    st.caption("Filter data locally without reloading.")
    
    # 4.1 日期筛选
    min_date = df_raw['transaction_date'].min().date()
    max_date = df_raw['transaction_date'].max().date()
    
    date_range = st.date_input(
        "📅 Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date
    )
    
    st.divider()
    
    # 4.2 分类筛选 (动态获取选项)
    # Origin
    all_origins = sorted(df_raw['origin_name'].unique().astype(str))
    sel_origins = st.multiselect("🛫 Origin (出口国)", all_origins, placeholder="All Origins")
    
    # Species
    all_species = sorted(df_raw['Species'].unique().astype(str))
    sel_species = st.multiselect("🌲 Species (树种)", all_species, placeholder="All Species")
    
    # Destination
    all_dests = sorted(df_raw['dest_name'].unique().astype(str))
    sel_dests = st.multiselect("🛬 Destination (进口国)", all_dests, placeholder="All Destinations")

# ==========================================
# 5. 执行筛选逻辑
# ==========================================
mask = pd.Series(True, index=df_raw.index)

# 日期过滤
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
    mask &= (df_raw['transaction_date'].dt.date >= start_d) & (df_raw['transaction_date'].dt.date <= end_d)

# 类别过滤
if sel_origins:
    mask &= df_raw['origin_name'].isin(sel_origins)
if sel_species:
    mask &= df_raw['Species'].isin(sel_species)
if sel_dests:
    mask &= df_raw['dest_name'].isin(sel_dests)

# 应用筛选
df = df_raw[mask].copy()

# 显示筛选结果统计
with st.sidebar:
    st.divider()
    st.metric("Records Found", f"{len(df):,}")
    st.metric(f"Total Vol ({target_unit})", f"{df['quantity'].sum():,.0f}")

if df.empty:
    st.error("❌ No data matches your filters. Please adjust the sidebar filters.")
    st.stop()

# ==========================================
# 6. 图表渲染区域 (使用 df)
# ==========================================

# --- Row 1: 趋势分析 (Trend) ---
st.subheader("1. ⏳ Time-Series Explorer (时间轴缩放)")
with st.container():
    trend_data = df.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
    months = sorted(trend_data['Month'].unique().tolist())
    species_list = sorted(trend_data['Species'].unique().tolist())
    
    series_list = []
    for sp in species_list:
        sp_data = trend_data[trend_data['Species'] == sp].set_index('Month').reindex(months, fill_value=0)['quantity'].tolist()
        series_list.append({
            "name": sp,
            "type": "bar",
            "stack": "total",
            "emphasis": {"focus": "series"},
            "data": sp_data,
            "animationDelay": 300
        })

    option_trend = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": species_list, "top": "bottom", "type": "scroll"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "toolbox": {
            "feature": {
                "magicType": {"type": ["line", "bar", "stack"]},
                "saveAsImage": {"title": "Save"}
            }
        },
        "dataZoom": [
            {"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100},
            {"type": "inside", "xAxisIndex": [0]}
        ],
        "xAxis": {"type": "category", "data": months},
        "yAxis": {"type": "value", "name": f"Vol ({target_unit})"},
        "series": series_list
    }
    st_echarts(options=option_trend, height="400px", key="echart_trend")

st.divider()

# --- Row 2: 桑基图 (Sankey) ---
st.subheader("2. 🌊 Trade Flow: Origin ➡ Species ➡ Dest")

# 数据准备
sankey_df = df.copy()
sankey_df['origin_name'] = sankey_df['origin_name'].fillna("Unknown").astype(str)
sankey_df['dest_name'] = sankey_df['dest_name'].fillna("Unknown").astype(str)
sankey_df['Species'] = sankey_df['Species'].fillna("Unknown").astype(str)

# Top N 限制 (仅在节点过多时启用)
if len(sankey_df) > 500:
    top_n = 20
    top_origins = sankey_df.groupby('origin_name')['quantity'].sum().nlargest(top_n).index
    top_dests = sankey_df.groupby('dest_name')['quantity'].sum().nlargest(top_n).index
    
    def format_origin(x): return f"🛫 {x}" if x in top_origins else "🛫 Other Origins"
    def format_dest(x): return f"🛬 {x}" if x in top_dests else "🛬 Other Dests"
else:
    # 数据量小时显示全部
    def format_origin(x): return f"🛫 {x}"
    def format_dest(x): return f"🛬 {x}"

sankey_df['source_node'] = sankey_df['origin_name'].apply(format_origin)
sankey_df['target_node'] = sankey_df['dest_name'].apply(format_dest)
sankey_df['mid_node']    = sankey_df['Species'] 

# 构造 Links
flow1 = sankey_df.groupby(['source_node', 'mid_node'])['quantity'].sum().reset_index()
flow1.columns = ['source', 'target', 'value']
flow2 = sankey_df.groupby(['mid_node', 'target_node'])['quantity'].sum().reset_index()
flow2.columns = ['source', 'target', 'value']

links_df = pd.concat([flow1, flow2], axis=0)
links_df = links_df[links_df['value'] > 0]

if not links_df.empty:
    unique_nodes = list(set(links_df['source']).union(set(links_df['target'])))
    nodes = [{"name": n} for n in unique_nodes]
    links = links_df.to_dict(orient='records')

    option_sankey = {
        "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
        "series": [{
            "type": "sankey",
            "layout": "none",
            "data": nodes,
            "links": links,
            "emphasis": {"focus": "adjacency"},
            "nodeWidth": 20,
            "levels": [
                {"depth": 0, "itemStyle": {"color": "#fbb4ae"}, "lineStyle": {"color": "source", "opacity": 0.2}},
                {"depth": 1, "itemStyle": {"color": "#b3cde3"}, "lineStyle": {"color": "source", "opacity": 0.2}},
                {"depth": 2, "itemStyle": {"color": "#ccebc5"}, "lineStyle": {"color": "source", "opacity": 0.2}}
            ],
            "lineStyle": {"curveness": 0.5},
            "label": {"color": "rgba(0,0,0,0.7)", "fontFamily": "Arial", "fontSize": 12}
        }]
    }
    st_echarts(options=option_sankey, height="600px", key="echart_sankey")
else:
    st.info("ℹ️ Not enough data to render Sankey flow with current filters.")

st.divider()

# --- Row 3: 旭日图 (Sunburst) ---
c_sun, c_info = st.columns([3, 1])

with c_sun:
    st.subheader("3. 🍩 Market Hierarchy (Origin > Species)")
    
    # 使用筛选后的 df
    sun_data = []
    # 按当前筛选的 Origin 分组
    for origin in sorted(df['origin_name'].unique()):
        origin_df = df[df['origin_name'] == origin]
        origin_val = origin_df['quantity'].sum()
        
        children = []
        for sp in sorted(origin_df['Species'].unique()):
            val = origin_df[origin_df['Species'] == sp]['quantity'].sum()
            if val > 0:
                children.append({"name": sp, "value": val})
        
        if origin_val > 0:
            sun_data.append({"name": origin, "children": children})

    option_sunburst = {
        "tooltip": {"trigger": "item"},
        "series": {
            "type": "sunburst",
            "data": sun_data,
            "radius": [0, "90%"],
            "label": {"rotate": "radial"},
            "emphasis": {"focus": "ancestor"},
            "itemStyle": {
                "borderRadius": 4,
                "borderWidth": 2
            }
        }
    }
    st_echarts(options=option_sunburst, height="500px", key="echart_sun")

with c_info:
    st.markdown("### 🔍 Inspector")
    st.markdown("Use the **Sidebar** on the left to filter specific trade flows.")
    
    st.markdown("**Current Filters:**")
    if sel_origins: st.markdown(f"- **Origin:** {', '.join(sel_origins)}")
    else: st.markdown("- **Origin:** All")
    
    if sel_species: st.markdown(f"- **Species:** {', '.join(sel_species)}")
    else: st.markdown("- **Species:** All")
    
    if sel_dests: st.markdown(f"- **Dest:** {', '.join(sel_dests)}")
    else: st.markdown("- **Dest:** All")