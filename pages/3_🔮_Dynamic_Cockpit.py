import streamlit as st
import pandas as pd
from streamlit_echarts import st_echarts, JsCode
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

# 获取原始数据副本
df_raw = st.session_state['analysis_df'].copy()

# ==========================================
# 3. 核心数据清洗 (Data Cleaning)
# ==========================================

# 3.1 强制数值转换
df_raw['quantity'] = pd.to_numeric(df_raw['quantity'], errors='coerce').fillna(0)
df_raw['total_value_usd'] = pd.to_numeric(df_raw['total_value_usd'], errors='coerce').fillna(0)

# 3.2 港口清洗
def clean_port_name(val):
    s = str(val).strip()
    if '(' in s: return s.split('(')[-1].replace(')', '').strip()
    return s

df_raw['port_of_arrival'] = df_raw['port_of_arrival'].fillna('Unknown').apply(clean_port_name)
if 'port_of_departure' in df_raw.columns:
    df_raw['port_of_departure'] = df_raw['port_of_departure'].fillna('Unknown').apply(clean_port_name)
else:
    df_raw['port_of_departure'] = 'Unknown'

name_fix_map = {
    "VIZAG": "Visakhapatnam", "VIZAG SEA": "Visakhapatnam",
    "GOA": "Mormugao (Goa)", "GOA PORT": "Mormugao (Goa)"
}
df_raw['port_of_arrival'] = df_raw['port_of_arrival'].replace(name_fix_map)
if hasattr(config, 'PORT_CODE_TO_NAME'):
    df_raw['port_of_arrival'] = df_raw['port_of_arrival'].replace(config.PORT_CODE_TO_NAME)

# 3.3 日期处理
df_raw['transaction_date'] = pd.to_datetime(df_raw['transaction_date'])
df_raw['Month'] = df_raw['transaction_date'].dt.to_period('M').astype(str)

# 3.4 树种识别
if 'Species' not in df_raw.columns:
    if 'product_desc_text' in df_raw.columns:
        df_raw['Species'] = df_raw['product_desc_text'].apply(utils.identify_species)
    else:
        df_raw['Species'] = 'Unknown'

# 3.5 国家名称映射
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

# 3.6 产品分类映射
def map_hs_to_category(hs_code):
    hs_str = str(hs_code)
    if hasattr(config, 'HS_CODES_MAP'):
        for category, codes in config.HS_CODES_MAP.items():
            for c in codes:
                if hs_str.startswith(c):
                    return category
    return "Other Products"

if 'Product_Category' not in df_raw.columns:
    df_raw['Product_Category'] = df_raw['hs_code'].apply(map_hs_to_category)

# ==========================================
# 4. 侧边栏筛选器 (Sidebar Filters)
# ==========================================
with st.sidebar:
    st.header("🔍 Cockpit Filters")

    # --- [Step 1] 全局单位清洗 ---
    st.subheader("🛠️ Data Cleaning")
    df_raw['quantity_unit'] = df_raw['quantity_unit'].fillna('Unknown')
    available_units = df_raw['quantity_unit'].unique().tolist()
    
    default_ix = 0
    for i, u in enumerate(available_units):
        if str(u).upper() in ['CBM', 'M3', 'MTQ', 'M3 ']:
            default_ix = i
            break
            
    target_unit = st.selectbox("📏 Global Unit (全局单位)", available_units, index=default_ix)
    
    with st.expander("🧹 Smart Outlier Filter", expanded=False):
        enable_price_clean = st.checkbox("Enable Filter", value=True)
        min_valid_price = st.number_input("Min Price ($/Unit)", value=5.0, step=1.0)
    
    st.divider()

    # --- [Step 2] 业务筛选 ---
    # 日期
    min_date = df_raw['transaction_date'].min().date()
    max_date = df_raw['transaction_date'].max().date()
    date_range = st.date_input("📅 Date Range", value=(min_date, max_date), min_value=min_date, max_value=max_date)
    
    # 动态获取选项
    all_products = sorted(df_raw['Product_Category'].astype(str).unique())
    all_origins = sorted(df_raw['origin_name'].astype(str).unique())
    all_species = sorted(df_raw['Species'].astype(str).unique())
    all_dests = sorted(df_raw['dest_name'].astype(str).unique())

    # 筛选器
    sel_products = st.multiselect("📦 Product (产品分类)", all_products, placeholder="All Products")
    sel_origins = st.multiselect("🛫 Origin (出口国)", all_origins, placeholder="All Origins")
    sel_species = st.multiselect("🌲 Species (树种)", all_species, placeholder="All Species")
    sel_dests = st.multiselect("🛬 Destination (进口国)", all_dests, placeholder="All Destinations")

# ==========================================
# 5. 执行筛选逻辑 (Filter Application)
# ==========================================

# 1. 应用单位筛选
df = df_raw[df_raw['quantity_unit'] == target_unit].copy()

# 2. 应用异常值筛选
if enable_price_clean:
    df['calc_price'] = df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
    df = df[df['calc_price'] >= min_valid_price]

