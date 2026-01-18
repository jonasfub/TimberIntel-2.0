import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import config
import utils  # 引用 utils.py

st.set_page_config(page_title="Timber Intel Core", page_icon="🌲", layout="wide")

st.title("🌲 Timber Intel - 情报分析看板")

# --- 0. 状态管理 (防止页面刷新后数据丢失) ---
if 'report_active' not in st.session_state:
    st.session_state['report_active'] = False
if 'analysis_df' not in st.session_state:
    st.session_state['analysis_df'] = pd.DataFrame()

# ==========================================
# 侧边栏设置
# ==========================================
with st.sidebar:
    st.header("📊 分析设置")
    
    if 'access_token' in st.session_state:
        st.success("✅ API Token 有效")
    else:
        st.info("API 未激活 (进入下载页自动激活)")
        
    st.divider()
    
    selected_category = st.selectbox("产品分类", list(config.HS_CODES_MAP.keys()))
    target_hs_codes = config.HS_CODES_MAP[selected_category]
    date_range = st.date_input("日期范围", value=(datetime.today() - timedelta(days=365), datetime.today()))

# ==========================================
# 主界面筛选
# ==========================================
st.markdown("### 🔍 筛选条件")
c1, c2 = st.columns(2)
with c1: 
    st.caption("快捷选择 (Origin):")
    utils.render_region_buttons("ana_origin", c1)
    ana_origins = st.multiselect("出口国 (Origin)", utils.get_all_country_codes(), format_func=utils.country_format_func, key="ana_origin")
with c2: 
    st.caption("快捷选择 (Dest):")
    utils.render_region_buttons("ana_dest", c2)
    ana_dests = st.multiselect("进口国 (Dest)", utils.get_all_country_codes(), format_func=utils.country_format_func, key="ana_dest")

c3, c4 = st.columns(2)
with c3:
    ana_hs_selected = st.multiselect("HS Codes (留空全选)", target_hs_codes, key="ana_hs")
    final_ana_hs_codes = ana_hs_selected if ana_hs_selected else target_hs_codes
with c4:
    species_options = list(config.SPECIES_KEYWORDS.keys()) + ["Other", "Unknown"]
    ana_species_selected = st.multiselect("树种 (Species) (留空全选)", species_options, key="ana_species")

st.divider()

# ==========================================
# 数据提取逻辑
# ==========================================
start_d, end_d = None, None
if isinstance(date_range, tuple):
    if len(date_range) == 2:
        start_d, end_d = date_range
    elif len(date_range) == 1:
        start_d = date_range[0]
        end_d = date_range[0]

if start_d and end_d:
    st.info(f"📅 当前分析范围: **{start_d}** 至 **{end_d}**")

    # 点击按钮 -> 触发数据加载并存入 Session State
    if st.button("📊 加载分析报告 (Load Analysis Report)", type="primary"):
        all_rows = []
        batch_size = 50000 
        page = 0
        max_pages = 20 
        
        with st.status("正在从数据库提取全量数据...", expanded=True) as status:
            try:
                while page < max_pages:
                    range_start = page * batch_size
                    range_end = range_start + batch_size - 1
                    status.write(f"正在提取第 {page+1} 批数据 (Offset {range_start})...")
                    
                    response = utils.supabase.table('trade_records').select("*")\
                        .gte('transaction_date', start_d).lte('transaction_date', end_d)\
                        .order("transaction_date", desc=True)\
                        .range(range_start, range_end).execute()
                    
                    rows = response.data
                    if not rows: break
                    all_rows.extend(rows)
                    if len(rows) < batch_size: break
                    page += 1
                
                status.update(label=f"提取完成: 共 {len(all_rows)} 条记录", state="complete")
                
                # 存入 Session State
                if all_rows:
                    st.session_state['analysis_df'] = pd.DataFrame(all_rows)
                    st.session_state['report_active'] = True
                else:
                    st.session_state['report_active'] = False
                    st.warning("数据库中无该时间段数据")
                
            except Exception as e: 
                status.update(label="提取出错", state="error")
                st.error(f"Error: {str(e)}")

