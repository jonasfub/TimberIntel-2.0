import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import sys
import os

# ==========================================
# 0. 路径设置
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
    st.stop()

df_raw = st.session_state['analysis_df'].copy()

# ==========================================
# 3. 数据清洗与增强 (预处理)
# ==========================================
# 数值转换
df_raw['quantity'] = pd.to_numeric(df_raw['quantity'], errors='coerce').fillna(0)
df_raw['total_value_usd'] = pd.to_numeric(df_raw['total_value_usd'], errors='coerce').fillna(0)
df_raw = df_raw[df_raw['quantity'] > 0]
target_unit = df_raw['quantity_unit'].mode()[0] if not df_raw['quantity_unit'].empty else "Unknown"

# 日期格式
df_raw['transaction_date'] = pd.to_datetime(df_raw['transaction_date'])
df_raw['Month'] = df_raw['transaction_date'].dt.to_period('M').astype(str)

# 补全 Species
if 'Species' not in df_raw.columns:
    if 'product_desc_text' in df_raw.columns:
        df_raw['Species'] = df_raw['product_desc_text'].apply(utils.identify_species)
    else:
        df_raw['Species'] = 'Unknown'

# 补全国家名
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
# 4. 侧边栏筛选器 (Sidebar Filters)
# ==========================================
with st.sidebar:
    st.header("🔍 Cockpit Filters")
    
    # 日期
    min_date = df_raw['transaction_date'].min().date()
    max_date = df_raw['transaction_date'].max().date()
    date_range = st.date_input("📅 Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    
    st.divider()
    
    # 分类筛选
    all_origins = sorted(df_raw['origin_name'].unique().astype(str))
    sel_origins = st.multiselect("🛫 Origin (出口国)", all_origins, placeholder="All Origins")
    
    all_species = sorted(df_raw['Species'].unique().astype(str))
    sel_species = st.multiselect("🌲 Species (树种)", all_species, placeholder="All Species")
    
    all_dests = sorted(df_raw['dest_name'].unique().astype(str))
    sel_dests = st.multiselect("🛬 Destination (进口国)", all_dests, placeholder="All Destinations")

# ==========================================
# 5. 执行筛选逻辑
# ==========================================
mask = pd.Series(True, index=df_raw.index)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
    mask &= (df_raw['transaction_date'].dt.date >= start_d) & (df_raw['transaction_date'].dt.date <= end_d)

if sel_origins: mask &= df_raw['origin_name'].isin(sel_origins)
if sel_species: mask &= df_raw['Species'].isin(sel_species)
if sel_dests: mask &= df_raw['dest_name'].isin(sel_dests)

df = df_raw[mask].copy()

# 侧边栏统计
with st.sidebar:
    st.divider()
    st.metric("Records Found", f"{len(df):,}")
    total_vol = df['quantity'].sum()
    total_val = df['total_value_usd'].sum()
    avg_price_global = total_val / total_vol if total_vol > 0 else 0
    
    st.metric(f"Total Vol ({target_unit})", f"{total_vol:,.0f}")
    st.metric("Avg Price (All)", f"${avg_price_global:,.1f}")

if df.empty:
    st.error("❌ No data matches your filters.")
    st.stop()

# ==========================================
# 6. 图表渲染区域
# ==========================================

# ------------------------------------------
# Row 1: Volume Trend (数量趋势)
# ------------------------------------------
st.subheader("1. 📈 Volume Trends (数量趋势)")

with st.container():
    # 数据聚合
    vol_data = df.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
    months = sorted(vol_data['Month'].unique().tolist())
    species_list = sorted(vol_data['Species'].unique().tolist())
    
    vol_series = []
    for sp in species_list:
        sp_data = vol_data[vol_data['Species'] == sp].set_index('Month').reindex(months, fill_value=0)['quantity'].tolist()
        vol_series.append({
            "name": sp,
            "type": "bar",
            "stack": "total",
            "emphasis": {"focus": "series"},
            "data": sp_data,
            "animationDelay": 200
        })

    option_vol = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": species_list, "top": "bottom", "type": "scroll"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "toolbox": {"feature": {"magicType": {"type": ["line", "bar", "stack"]}, "saveAsImage": {}}},
        "dataZoom": [{"type": "slider", "xAxisIndex": 0, "start": 0, "end": 100}, {"type": "inside"}],
        "xAxis": {"type": "category", "data": months},
        "yAxis": {"type": "value", "name": f"Vol ({target_unit})"},
        "series": vol_series
    }
    st_echarts(options=option_vol, height="400px", key="echart_vol")

