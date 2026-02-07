import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, date
import config
import utils  # 引用 utils.py

# --- 页面基础设置 ---
st.set_page_config(page_title="Timber Intel Core", page_icon="🌲", layout="wide")

st.title("🌲 Timber Intel - Analysis Dashboard (情报分析看板)")

# --- 0. 状态管理 (防止页面刷新后数据丢失) ---
if 'report_active' not in st.session_state:
    st.session_state['report_active'] = False
if 'analysis_df' not in st.session_state:
    st.session_state['analysis_df'] = pd.DataFrame()

# ==========================================
# 侧边栏设置 (Sidebar Settings)
# ==========================================
with st.sidebar:
    st.header("📊 Analysis Settings (分析设置)")
    
    # API Token 检查
    if utils.get_auto_token():
        st.success("✅ API Token Valid (API 有效)")
    else:
        st.info("⚠️ API Inactive (Token 失效 - 将尝试自动刷新)")
        
    st.divider()
    
    # 1. 产品分类
    selected_category = st.selectbox(
        "Product Category (产品分类)", 
        list(config.HS_CODES_MAP.keys())
    )
    target_hs_codes = config.HS_CODES_MAP[selected_category]
    
    st.divider()

    # 2. 日期范围逻辑 (Date Range Logic)
    st.markdown("📅 **Time Period (时间范围)**")

    # --- 核心日期计算逻辑 ---
    def set_date_range(range_type):
        today = datetime.now().date()
        
        if range_type == 'last_month':
            # 逻辑：本月1号 - 1天 = 上月最后一天
            first_of_this_month = today.replace(day=1)
            end_date = first_of_this_month - timedelta(days=1)
            start_date = end_date.replace(day=1)
            st.session_state['global_date_range'] = (start_date, end_date)
            
        elif range_type == 'last_quarter':
            # 逻辑：
            # 1. 计算当前季度的起始月份 (1, 4, 7, 10)
            # 2. 当前季度1号 - 1天 = 上季度最后一天
            # 3. 上季度最后一天向前推2个月的1号 = 上季度第一天
            current_month = today.month
            curr_q_start_month = 3 * ((current_month - 1) // 3) + 1
            curr_q_start_date = date(today.year, curr_q_start_month, 1)
            
            end_date = curr_q_start_date - timedelta(days=1)
            start_date = date(end_date.year, end_date.month - 2, 1)
            st.session_state['global_date_range'] = (start_date, end_date)
            
        elif range_type == 'last_year':
            # 逻辑：去年的1月1日 到 12月31日
            last_year_val = today.year - 1
            st.session_state['global_date_range'] = (date(last_year_val, 1, 1), date(last_year_val, 12, 31))

    # --- 快捷按钮布局 (3列) ---
    c_d1, c_d2, c_d3 = st.columns(3)
    
    with c_d1: 
        st.button(
            "Last Month\n(上月)", 
            help="Previous Calendar Month (上一个完整自然月)", 
            on_click=set_date_range, args=('last_month',), 
            use_container_width=True
        )
    with c_d2: 
        st.button(
            "Last Q\n(上季)", 
            help="Previous Calendar Quarter (上一个完整自然季度)", 
            on_click=set_date_range, args=('last_quarter',), 
            use_container_width=True
        )
    with c_d3: 
        st.button(
            "Last Year\n(去年)", 
            help="Previous Calendar Year (上一个完整自然年)", 
            on_click=set_date_range, args=('last_year',), 
            use_container_width=True
        )

    # --- 初始化默认值 ---
    today = datetime.now().date()
    if 'global_date_range' not in st.session_state:
        # 默认初始化为: 上一个月 (通常比去年更常用)
        first_of_this_month = today.replace(day=1)
        end_date = first_of_this_month - timedelta(days=1)
        start_date = end_date.replace(day=1)
        st.session_state['global_date_range'] = (start_date, end_date)

    # --- 日期选择器 ---
    # 关键：不要设置 value，只设置 key，让 key 绑定 Session State
    date_range = st.date_input(
        "Custom Range (自定义范围)", 
        max_value=today,
        format="YYYY-MM-DD",
        key="global_date_range" 
    )

# ==========================================
# 主界面筛选 (Main Filters)
# ==========================================
st.markdown("### 🔍 Filters (筛选条件)")
c1, c2 = st.columns(2)
with c1: 
    st.caption("Quick Select - Origin (快捷选择 - 出口国):")
    utils.render_region_buttons("ana_origin", c1)
    ana_origins = st.multiselect(
        "Origin Country (出口国)", 
        utils.get_all_country_codes(), 
        format_func=utils.country_format_func, 
        key="ana_origin"
    )
with c2: 
    st.caption("Quick Select - Dest (快捷选择 - 进口国):")
    utils.render_region_buttons("ana_dest", c2)
    ana_dests = st.multiselect(
        "Destination Country (进口国)", 
        utils.get_all_country_codes(), 
        format_func=utils.country_format_func, 
        key="ana_dest"
    )

c3, c4 = st.columns(2)
with c3:
    ana_hs_selected = st.multiselect("HS Codes (Leave empty for All/留空全选)", target_hs_codes, key="ana_hs")
    final_ana_hs_codes = ana_hs_selected if ana_hs_selected else target_hs_codes
with c4:
    species_options = list(config.SPECIES_KEYWORDS.keys()) + ["Other", "Unknown"]
    ana_species_selected = st.multiselect("Species (树种) (Leave empty for All/留空全选)", species_options, key="ana_species")

st.divider()

# ==========================================
# 数据提取逻辑 (Data Extraction Logic)
# ==========================================
start_d, end_d = None, None
is_date_valid = False

if isinstance(date_range, tuple):
    if len(date_range) == 2:
        start_d, end_d = date_range
        is_date_valid = True
    elif len(date_range) == 1:
        # 用户只选了开始时间，还没选结束时间
        st.warning("⚠️ Please select an End Date to proceed (请选择结束日期).")

if is_date_valid and start_d and end_d:
    st.info(f"📅 Current Analysis Period (当前分析范围): **{start_d}** to **{end_d}**")

    # 点击按钮 -> 触发数据加载并存入 Session State
    if st.button("📊 Load Analysis Report (加载分析报告)", type="primary", use_container_width=True):
        # --- 核心配置 ---
        all_rows = []
        batch_size = 5000       # 单次请求最大行数
        chunk_days = 7          # 每次只取 7 天的数据
        
        # 仅查询需要的列
        needed_columns = "transaction_date,hs_code,product_desc_text,origin_country_code,dest_country_code,quantity,quantity_unit,total_value_usd,port_of_arrival,exporter_name,importer_name,unique_record_id"
        
        with st.status("🚀 Starting Data Extraction (正在启动分片提取)...", expanded=True) as status:
            msg_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            try:
                # 转换 date 对象为 datetime 对象以进行加减运算
                current_start_dt = datetime.combine(start_d, datetime.min.time())
                end_dt = datetime.combine(end_d, datetime.min.time())

                # 1. 计算总天数
                total_days = (end_dt - current_start_dt).days
                if total_days <= 0: total_days = 1
                
                # 2. 初始化循环变量
                current_chunk_start = current_start_dt
                
                while current_chunk_start <= end_dt:
                    # 计算当前切片的结束日期
                    current_chunk_end = min(current_chunk_start + timedelta(days=chunk_days), end_dt)
                    
                    # 更新进度
                    days_done = (current_chunk_start - current_start_dt).days
                    progress = min(days_done / total_days, 0.99)
                    progress_bar.progress(progress)
                    msg_placeholder.info(f"📅 Fetching: {current_chunk_start.date()} to {current_chunk_end.date()} ... (Records: {len(all_rows)})")
                    
                    # 3. 切片内部提取
                    chunk_offset = 0
                    while True:
                        query = utils.supabase.table('trade_records')\
                            .select(needed_columns)\
                            .gte('transaction_date', current_chunk_start.date())\
                            .lte('transaction_date', current_chunk_end.date())
                        
                        if ana_origins: query = query.in_('origin_country_code', ana_origins)
                        if ana_dests: query = query.in_('dest_country_code', ana_dests)
                        
                        response = query.range(chunk_offset, chunk_offset + batch_size - 1).execute()
                        rows = response.data
                        
                        if not rows:
                            break
                        
                        all_rows.extend(rows)
                        chunk_offset += len(rows)
                        
                        if len(rows) < batch_size:
                            break
                    
                    # 4. 移动到下一个时间切片
                    current_chunk_start = current_chunk_end + timedelta(days=1)
                
                # 完成
                progress_bar.progress(1.0)
                msg_placeholder.empty()
                status.update(label=f"✅ Extraction Complete: {len(all_rows)} records (提取完成)", state="complete")
                
                if all_rows:
                    # 转 DataFrame 并按日期排序
                    df = pd.DataFrame(all_rows)
                    df = df.sort_values(by='transaction_date', ascending=False)
                    
                    st.session_state['analysis_df'] = df
                    st.session_state['report_active'] = True
                else:
                    st.session_state['report_active'] = False
                    st.warning("No data found for this period (该时间段无数据)")
                    
            except Exception as e: 
                status.update(label="Extraction Error (提取出错)", state="error")
                st.error(f"Error detail: {str(e)}")

# ==========================================
# 报告渲染逻辑 (Report Rendering)
# ==========================================
if st.session_state.get('report_active', False) and not st.session_state['analysis_df'].empty:
    df = st.session_state['analysis_df']

    # --- 数据清洗 ---
    df['port_of_arrival'] = df['port_of_arrival'].fillna('Unknown').astype(str).apply(
        lambda x: x.split('(')[-1].replace(')', '').strip() if '(' in x else x.strip()
    )
    name_fix_map = {
        "VIZAG": "Visakhapatnam", "VIZAG SEA": "Visakhapatnam",
        "GOA": "Mormugao (Goa)", "GOA PORT": "Mormugao (Goa)"
    }
    df['port_of_arrival'] = df['port_of_arrival'].replace(name_fix_map)
    if hasattr(config, 'PORT_CODE_TO_NAME'):
        df['port_of_arrival'] = df['port_of_arrival'].replace(config.PORT_CODE_TO_NAME)
    
    # --- 基础处理 ---
    min_date = df['transaction_date'].min()
    max_date = df['transaction_date'].max()
    
    df['match_hs'] = df['hs_code'].astype(str).apply(lambda x: any(x.startswith(t) for t in final_ana_hs_codes))
    df = df[df['match_hs']]
    
    if 'product_desc_text' in df.columns:
        df['Species'] = df['product_desc_text'].apply(utils.identify_species)
    else:
        df['Species'] = 'Unknown'

    # --- 智能树种清洗 ---
    current_category_type = None
    if "Softwood" in selected_category: current_category_type = "Softwood"
    elif "Hardwood" in selected_category: current_category_type = "Hardwood"
    
    if current_category_type:
        forbidden_type = "Hardwood" if current_category_type == "Softwood" else "Softwood"
        forbidden_species = getattr(config, 'SPECIES_CATEGORY_MAP', {}).get(forbidden_type, [])
        if forbidden_species:
            df = df[~df['Species'].isin(forbidden_species)]
    
    # --- 本地筛选 ---
    if ana_species_selected: df = df[df['Species'].isin(ana_species_selected)]
    if ana_origins: df = df[df['origin_country_code'].isin(ana_origins)]
    if ana_dests: df = df[df['dest_country_code'].isin(ana_dests)]

    if df.empty:
        st.warning("No data after local filtering (本地筛选后无数据)")
    else:
        # 3. 计算指标
        df['unit_price'] = df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 and pd.notnull(x['total_value_usd']) else 0, axis=1)
        
        # 安全的国家名称转换函数
        def get_country_name_en(code):
            if pd.isna(code) or code == "" or code is None:
                return "Unknown"
            full_name = config.COUNTRY_NAME_MAP.get(code, code)
            full_name_str = str(full_name)
            if '(' in full_name_str: 
                return full_name_str.split(' (')[0]
            return full_name_str

        df['origin_name'] = df['origin_country_code'].apply(get_country_name_en)
        df['dest_name'] = df['dest_country_code'].apply(get_country_name_en)
        df['Month'] = pd.to_datetime(df['transaction_date']).dt.to_period('M').astype(str)
        sorted_months = sorted(df['Month'].unique())

        # ========================================================
        # Global Unit Filter (全局单位清洗)
        # ========================================================
        
        df['quantity_unit'] = df['quantity_unit'].fillna('Unknown')
        vol_units = df['quantity_unit'].unique().tolist()
        
        default_unit_idx = 0
        for i, u in enumerate(vol_units):
            if str(u).upper() in ['MTQ', 'CBM', 'M3', 'M3 ']:
                default_unit_idx = i
                break
        
        c_unit_sel, _ = st.columns([1, 3])
        with c_unit_sel:
            target_unit = st.selectbox(
                "🔢 Global Unit Filter (全局单位清洗):", 
                vol_units, 
                index=default_unit_idx
            )
            
        df_clean_qty = df[df['quantity_unit'] == target_unit].copy()
        
        # Smart Price Filter (智能价格清洗)
        with st.expander("🧹 Smart Outlier Filter (异常值智能清洗)", expanded=True):
            c_cl1, c_cl2 = st.columns([3, 1])
            with c_cl1:
                st.info("💡 Enable this to auto-remove records with extremely low unit price (KG mislabeled as M3). / 开启此功能可自动剔除单价极低的数据。")
            with c_cl2:
                enable_price_clean = st.checkbox("Enable (启用)", value=True)
                
            if enable_price_clean:
                min_valid_price = st.number_input("Min Valid Price ($/Unit) / 最低有效单价", value=5.0, step=1.0)
                
                df_clean_qty['calc_price'] = df_clean_qty.apply(
                    lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1
                )
                
                count_before = len(df_clean_qty)
                df_clean_qty = df_clean_qty[df_clean_qty['calc_price'] >= min_valid_price]
                count_after = len(df_clean_qty)
                
                if count_before > count_after:
                    st.warning(f"🧹 Removed {count_before - count_after} outlier records (Price < ${min_valid_price})")

        # --- KPI ---
        k1, k2, k3 = st.columns(3)
        k1.metric("Record Count (记录数)", len(df))
        
        clean_qty_sum = df_clean_qty['quantity'].sum()
        k2.metric(f"Total Volume ({target_unit})", f"{clean_qty_sum:,.0f}")
        
        total_val = df['total_value_usd'].sum()
        k3.metric("Total Value (USD)", f"${total_val:,.0f}")
        
        st.divider()

        # ============================================
        # 1. 数量趋势 (Volume Trends)
        # ============================================
        st.subheader("📈 Volume Trends (数量趋势)")
        
        if not df_clean_qty.empty:
            r1_c1, r1_c2 = st.columns(2)
            
            with r1_c1:
                chart_species = df_clean_qty.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
                fig_sp = px.bar(
                    chart_species, x="Month", y="quantity", color="Species", 
                    title=f"Monthly Volume by Species - {target_unit} (月度数量 - 按树种)",
                    category_orders={"Month": sorted_months}
                )
                fig_sp.update_xaxes(type='category')
                st.plotly_chart(fig_sp, use_container_width=True)

            with r1_c2:
                chart_origin = df_clean_qty.groupby(['Month', 'origin_name'])['quantity'].sum().reset_index()
                fig_org = px.bar(
                    chart_origin, x="Month", y="quantity", color="origin_name",
                    title=f"Monthly Volume by Origin - {target_unit} (月度数量 - 按出口国)",
                    category_orders={"Month": sorted_months}
                )
                fig_org.update_xaxes(type='category')
                st.plotly_chart(fig_org, use_container_width=True)
        else:
            st.warning(f"No valid data for unit: {target_unit}")

        st.divider()
        
        # ============================================
        # 2. 金额趋势 (Value Trends)
        # ============================================
        st.subheader("💰 Value Trends & Structure (金额趋势与结构)")
        r2_c1, r2_c2 = st.columns(2)

        with r2_c1:
            chart_val_origin = df.groupby(['Month', 'origin_name'])['total_value_usd'].sum().reset_index()
            fig_val_org = px.bar(
                chart_val_origin, x="Month", y="total_value_usd", color="origin_name",
                title="Monthly Value by Origin - USD (月度金额 - 按出口国)",
                category_orders={"Month": sorted_months}
            )
            fig_val_org.update_xaxes(type='category')
            st.plotly_chart(fig_val_org, use_container_width=True)

        with r2_c2:
            if ana_origins and not ana_dests:
                g_col = 'dest_name'
                label_suffix = "Dest"
            else:
                g_col = 'origin_name'
                label_suffix = "Origin"
            
            title_pie = f"Value Share by {label_suffix} (金额占比 - USD)"
            st.plotly_chart(px.pie(df, names=g_col, values='total_value_usd', hole=0.4, title=title_pie), use_container_width=True)

        st.divider()

        # ============================================
        # 3. 价格分析 (Price Analysis)
        # ============================================
        st.subheader("🏷️ Price Analysis (价格分析)")
        st.caption(f"Based on Unit (基于单位): **{target_unit}**")
        
        if not df_clean_qty.empty:
            r3_c1, r3_c2 = st.columns(2)

            with r3_c1:
                price_org_df = df_clean_qty.groupby('origin_name')[['total_value_usd', 'quantity']].sum().reset_index()
                price_org_df['avg_price'] = price_org_df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
                price_org_df = price_org_df.sort_values('avg_price', ascending=False)
                
                fig_price_org = px.bar(
                    price_org_df, x="origin_name", y="avg_price",
                    title=f"Avg Price by Origin (各出口国均价 - USD/{target_unit})", 
                    color="avg_price", color_continuous_scale="Blues", text_auto='.0f'
                )
                st.plotly_chart(fig_price_org, use_container_width=True)

            with r3_c2:
                price_sp_df = df_clean_qty.groupby('Species')[['total_value_usd', 'quantity']].sum().reset_index()
                price_sp_df['avg_price'] = price_sp_df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
                price_sp_df = price_sp_df.sort_values('avg_price', ascending=False)
                
                fig_price_sp = px.bar(
                    price_sp_df, x="Species", y="avg_price",
                    title=f"Avg Price by Species (各树种均价 - USD/{target_unit})",
                    color="avg_price", color_continuous_scale="Greens", text_auto='.0f'
                )
                st.plotly_chart(fig_price_sp, use_container_width=True)
        else:
            st.warning("No data available for Price Analysis.")

        st.divider()

        # ============================================
        # 4. 贸易商排名 (Top Traders)
        # ============================================
        st.subheader("🏆 Top Traders (贸易商排名 - by USD)")
        
        df['importer_name'] = df['importer_name'].fillna('Unknown').replace('', 'Unknown')
        df['exporter_name'] = df['exporter_name'].fillna('Unknown').replace('', 'Unknown')
        
        trader_c1, trader_c2 = st.columns(2)
        
        with trader_c1:
            top_exporters = df.groupby('exporter_name')['total_value_usd'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_exp = px.bar(
                top_exporters, y="exporter_name", x="total_value_usd", 
                orientation='h',
                title="🔥 Top 10 Exporters (供应商)",
                color="total_value_usd", 
                color_continuous_scale="Oranges", 
                text_auto='.2s' 
            )
            st.plotly_chart(fig_exp, use_container_width=True)
            
        with trader_c2:
            top_importers = df.groupby('importer_name')['total_value_usd'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_imp = px.bar(
                top_importers, y="importer_name", x="total_value_usd", 
                orientation='h',
                title="🛒 Top 10 Buyers (采购商)",
                color="total_value_usd", 
                color_continuous_scale="Teal", 
                text_auto='.2s'
            )
            st.plotly_chart(fig_imp, use_container_width=True)

        st.divider()

        # ============================================
        # 5. 港口分析 (Port Analysis)
        # ============================================
        st.subheader("⚓ Port Analysis (港口分析)")
        
        df['port_of_arrival'] = df['port_of_arrival'].fillna('Unknown').replace('', 'Unknown')

        # --- Top 10 ---
        st.markdown("##### 🏆 Top 10 Ports (Top 10 港口)")
        t1, t2 = st.columns(2)
        with t1:
            top_val_ports = df.groupby('port_of_arrival')['total_value_usd'].sum().nlargest(10).index.tolist()
            chart_port_val = df[df['port_of_arrival'].isin(top_val_ports)].groupby(['port_of_arrival', 'Species'])['total_value_usd'].sum().reset_index()
            fig_pv = px.bar(
                chart_port_val, x="port_of_arrival", y="total_value_usd", color="Species", 
                title="Top 10 by Value (USD)", 
                category_orders={"port_of_arrival": top_val_ports}
            )
            st.plotly_chart(fig_pv, use_container_width=True)
        with t2:
            if not df_clean_qty.empty:
                top_qty_ports = df_clean_qty.groupby('port_of_arrival')['quantity'].sum().nlargest(10).index.tolist()
                chart_port_qty = df_clean_qty[df_clean_qty['port_of_arrival'].isin(top_qty_ports)].groupby(['port_of_arrival', 'Species'])['quantity'].sum().reset_index()
                fig_pq = px.bar(
                    chart_port_qty, x="port_of_arrival", y="quantity", color="Species", 
                    title=f"Top 10 by Volume ({target_unit})", 
                    category_orders={"port_of_arrival": top_qty_ports}
                )
                st.plotly_chart(fig_pq, use_container_width=True)
            else:
                st.info("No volume data available.")

        st.divider()

        # --- Map & Inspector ---
        st.markdown("##### 🌏 Port Inspector & Map (港口透视)")
        
        if not df_clean_qty.empty:
            map_df = df_clean_qty.groupby('port_of_arrival')['quantity'].sum().reset_index()
            val_df = df.groupby('port_of_arrival')['total_value_usd'].sum().reset_index()
            map_df = map_df.merge(val_df, on='port_of_arrival', how='left')
            
            port_species_df = df_clean_qty.groupby(['port_of_arrival', 'Species'])['quantity'].sum().reset_index()
            dom_sp_df = port_species_df.sort_values('quantity', ascending=False).drop_duplicates('port_of_arrival')
            dom_sp_df = dom_sp_df[['port_of_arrival', 'Species']].rename(columns={'Species': 'dominant_species'})
            map_df = map_df.merge(dom_sp_df, on='port_of_arrival', how='left')

            def get_coords(port_name):
                if not port_name: return None, None
                p_upper = str(port_name).upper().strip()
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
                        title=f"Global Port Distribution (Size: Volume {target_unit})",
                        color_continuous_scale="Viridis"
                    )
                    fig_map.update_geos(showcountries=True, countrycolor="#e5e5e5", showcoastlines=True)
                    fig_map.update_layout(height=500, margin={"r":0,"t":30,"l":0,"b":0}, legend=dict(orientation="h", y=-0.1))
                    st.plotly_chart(fig_map, use_container_width=True)
                else:
                    st.warning("No coordinate data available for map.")

            with col_inspector:
                st.markdown("##### 🔬 Detail (详情)")
                sorted_ports = map_df.sort_values('quantity', ascending=False)['port_of_arrival'].tolist()
                if sorted_ports:
                    selected_port = st.selectbox("Select Port (选择港口)", sorted_ports, key="port_inspector_select")
                    
                    port_df_qty = df_clean_qty[df_clean_qty['port_of_arrival'] == selected_port]
                    port_df_val = df[df['port_of_arrival'] == selected_port]
                    
                    p_qty = port_df_qty['quantity'].sum()
                    p_val = port_df_val['total_value_usd'].sum()
                    
                    c1p, c2p = st.columns(2)
                    c1p.metric(f"Vol ({target_unit})", f"{p_qty:,.0f}")
                    c2p.metric("Val (USD)", f"${p_val:,.0f}")
                    
                    st.markdown(f"**{selected_port} - Species Mix**")
                    port_sp_pie = port_df_qty.groupby('Species')['quantity'].sum().reset_index()
                    fig_pie = px.pie(port_sp_pie, names='Species', values='quantity', hole=0.3)
                    fig_pie.update_layout(height=250, margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False)
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No ports found.")
        else:
            st.warning("No volume data for map.")

        st.divider()
        
        # 详情表
        st.subheader("📋 Detailed Records (详细数据)")
        
        cols = ['transaction_date', 'hs_code', 'Species', 'origin_name', 'dest_name', 'port_of_arrival', 'quantity', 'quantity_unit', 'total_value_usd', 'unit_price', 'exporter_name', 'importer_name']
        final_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[final_cols], use_container_width=True)

elif start_d and end_d:
    st.info("👈 Please click 'Load Analysis Report' button to start.")
else:
    st.info("Please select a date range.")