# ==========================================
# 报告渲染逻辑 (基于 Session State)
# ==========================================
if st.session_state.get('report_active', False) and not st.session_state['analysis_df'].empty:
    df = st.session_state['analysis_df']
    
    # --- 数据清洗与名称映射 ---
    # 1. 基础处理
    min_date = df['transaction_date'].min()
    max_date = df['transaction_date'].max()
    st.caption(f"🔎 覆盖检查: 数据库返回的最早日期是 `{min_date}`，最晚日期是 `{max_date}`")
    
    # 2. 本地筛选
    df['match_hs'] = df['hs_code'].astype(str).apply(lambda x: any(x.startswith(t) for t in final_ana_hs_codes))
    df = df[df['match_hs']]
    
    # 识别树种
    df['Species'] = df['product_desc_text'].apply(utils.identify_species)

    # ========================================================
    # 🔥 自动清洗脏数据 (Smart Cleaning Logic)
    # ========================================================
    current_category_type = None
    if "Softwood" in selected_category:
        current_category_type = "Softwood"
    elif "Hardwood" in selected_category:
        current_category_type = "Hardwood"
    
    if current_category_type:
        forbidden_type = "Hardwood" if current_category_type == "Softwood" else "Softwood"
        forbidden_species = getattr(config, 'SPECIES_CATEGORY_MAP', {}).get(forbidden_type, [])
        
        if forbidden_species:
            dirty_rows = df[df['Species'].isin(forbidden_species)]
            if not dirty_rows.empty:
                dirty_count = len(dirty_rows)
                dirty_list = dirty_rows['Species'].unique()
                st.warning(f"🧹 智能清洗: 自动隐藏了 {dirty_count} 条分类错误的记录 (识别为: {', '.join(dirty_list)})。原因：HS编码属于 {current_category_type}，但产品描述为 {forbidden_type}。")
                df = df[~df['Species'].isin(forbidden_species)]
    # ========================================================
    
    # 继续原有的筛选
    if ana_species_selected: df = df[df['Species'].isin(ana_species_selected)]
    if ana_origins: df = df[df['origin_country_code'].isin(ana_origins)]
    if ana_dests: df = df[df['dest_country_code'].isin(ana_dests)]

    if df.empty:
        st.warning("本地筛选后无数据")
    else:
        # 3. 计算指标
        df['unit_price'] = df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 and pd.notnull(x['total_value_usd']) else 0, axis=1)
        
        # 4. 映射国家全名 (纯英文)
        def get_country_name_en(code):
            full_name = config.COUNTRY_NAME_MAP.get(code, code)
            if '(' in full_name: return full_name.split(' (')[0]
            return full_name

        df['origin_name'] = df['origin_country_code'].apply(get_country_name_en)
        df['dest_name'] = df['dest_country_code'].apply(get_country_name_en)
        
        # 5. 月份排序准备
        df['Month'] = pd.to_datetime(df['transaction_date']).dt.to_period('M').astype(str)
        sorted_months = sorted(df['Month'].unique())

        # --- KPI ---
        k1, k2, k3 = st.columns(3)
        k1.metric("记录数 (Count)", len(df))
        k2.metric("总数量 (Total Qty)", f"{df['quantity'].sum():,.0f}")
        total_val = df['total_value_usd'].sum()
        k3.metric("总金额 (Total Value)", f"${total_val:,.0f}")
        
        st.divider()

        # ============================================
        # 1. 数量趋势 (Quantity Trends)
        # ============================================
        st.subheader("📈 数量趋势 (Volume Trends)")
        r1_c1, r1_c2 = st.columns(2)
        
        with r1_c1:
            chart_species = df.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
            fig_sp = px.bar(
                chart_species, x="Month", y="quantity", color="Species", 
                title="月度数量趋势 - 按树种 (Qty by Species)",
                category_orders={"Month": sorted_months}
            )
            fig_sp.update_xaxes(type='category')
            st.plotly_chart(fig_sp, use_container_width=True)

        with r1_c2:
            chart_origin = df.groupby(['Month', 'origin_name'])['quantity'].sum().reset_index()
            fig_org = px.bar(
                chart_origin, x="Month", y="quantity", color="origin_name",
                title="月度数量趋势 - 按出口国 (Qty by Origin)",
                category_orders={"Month": sorted_months}
            )
            fig_org.update_xaxes(type='category')
            st.plotly_chart(fig_org, use_container_width=True)

        st.divider()
        
        # ============================================
        # 2. 金额趋势与结构 (USD)
        # ============================================
        st.subheader("💰 金额趋势与结构 (Value Trends & Structure)")
        r2_c1, r2_c2 = st.columns(2)

        with r2_c1:
            chart_val_origin = df.groupby(['Month', 'origin_name'])['total_value_usd'].sum().reset_index()
            fig_val_org = px.bar(
                chart_val_origin, x="Month", y="total_value_usd", color="origin_name",
                title="月度金额趋势 - 按出口国 (Total Value by Origin - USD)",
                category_orders={"Month": sorted_months}
            )
            fig_val_org.update_xaxes(type='category')
            fig_val_org.update_layout(yaxis_title="Total Value (USD)")
            st.plotly_chart(fig_val_org, use_container_width=True)

        with r2_c2:
            if ana_origins and not ana_dests:
                g_col = 'dest_name'
                title_pie = "进口国数量占比 (Dest Share)"
            else:
                g_col = 'origin_name'
                title_pie = "出口国数量占比 (Origin Share)"
            st.plotly_chart(px.pie(df, names=g_col, values='quantity', hole=0.4, title=title_pie), use_container_width=True)

        st.divider()

        # ============================================
        # 3. 价格分析 (Price Analysis - USD)
        # ============================================
        st.subheader("🏷️ 价格分析 (Price Analysis)")
        
        # [Unit Filter]
        df['quantity_unit'] = df['quantity_unit'].fillna('Unknown')
        available_units = df['quantity_unit'].unique().tolist()
        
        default_idx = 0
        for i, u in enumerate(available_units):
            if str(u).upper() in ['MTQ', 'CBM', 'M3']:
                default_idx = i
                break
        
        st.markdown("⚠️ **Note:** Price analysis only applies to the selected unit to avoid mixing KG/M3.")
        price_unit_filter = st.selectbox(
            "Select Unit for Price Calculation:", 
            available_units, 
            index=default_idx
        )
        
        df_price_calc = df[df['quantity_unit'] == price_unit_filter].copy()
        
        if not df_price_calc.empty:
            r3_c1, r3_c2 = st.columns(2)

            with r3_c1:
                price_org_df = df_price_calc.groupby('origin_name')[['total_value_usd', 'quantity']].sum().reset_index()
                price_org_df['avg_price'] = price_org_df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
                price_org_df = price_org_df.sort_values('avg_price', ascending=False)
                
                fig_price_org = px.bar(
                    price_org_df, x="origin_name", y="avg_price",
                    title=f"各出口国加权均价 (Avg Price - {price_unit_filter})", 
                    color="avg_price", color_continuous_scale="Blues", text_auto='.0f'
                )
                fig_price_org.update_layout(xaxis_title="Origin", yaxis_title=f"Avg Price (USD/{price_unit_filter})")
                st.plotly_chart(fig_price_org, use_container_width=True)

            with r3_c2:
                price_sp_df = df_price_calc.groupby('Species')[['total_value_usd', 'quantity']].sum().reset_index()
                price_sp_df['avg_price'] = price_sp_df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
                price_sp_df = price_sp_df.sort_values('avg_price', ascending=False)
                
                fig_price_sp = px.bar(
                    price_sp_df, x="Species", y="avg_price",
                    title=f"各树种加权均价 (Avg Price - {price_unit_filter})",
                    color="avg_price", color_continuous_scale="Greens", text_auto='.0f'
                )
                fig_price_sp.update_layout(xaxis_title="Species", yaxis_title=f"Avg Price (USD/{price_unit_filter})")
                st.plotly_chart(fig_price_sp, use_container_width=True)
        else:
            st.warning(f"No records found for unit: {price_unit_filter}")

        st.divider()

        # ============================================
        # 4. 港口分析 (Port Analysis)
        # ============================================
        st.subheader("⚓ 港口分析 (Port Analysis)")
        
        df['port_of_arrival'] = df['port_of_arrival'].fillna('Unknown').replace('', 'Unknown')

        # --- Top 10 ---
        st.markdown("##### 🏆 Top 10 港口排名 (Top 10 Ports)")
        t1, t2 = st.columns(2)
        with t1:
            top_val_ports = df.groupby('port_of_arrival')['total_value_usd'].sum().nlargest(10).index.tolist()
            chart_port_val = df[df['port_of_arrival'].isin(top_val_ports)].groupby(['port_of_arrival', 'Species'])['total_value_usd'].sum().reset_index()
            fig_pv = px.bar(
                chart_port_val, x="port_of_arrival", y="total_value_usd", color="Species", 
                title="Top 10 by Value (USD)", 
                category_orders={"port_of_arrival": top_val_ports}
            )
            fig_pv.update_layout(yaxis_title="Total Value (USD)")
            st.plotly_chart(fig_pv, use_container_width=True)
        with t2:
            top_qty_ports = df.groupby('port_of_arrival')['quantity'].sum().nlargest(10).index.tolist()
            chart_port_qty = df[df['port_of_arrival'].isin(top_qty_ports)].groupby(['port_of_arrival', 'Species'])['quantity'].sum().reset_index()
            fig_pq = px.bar(
                chart_port_qty, x="port_of_arrival", y="quantity", color="Species", 
                title="Top 10 by Volume", 
                category_orders={"port_of_arrival": top_qty_ports}
            )
            st.plotly_chart(fig_pq, use_container_width=True)

        st.divider()

        # --- Map & Inspector ---
        st.markdown("##### 🌏 港口透视 (Port Inspector & Map)")
        
        map_df = df.groupby('port_of_arrival')[['quantity', 'total_value_usd']].sum().reset_index()
        port_species_df = df.groupby(['port_of_arrival', 'Species'])['quantity'].sum().reset_index()
        dom_sp_df = port_species_df.sort_values('quantity', ascending=False).drop_duplicates('port_of_arrival')
        dom_sp_df = dom_sp_df[['port_of_arrival', 'Species']].rename(columns={'Species': 'dominant_species'})
        map_df = map_df.merge(dom_sp_df, on='port_of_arrival', how='left')

        # 坐标匹配
        def get_coords(port_name):
            if not port_name: return None, None
            p_upper = port_name.upper().strip()
            if p_upper in config.PORT_COORDINATES:
                return config.PORT_COORDINATES[p_upper]['lat'], config.PORT_COORDINATES[p_upper]['lon']
            for key in config.PORT_COORDINATES:
                if key in p_upper and len(key) > 3:
                     return config.PORT_COORDINATES[key]['lat'], config.PORT_COORDINATES[key]['lon']
            return None, None

        map_df['lat'], map_df['lon'] = zip(*map_df['port_of_arrival'].map(get_coords))
        plot_map_df = map_df.dropna(subset=['lat', 'lon'])

        col_map, col_inspector = st.columns([2, 1])

        with col_map:
            if not plot_map_df.empty:
                fig_map = px.scatter_geo(
                    plot_map_df,
                    lat='lat', lon='lon',
                    size='quantity', 
                    color='dominant_species',
                    hover_name='port_of_arrival',
                    projection="natural earth",
                    size_max=40,
                    title="全球港口分布 (Global View)",
                    color_continuous_scale="Viridis"
                )
                fig_map.update_geos(showcountries=True, countrycolor="#e5e5e5", showcoastlines=True)
                fig_map.update_layout(height=500, margin={"r":0,"t":30,"l":0,"b":0}, legend=dict(orientation="h", y=-0.1))
                st.plotly_chart(fig_map, use_container_width=True)
            else:
                st.warning("暂无匹配坐标的港口数据")

        with col_inspector:
            st.markdown("##### 🔬 港口详情 (Detail)")
            sorted_ports = map_df.sort_values('quantity', ascending=False)['port_of_arrival'].tolist()
            if sorted_ports:
                selected_port = st.selectbox("选择港口 (Select Port)", sorted_ports, key="port_inspector_select")
                
                port_df = df[df['port_of_arrival'] == selected_port]
                p_qty = port_df['quantity'].sum()
                p_val = port_df['total_value_usd'].sum()
                c1p, c2p = st.columns(2)
                c1p.metric("Volume", f"{p_qty:,.0f}")
                c2p.metric("Value (USD)", f"${p_val:,.0f}")
                
                # 材种饼图
                st.markdown(f"**{selected_port} - 材种分布**")
                port_sp_pie = port_df.groupby('Species')['quantity'].sum().reset_index()
                fig_pie = px.pie(port_sp_pie, names='Species', values='quantity', hole=0.3)
                fig_pie.update_layout(height=250, margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False)
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("无港口数据")

        st.divider()
        
        # 详情表
        st.subheader("📋 详细数据 (Details)")
        # [NEW] 加上 unit_price
        cols = ['transaction_date', 'hs_code', 'Species', 'origin_name', 'dest_name', 'port_of_arrival', 'quantity', 'quantity_unit', 'total_value_usd', 'unit_price', 'exporter_name']
        final_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[final_cols], use_container_width=True)

elif start_d and end_d:
    st.info("👈 请点击“加载分析报告”按钮开始分析")
else:
    st.info("请选择日期范围")