st.divider()

# ------------------------------------------
# Row 2: Price Trend (单价趋势) [修改为柱状图 📊]
# ------------------------------------------
st.subheader("2. 💰 Price Trends (单价走势)")
st.caption(f"Calculated as: Total Value / Total Quantity (Unit: USD / {target_unit})")

with st.container():
    # 数据聚合
    price_agg = df.groupby(['Month', 'Species'])[['total_value_usd', 'quantity']].sum().reset_index()
    price_agg['avg_price'] = price_agg.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
    
    price_series = []
    for sp in species_list:
        sp_df = price_agg[price_agg['Species'] == sp].set_index('Month').reindex(months)
        sp_price_data = [x if pd.notnull(x) else None for x in sp_df['avg_price']]
        
        price_series.append({
            "name": sp,
            "type": "bar",   # <--- 改为 bar
            # "stack": "total", # 注意：单价不建议堆叠，所以注释掉这一行，让它们并排显示
            "emphasis": {"focus": "series"},
            "data": sp_price_data,
            "markPoint": {
                "data": [
                    {"type": "max", "name": "Max"},
                    {"type": "min", "name": "Min"}
                ]
            }
        })

    option_price = {
        "tooltip": {"trigger": "axis", "valueFormatter": "(value) => '$' + Number(value).toFixed(1)"},
        "legend": {"data": species_list, "top": "bottom", "type": "scroll"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "toolbox": {
            "feature": {
                "magicType": {"type": ["line", "bar"]}, # 允许用户切回折线图
                "saveAsImage": {}
            }
        },
        "dataZoom": [{"type": "slider", "xAxisIndex": 0, "start": 0, "end": 100}, {"type": "inside"}],
        "xAxis": {"type": "category", "data": months},
        "yAxis": {"type": "value", "name": "USD/Unit", "scale": True},
        "series": price_series
    }
    st_echarts(options=option_price, height="400px", key="echart_price")

st.divider()

# ------------------------------------------
# Row 3: Sankey Flow (桑基图)
# ------------------------------------------
st.subheader("3. 🌊 Trade Flow: Origin ➡ Species ➡ Dest")

# 数据准备
sankey_df = df.copy()
sankey_df['origin_name'] = sankey_df['origin_name'].fillna("Unknown").astype(str)
sankey_df['dest_name'] = sankey_df['dest_name'].fillna("Unknown").astype(str)
sankey_df['Species'] = sankey_df['Species'].fillna("Unknown").astype(str)

# 动态 Top N
if len(sankey_df) > 500:
    top_n = 20
    top_origins = sankey_df.groupby('origin_name')['quantity'].sum().nlargest(top_n).index
    top_dests = sankey_df.groupby('dest_name')['quantity'].sum().nlargest(top_n).index
    def format_origin(x): return f"🛫 {x}" if x in top_origins else "🛫 Other Origins"
    def format_dest(x): return f"🛬 {x}" if x in top_dests else "🛬 Other Dests"
else:
    def format_origin(x): return f"🛫 {x}"
    def format_dest(x): return f"🛬 {x}"

sankey_df['source_node'] = sankey_df['origin_name'].apply(format_origin)
sankey_df['target_node'] = sankey_df['dest_name'].apply(format_dest)
sankey_df['mid_node']    = sankey_df['Species'] 

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
    st.info("ℹ️ Not enough data to render Sankey flow.")

st.divider()

# ------------------------------------------
# Row 4: Sunburst (旭日图)
# ------------------------------------------
c_sun, c_info = st.columns([3, 1])

with c_sun:
    st.subheader("4. 🍩 Market Hierarchy (Origin > Species)")
    
    sun_data = []
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
            "itemStyle": {"borderRadius": 4, "borderWidth": 2}
        }
    }
    st_echarts(options=option_sunburst, height="500px", key="echart_sun")

with c_info:
    st.markdown("### 🔍 Inspector")
    st.markdown("**Current Filters:**")
    if sel_origins: st.markdown(f"- **Origin:** {', '.join(sel_origins)}")
    else: st.markdown("- **Origin:** All")
    if sel_species: st.markdown(f"- **Species:** {', '.join(sel_species)}")
    else: st.markdown("- **Species:** All")