# 3. 应用业务筛选
mask = pd.Series(True, index=df.index)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_d, end_d = date_range
    mask &= (df['transaction_date'].dt.date >= start_d) & (df['transaction_date'].dt.date <= end_d)

if sel_products: mask &= df['Product_Category'].isin(sel_products)
if sel_origins: mask &= df['origin_name'].isin(sel_origins)
if sel_species: mask &= df['Species'].isin(sel_species)
if sel_dests: mask &= df['dest_name'].isin(sel_dests)

df = df[mask].copy()

# 侧边栏统计
with st.sidebar:
    st.divider()
    st.metric("Records Found", f"{len(df):,}")
    
    total_vol = df['quantity'].sum()
    total_val = df['total_value_usd'].sum()
    avg_price_global = total_val / total_vol if total_vol > 0 else 0
    
    st.metric(f"Total Vol ({target_unit})", f"{total_vol:,.0f}")
    st.metric(f"Avg Price (USD/{target_unit})", f"${avg_price_global:,.1f}")

if df.empty:
    st.error(f"❌ No data matches your filters (Unit: {target_unit}). Try adjusting your filters.")
    st.stop()

# ==========================================
# 6. 图表渲染区域
# ==========================================

# ------------------------------------------
# Row 1: Volume Trend
# ------------------------------------------
st.subheader("1. 📈 Volume Trends (数量趋势)")

