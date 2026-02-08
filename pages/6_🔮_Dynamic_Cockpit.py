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

# 3.1 基础数值转换与空值填充
df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
df['total_value_usd'] = pd.to_numeric(df['total_value_usd'], errors='coerce').fillna(0)

# 获取单位 (取出现最多的单位)
target_unit = df['quantity_unit'].mode()[0] if not df['quantity_unit'].empty else "Unknown"

# 过滤无效数据 (数量为0的行)
df = df[df['quantity'] > 0]

# 3.2 生成 'Month' 列 (修复 KeyError)
# 确保 transaction_date 是 datetime 类型
df['transaction_date'] = pd.to_datetime(df['transaction_date'])
df['Month'] = df['transaction_date'].dt.to_period('M').astype(str)

# 3.3 生成 'Species' 列 (修复 KeyError)
if 'Species' not in df.columns:
    if 'product_desc_text' in df.columns:
        # 使用 utils 中的函数识别树种
        df['Species'] = df['product_desc_text'].apply(utils.identify_species)
    else:
        df['Species'] = 'Unknown'

# 3.4 生成国家全名 'origin_name' & 'dest_name' (修复 KeyError)
def get_country_name_en(code):
    if pd.isna(code) or code == "" or code is None: return "Unknown"
    full_name = config.COUNTRY_NAME_MAP.get(code, code)
    full_name_str = str(full_name)
    if '(' in full_name_str: return full_name_str.split(' (')[0]
    return full_name_str

if 'origin_name' not in df.columns:
    df['origin_name'] = df['origin_country_code'].apply(get_country_name_en)

if 'dest_name' not in df.columns:
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
# [修复说明] 防止空图表：1.填充NaN 2.给节点加前缀防止闭环
st.subheader("2. 🌊 Trade Flow: Origin ➡ Species ➡ Dest")
st.caption("Trace the timber flow. Hover to see details.")

sankey_df = df.copy()

# 1. 强制转字符串，防止 NaN 报错
sankey_df['origin_name'] = sankey_df['origin_name'].fillna("Unknown Origin").astype(str)
sankey_df['dest_name'] = sankey_df['dest_name'].fillna("Unknown Dest").astype(str)
sankey_df['Species'] = sankey_df['Species'].fillna("Unknown Species").astype(str)

# 2. 筛选 Top N (简化图表，防止太乱)
top_n = 15
top_origins = sankey_df.groupby('origin_name')['quantity'].sum().nlargest(top_n).index
top_dests = sankey_df.groupby('dest_name')['quantity'].sum().nlargest(top_n).index

# 3. 添加前缀 (关键步骤：防止 Origin='China' 和 Dest='China' 造成死循环)
def format_origin(x):
    name = x if x in top_origins else 'Other Origins'
    return f"🛫 {name}"  # 添加起飞图标

def format_dest(x):
    name = x if x in top_dests else 'Other Dests'
    return f"🛬 {name}"  # 添加降落图标

sankey_df['source_node'] = sankey_df['origin_name'].apply(format_origin)
sankey_df['target_node'] = sankey_df['dest_name'].apply(format_dest)
sankey_df['mid_node']    = sankey_df['Species'] 

# 4. 构造连接数据
# Link 1: Origin -> Species
flow1 = sankey_df.groupby(['source_node', 'mid_node'])['quantity'].sum().reset_index()
flow1.columns = ['source', 'target', 'value']

# Link 2: Species -> Dest
flow2 = sankey_df.groupby(['mid_node', 'target_node'])['quantity'].sum().reset_index()
flow2.columns = ['source', 'target', 'value']

links_df = pd.concat([flow1, flow2], axis=0)
links_df = links_df[links_df['value'] > 0] # 过滤掉 0 值

# 5. 渲染
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
    st.warning("⚠️ No valid flow data available for Sankey diagram.")

st.divider()

# --- Row 3: 旭日图 (Sunburst) ---
c_sun, c_info = st.columns([3, 1])

with c_sun:
    st.subheader("3. 🍩 Market Hierarchy (Origin > Species)")
    
    # 使用之前处理好的 sankey_df (带有 source_node 分组) 来做旭日图，或者重新聚合
    # 这里为了名字好看，重新用原始名称聚合
    sun_df = df.copy()
    sun_df['origin_group'] = sun_df['origin_name'].apply(lambda x: x if x in top_origins else 'Other Origins')
    
    sun_data = []
    # 1. 第一层：Origin
    for origin in sun_df['origin_group'].unique():
        origin_df = sun_df[sun_df['origin_group'] == origin]
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