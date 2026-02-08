import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts
import sys
import os

# ==========================================
# 0. 路径设置 (为了能引用根目录的 config 和 utils)
# ==========================================
# 获取当前文件所在目录的上一级目录 (即项目根目录)
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
st.caption("Interactive visualization powered by ECharts. Data source: Shared from Home Page.")

# ==========================================
# 2. 守门员逻辑 (检查是否有数据)
# ==========================================
if 'analysis_df' not in st.session_state or st.session_state['analysis_df'].empty:
    st.warning("⚠️ No data loaded. Please go to the **Home Page**, select a date range, and click 'Load Analysis Report'.")
    st.info("👈 You can navigate back using the sidebar.")
    st.stop()  # 停止执行后续代码

# 获取数据副本，防止修改影响主页
df = st.session_state['analysis_df'].copy()

# ==========================================
# 3. 数据清洗与增强 (关键修复步骤 🛠️)
# ==========================================
# 主页存入 session_state 的通常是原始数据，这里必须重新计算 Month, Species 等字段

# 3.1 基础数值转换
df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
df['total_value_usd'] = pd.to_numeric(df['total_value_usd'], errors='coerce').fillna(0)

# 获取单位 (取出现最多的单位)
target_unit = df['quantity_unit'].mode()[0] if not df['quantity_unit'].empty else "Unknown"

# 过滤无效数据 (数量为0的行)
df = df[df['quantity'] > 0]

# 3.2 生成 'Month' 列 (用于时间轴)
if 'Month' not in df.columns:
    df['transaction_date'] = pd.to_datetime(df['transaction_date'])
    df['Month'] = df['transaction_date'].dt.to_period('M').astype(str)

# 3.3 生成 'Species' 列 (调用 utils)
if 'Species' not in df.columns:
    if 'product_desc_text' in df.columns:
        df['Species'] = df['product_desc_text'].apply(utils.identify_species)
    else:
        df['Species'] = 'Unknown'

# 3.4 生成国家全名 (调用 config)
if 'origin_name' not in df.columns:
    def get_country_name_en(code):
        if pd.isna(code) or code == "" or code is None: return "Unknown"
        full_name = config.COUNTRY_NAME_MAP.get(code, code)
        full_name_str = str(full_name)
        if '(' in full_name_str: return full_name_str.split(' (')[0]
        return full_name_str

    df['origin_name'] = df['origin_country_code'].apply(get_country_name_en)
    df['dest_name'] = df['dest_country_code'].apply(get_country_name_en)

# ==========================================
# 4. 图表渲染区域
# ==========================================

# --- Row 1: 趋势分析 (Trend) ---
st.subheader("1. ⏳ Time-Series Explorer (时间轴缩放)")
with st.container():
    # 数据聚合
    trend_data = df.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
    months = sorted(trend_data['Month'].unique().tolist())
    species_list = trend_data['Species'].unique().tolist()
    
    series_list = []
    for sp in species_list:
        # 重建索引以对齐时间轴 (防止某个月没有数据导致错位)
        sp_data = trend_data[trend_data['Species'] == sp].set_index('Month').reindex(months, fill_value=0)['quantity'].tolist()
        series_list.append({
            "name": sp,
            "type": "bar",
            "stack": "total",
            "emphasis": {"focus": "series"},
            "data": sp_data,
            "animationDelay": 300 # 动画效果
        })

    option_trend = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": species_list, "top": "bottom", "type": "scroll"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "toolbox": {
            "feature": {
                "magicType": {"type": ["line", "bar", "stack"]}, # 魔法切换：堆叠/平铺/折线
                "saveAsImage": {"title": "Save"}
            }
        },
        "dataZoom": [
            {"type": "slider", "show": True, "xAxisIndex": [0], "start": 0, "end": 100}, # 底部滑块
            {"type": "inside", "xAxisIndex": [0]} # 鼠标滚轮缩放
        ],
        "xAxis": {"type": "category", "data": months},
        "yAxis": {"type": "value", "name": f"Vol ({target_unit})"},
        "series": series_list
    }
    st_echarts(options=option_trend, height="450px", key="echart_trend")

st.divider()

# --- Row 2: 桑基图 (Sankey) ---
st.subheader("2. 🌊 Trade Flow: Origin ➡ Species ➡ Dest")
st.caption("Trace the timber flow. Hover to see details.")

# 桑基图数据处理
sankey_df = df.copy()

# 为了图表美观，只取 Top N 的节点，其余归为 "Others" (防止线条太密)
top_n = 15
top_origins = sankey_df.groupby('origin_name')['quantity'].sum().nlargest(top_n).index
top_dests = sankey_df.groupby('dest_name')['quantity'].sum().nlargest(top_n).index

sankey_df['origin_final'] = sankey_df['origin_name'].apply(lambda x: x if x in top_origins else 'Other Origins')
sankey_df['dest_final'] = sankey_df['dest_name'].apply(lambda x: x if x in top_dests else 'Other Dests')

# 构造节点 Link: Origin -> Species
flow1 = sankey_df.groupby(['origin_final', 'Species'])['quantity'].sum().reset_index()
flow1.columns = ['source', 'target', 'value']

# 构造节点 Link: Species -> Dest
flow2 = sankey_df.groupby(['Species', 'dest_final'])['quantity'].sum().reset_index()
flow2.columns = ['source', 'target', 'value']

links_df = pd.concat([flow1, flow2], axis=0)

# 生成唯一节点列表
all_nodes = list(set(links_df['source']).union(set(links_df['target'])))
nodes = [{"name": n} for n in all_nodes]
links = links_df.to_dict(orient='records')

option_sankey = {
    "tooltip": {"trigger": "item", "triggerOn": "mousemove"},
    "series": [{
        "type": "sankey",
        "layout": "none",
        "data": nodes,
        "links": links,
        "emphasis": {"focus": "adjacency"}, # 悬停高亮相关连线
        "levels": [
            {"depth": 0, "itemStyle": {"color": "#fbb4ae"}, "lineStyle": {"color": "source", "opacity": 0.2}},
            {"depth": 1, "itemStyle": {"color": "#b3cde3"}, "lineStyle": {"color": "source", "opacity": 0.2}},
            {"depth": 2, "itemStyle": {"color": "#ccebc5"}, "lineStyle": {"color": "source", "opacity": 0.2}}
        ],
        "lineStyle": {"curveness": 0.5},
        "label": {"color": "rgba(0,0,0,0.7)", "fontFamily": "Arial"}
    }]
}
st_echarts(options=option_sankey, height="600px", key="echart_sankey")

st.divider()

# --- Row 3: 旭日图 (Sunburst) ---
c_sun, c_info = st.columns([3, 1])

with c_sun:
    st.subheader("3. 🍩 Market Hierarchy (Origin > Species)")
    
    # 构造旭日图层级数据
    sun_data = []
    # 1. 第一层：Origin
    # 这里用 origin_final 避免国家太多
    for origin in sankey_df['origin_final'].unique():
        origin_df = sankey_df[sankey_df['origin_final'] == origin]
        origin_val = origin_df['quantity'].sum()
        
        children = []
        # 2. 第二层：Species
        for sp in origin_df['Species'].unique():
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
                "borderRadius": 5,
                "borderWidth": 2
            }
        }
    }
    st_echarts(options=option_sunburst, height="600px", key="echart_sun")

with c_info:
    st.info("Instructions:")
    st.markdown("""
    * **Inner Circle:** Origin Country
    * **Outer Circle:** Species exported
    * **Click:** Click a sector to drill down (Zoom in).
    * **Center Click:** Click the center to zoom out.
    """)