with st.container():
    c_view, _ = st.columns([4, 4]) # 稍微调宽一点左边，容纳更多按钮
    with c_view:
        view_dim = st.radio(
            "Group By (分组依据):", 
            ["Species (树种)", "Product (产品)", "Origin (出口国)", "Dest (进口国)", "Dest Port (卸货港)"],  # ✨ 新增 "Dest (进口国)"
            horizontal=True,
            key="vol_group"
        )
    
    # 更新映射字典
    dim_map = {
        "Species (树种)": "Species",
        "Product (产品)": "Product_Category",
        "Origin (出口国)": "origin_name",
        "Dest (进口国)": "dest_name",           # ✨ 新增映射
        "Dest Port (卸货港)": "port_of_arrival"
    }
    target_col = dim_map[view_dim]

    vol_data = df.groupby(['Month', target_col])['quantity'].sum().reset_index()
    months = sorted(vol_data['Month'].unique().tolist())
    group_list = sorted(vol_data[target_col].astype(str).unique().tolist())
    
    vol_series = []
    for item in group_list:
        item_data = vol_data[vol_data[target_col] == item].set_index('Month')['quantity'].reindex(months, fill_value=0).tolist()
        vol_series.append({
            "name": item,
            "type": "bar",
            "stack": "total",
            "emphasis": {"focus": "series"},
            "data": item_data,
            "animationDelay": 200
        })

    option_vol = {
        "tooltip": {"trigger": "axis", "axisPointer": {"type": "shadow"}},
        "legend": {"data": group_list, "top": "bottom", "type": "scroll"},
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
# Row 2: Price Trend
# ------------------------------------------
st.subheader("2. 💰 Price Trends (单价走势)")
st.caption(f"Calculated as: Total Value / Total Quantity (Unit: USD / {target_unit})")

with st.container():
    c_view_p, _ = st.columns([4, 4]) # 稍微调宽一点左边
    with c_view_p:
        view_dim_p = st.radio(
            "Group By (分组依据):", 
            ["Species (树种)", "Product (产品)", "Origin (出口国)", "Dest (进口国)", "Dest Port (卸货港)"], # ✨ 同样新增 "Dest (进口国)"
            horizontal=True,
            key="price_group"
        )
    target_col_p = dim_map[view_dim_p]

    price_agg = df.groupby(['Month', target_col_p])[['total_value_usd', 'quantity']].sum().reset_index()
    price_agg['avg_price'] = price_agg.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
    
    group_list_p = sorted(price_agg[target_col_p].astype(str).unique().tolist())
    price_series = []
    
    for item in group_list_p:
        item_df = price_agg[price_agg[target_col_p] == item].set_index('Month').reindex(months)
        item_price_data = [x if pd.notnull(x) else None for x in item_df['avg_price']]
        
        price_series.append({
            "name": item,
            "type": "bar",
            "emphasis": {"focus": "series"},
            "data": item_price_data,
            "markPoint": {"data": [{"type": "max", "name": "Max"}, {"type": "min", "name": "Min"}]}
        })

    option_price = {
        "tooltip": {"trigger": "axis", "valueFormatter": "(value) => '$' + Number(value).toFixed(1)"},
        "legend": {"data": group_list_p, "top": "bottom", "type": "scroll"},
        "grid": {"left": "3%", "right": "4%", "bottom": "15%", "containLabel": True},
        "toolbox": {"feature": {"magicType": {"type": ["line", "bar"]}, "saveAsImage": {}}},
        "dataZoom": [{"type": "slider", "xAxisIndex": 0, "start": 0, "end": 100}, {"type": "inside"}],
        "xAxis": {"type": "category", "data": months},
        "yAxis": {"type": "value", "name": "USD/Unit", "scale": True},
        "series": price_series
    }
    st_echarts(options=option_price, height="400px", key="echart_price")

st.divider()

# ------------------------------------------
# 下面的 Row 3, 4, 5 (Sankey, Sunburst, GeoMap) 保持不变
# ...
# ------------------------------------------
# Row 3: Sankey Flow
# ------------------------------------------
st.subheader("3. 🌊 Trade Flow: Origin ➡ Species ➡ Dest")

sankey_df = df.copy()
sankey_df['origin_name'] = sankey_df['origin_name'].fillna("Unknown").astype(str)
sankey_df['dest_name'] = sankey_df['dest_name'].fillna("Unknown").astype(str)
sankey_df['Species'] = sankey_df['Species'].fillna("Unknown").astype(str)

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
# Row 4: Sunburst
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
    st.markdown(f"- **Unit:** {target_unit}")
    if sel_products: st.markdown(f"- **Product:** {', '.join(sel_products)}")
    else: st.markdown("- **Product:** All")
    if sel_origins: st.markdown(f"- **Origin:** {', '.join(sel_origins)}")
    else: st.markdown("- **Origin:** All")

st.divider()

# ------------------------------------------
# Row 5: GeoMap (Effect Scatter) - [新增 🆕]
# ------------------------------------------
import plotly.express as px  # 确保头部引入了 plotly.express

# ... (保留上面的所有代码) ...

st.divider()
# ... (保留上面的代码) ...

st.divider()

# ------------------------------------------
# Row 5: Global Port Distribution (全球港口分布) - [已升级: 全宽显示 + 详情折叠]
# ------------------------------------------
st.subheader("5. 🌏 Global Port Distribution (全球港口分布)")

# 1. 准备聚合数据
map_df = df.groupby('port_of_arrival')[['quantity', 'total_value_usd']].sum().reset_index()

# 2. 获取坐标
def get_coords(port_name):
    if not port_name: return None, None
    p_upper = str(port_name).upper().strip()
    
    # 尝试直接匹配
    if hasattr(config, 'PORT_COORDINATES'):
        if p_upper in config.PORT_COORDINATES:
            return config.PORT_COORDINATES[p_upper]['lat'], config.PORT_COORDINATES[p_upper]['lon']
        
        # 尝试模糊匹配
        for key in config.PORT_COORDINATES:
            if key in p_upper and len(key) > 3:
                return config.PORT_COORDINATES[key]['lat'], config.PORT_COORDINATES[key]['lon']
    return None, None

# 应用坐标
map_df['lat'], map_df['lon'] = zip(*map_df['port_of_arrival'].map(get_coords))

# 3. 过滤掉没有坐标的港口
plot_map_df = map_df.dropna(subset=['lat', 'lon'])
missing_ports = map_df[map_df['lat'].isna()]['port_of_arrival'].unique().tolist()

# 4. 渲染地图 (取消 st.columns 分栏，直接显示)
if not plot_map_df.empty:
    # 使用 Plotly 绘制 3D 地球
    fig_map = px.scatter_geo(
        plot_map_df,
        lat='lat',
        lon='lon',
        size='quantity',             
        hover_name='port_of_arrival',
        hover_data={'quantity': True, 'total_value_usd': True, 'lat': False, 'lon': False},
        projection="orthographic",   # 3D 地球
        title=f"Global Arrival Ports ({target_unit})",
        template="plotly_dark"       
    )
    
    # 调整视觉样式：增加高度，减少边距，让球体更大
    fig_map.update_geos(
        showcountries=True, countrycolor="#444",
        showcoastlines=True, coastlinecolor="#444",
        showland=True, landcolor="#1e1e1e",
        showocean=True, oceancolor="#0e1117", 
        showlakes=False,
        projection_scale=1.1 # 🟢 放大一点地球的显示比例
    )
    fig_map.update_traces(marker=dict(color="#00f2ff", line=dict(width=0), opacity=0.8)) 
    fig_map.update_layout(
        margin={"r":0,"t":30,"l":0,"b":0}, # 🟢 极简边距
        height=600,                        # 🟢 增加高度 (从500 -> 600)
        paper_bgcolor="rgba(0,0,0,0)", 
    )
    
    # 全宽显示
    st.plotly_chart(fig_map, use_container_width=True)

    # 5. 将列表移入折叠面板
    with st.expander("📍 View Port Statistics (查看港口详情数据)"):
        c_tbl, c_miss = st.columns([2, 1])
        with c_tbl:
            st.markdown("**Top Ports by Volume:**")
            st.dataframe(
                plot_map_df.sort_values('quantity', ascending=False).head(20)[['port_of_arrival', 'quantity', 'total_value_usd']],
                use_container_width=True,
                hide_index=True
            )
        with c_miss:
            if missing_ports:
                st.markdown("**⚠️ Unmapped Ports (无坐标):**")
                st.write(missing_ports)
else:
    st.warning("⚠️ No coordinate data matched for current filtered ports.")