import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import config
import utils  # 引用 utils.py

# --- 页面基础设置 ---
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
    
    # 简单的 Token 状态检查
    if utils.get_auto_token(): # 尝试获取或刷新 Token
        st.success("✅ API Token 有效")
    else:
        st.info("API 未激活 (进入下载页自动激活)")
        
    st.divider()
    
    selected_category = st.selectbox("产品分类", list(config.HS_CODES_MAP.keys()))
    target_hs_codes = config.HS_CODES_MAP[selected_category]
    # 默认过去一年
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
        batch_size = 5000  # 保持 5000
        
        # 优化：仅需要的列
        needed_columns = "transaction_date,hs_code,product_desc_text,origin_country_code,dest_country_code,quantity,quantity_unit,total_value_usd,port_of_arrival,exporter_name,importer_name,unique_record_id"
        
        with st.status("🚀 初始化高速提取任务 (Cursor Mode)...", expanded=True) as status:
            msg_placeholder = st.empty()
            progress_bar = st.progress(0)
            
            # --- 🚀 核心修改：使用 last_id 进行游标分页 ---
            last_id = None 
            total_fetched = 0
            
            try:
                while True:
                    msg_placeholder.info(f"🔄 正在提取数据... 已获取 {total_fetched} 条")
                    
                    # 构建查询
                    query = utils.supabase.table('trade_records')\
                        .select(needed_columns)\
                        .gte('transaction_date', start_d).lte('transaction_date', end_d)
                    
                    # 应用筛选
                    if ana_origins: query = query.in_('origin_country_code', ana_origins)
                    if ana_dests: query = query.in_('dest_country_code', ana_dests)
                    
                    # ⚡️ 性能优化关键点：
                    # 1. 不再使用 range (offset)，而是使用 .lt (less than) 上一次的 last_id
                    # 2. 我们依赖 unique_record_id 的索引来快速定位
                    if last_id:
                        query = query.lt('unique_record_id', last_id)
                    
                    # 3. 必须按 ID 倒序排列，确保游标逻辑正确
                    response = query.order("unique_record_id", desc=True).limit(batch_size).execute()
                    
                    rows = response.data
                    if not rows: 
                        break # 没有数据了，停止
                    
                    all_rows.extend(rows)
                    total_fetched += len(rows)
                    
                    # 更新游标：记录这一批最后一条数据的 ID
                    last_id = rows[-1]['unique_record_id']
                    
                    # 更新进度条 (假定大概 50w 条，只是视觉效果)
                    if total_fetched < 500000:
                        progress_bar.progress(min(total_fetched / 500000, 1.0))
                    
                    # 如果取到的数据少于 batch_size，说明是最后一页了
                    if len(rows) < batch_size:
                        break
                
                progress_bar.empty()
                msg_placeholder.empty()
                status.update(label=f"✅ 提取完成: 共 {len(all_rows)} 条记录", state="complete")
                
                if all_rows:
                    # 转为 DataFrame
                    df = pd.DataFrame(all_rows)
                    
                    # 💡 提示：因为我们按 ID 下载，所以这里要在内存里重新按日期排个序，方便后续画图
                    df = df.sort_values(by='transaction_date', ascending=False)
                    
                    st.session_state['analysis_df'] = df
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
    st.caption(f"🔎 覆盖检查: 数据库返回的最早日期是 `{min_date}`，最晚日期是 `{max_date}`")
    
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
            dirty_rows = df[df['Species'].isin(forbidden_species)]
            if not dirty_rows.empty:
                df = df[~df['Species'].isin(forbidden_species)]
    
    # --- 本地筛选 ---
    if ana_species_selected: df = df[df['Species'].isin(ana_species_selected)]
    if ana_origins: df = df[df['origin_country_code'].isin(ana_origins)]
    if ana_dests: df = df[df['dest_country_code'].isin(ana_dests)]

    if df.empty:
        st.warning("本地筛选后无数据")
    else:
        # 3. 计算指标
        df['unit_price'] = df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 and pd.notnull(x['total_value_usd']) else 0, axis=1)
        
        def get_country_name_en(code):
            full_name = config.COUNTRY_NAME_MAP.get(code, code)
            if '(' in full_name: return full_name.split(' (')[0]
            return full_name

        df['origin_name'] = df['origin_country_code'].apply(get_country_name_en)
        df['dest_name'] = df['dest_country_code'].apply(get_country_name_en)
        df['Month'] = pd.to_datetime(df['transaction_date']).dt.to_period('M').astype(str)
        sorted_months = sorted(df['Month'].unique())

        # ========================================================
        # 🔥 [核心更新] 全局单位筛选 (Global Unit Filter)
        # ========================================================
        
        df['quantity_unit'] = df['quantity_unit'].fillna('Unknown')
        vol_units = df['quantity_unit'].unique().tolist()
        
        # 自动探测 M3
        default_unit_idx = 0
        for i, u in enumerate(vol_units):
            if str(u).upper() in ['MTQ', 'CBM', 'M3', 'M3 ']:
                default_unit_idx = i
                break
        
        c_unit_sel, _ = st.columns([1, 3])
        with c_unit_sel:
            target_unit = st.selectbox(
                "🔢 全局单位清洗 (Unit Filter):", 
                vol_units, 
                index=default_unit_idx,
                help="选中特定单位（如 M3）后，所有货量统计图表将自动过滤掉其他单位的脏数据。"
            )
            
        # 🌟 第一步：按单位过滤
        df_clean_qty = df[df['quantity_unit'] == target_unit].copy()
        
        # 🌟 [关键新增] 第二步：智能价格清洗 (Smart Price Filter)
        # 目的是过滤掉单位写着 "M3" 但数值其实是 "KG" 的离谱数据
        # 逻辑：如果单价 (USD/Unit) 极低 (<$1)，说明分母(数量)极大，肯定是错的
        
        with st.expander("🧹 异常值智能清洗 (Smart Outlier Filter)", expanded=True):
            c_cl1, c_cl2 = st.columns([3, 1])
            with c_cl1:
                st.info("💡 开启此功能可自动剔除【单价极低】的数据（通常是KG错标为M3导致数量虚高）。")
            with c_cl2:
                enable_price_clean = st.checkbox("启用清洗", value=True)
                
            if enable_price_clean:
                # 默认最低单价 $5 (不管是木片还是原木，1立方米都不太可能低于5美元)
                min_valid_price = st.number_input("最低有效单价 ($/Unit)", value=5.0, step=1.0, help="低于此单价的记录将被视为脏数据剔除。")
                
                # 计算临时单价
                df_clean_qty['calc_price'] = df_clean_qty.apply(
                    lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1
                )
                
                # 记录清洗前数量
                count_before = len(df_clean_qty)
                # 执行过滤
                df_clean_qty = df_clean_qty[df_clean_qty['calc_price'] >= min_valid_price]
                count_after = len(df_clean_qty)
                
                if count_before > count_after:
                    st.warning(f"🧹 已自动剔除 {count_before - count_after} 条疑似脏数据 (单价 < ${min_valid_price})")

        # --- KPI ---
        k1, k2, k3 = st.columns(3)
        k1.metric("记录数 (Count)", len(df))
        
        # KPI 使用清洗后的数据
        clean_qty_sum = df_clean_qty['quantity'].sum()
        k2.metric(f"总数量 (Total {target_unit})", f"{clean_qty_sum:,.0f}")
        
        # 总金额使用原始数据 (df)
        total_val = df['total_value_usd'].sum()
        k3.metric("总金额 (Total Value USD)", f"${total_val:,.0f}")
        
        st.divider()

        # ============================================
        # 1. 数量趋势 (Volume Trends) - 使用 Clean DF
        # ============================================
        st.subheader("📈 数量趋势 (Volume Trends)")
        
        if not df_clean_qty.empty:
            r1_c1, r1_c2 = st.columns(2)
            
            with r1_c1:
                chart_species = df_clean_qty.groupby(['Month', 'Species'])['quantity'].sum().reset_index()
                fig_sp = px.bar(
                    chart_species, x="Month", y="quantity", color="Species", 
                    title=f"月度数量趋势 - 按树种 ({target_unit})",
                    category_orders={"Month": sorted_months}
                )
                fig_sp.update_xaxes(type='category')
                st.plotly_chart(fig_sp, use_container_width=True)

            with r1_c2:
                chart_origin = df_clean_qty.groupby(['Month', 'origin_name'])['quantity'].sum().reset_index()
                fig_org = px.bar(
                    chart_origin, x="Month", y="quantity", color="origin_name",
                    title=f"月度数量趋势 - 按出口国 ({target_unit})",
                    category_orders={"Month": sorted_months}
                )
                fig_org.update_xaxes(type='category')
                st.plotly_chart(fig_org, use_container_width=True)
        else:
            st.warning(f"在单位 ({target_unit}) 下无有效数据。")

        st.divider()
        
        # ============================================
        # 2. 金额趋势与结构 (Value) - 使用 Full DF
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
                label_suffix = "Dest"
            else:
                g_col = 'origin_name'
                label_suffix = "Origin"
            
            # 使用 Value 占比
            title_pie = f"出口国金额占比 ({label_suffix} Share - by Value USD)"
            st.plotly_chart(px.pie(df, names=g_col, values='total_value_usd', hole=0.4, title=title_pie), use_container_width=True)

        st.divider()

        # ============================================
        # 3. 价格分析 (Price Analysis - USD) - 使用 Clean DF
        # ============================================
        st.subheader("🏷️ 价格分析 (Price Analysis)")
        st.caption(f"当前分析基于单位: **{target_unit}**")
        
        if not df_clean_qty.empty:
            r3_c1, r3_c2 = st.columns(2)

            with r3_c1:
                price_org_df = df_clean_qty.groupby('origin_name')[['total_value_usd', 'quantity']].sum().reset_index()
                price_org_df['avg_price'] = price_org_df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
                price_org_df = price_org_df.sort_values('avg_price', ascending=False)
                
                fig_price_org = px.bar(
                    price_org_df, x="origin_name", y="avg_price",
                    title=f"各出口国加权均价 (Avg Price - {target_unit})", 
                    color="avg_price", color_continuous_scale="Blues", text_auto='.0f'
                )
                fig_price_org.update_layout(xaxis_title="Origin", yaxis_title=f"Avg Price (USD/{target_unit})")
                st.plotly_chart(fig_price_org, use_container_width=True)

            with r3_c2:
                price_sp_df = df_clean_qty.groupby('Species')[['total_value_usd', 'quantity']].sum().reset_index()
                price_sp_df['avg_price'] = price_sp_df.apply(lambda x: x['total_value_usd'] / x['quantity'] if x['quantity'] > 0 else 0, axis=1)
                price_sp_df = price_sp_df.sort_values('avg_price', ascending=False)
                
                fig_price_sp = px.bar(
                    price_sp_df, x="Species", y="avg_price",
                    title=f"各树种加权均价 (Avg Price - {target_unit})",
                    color="avg_price", color_continuous_scale="Greens", text_auto='.0f'
                )
                fig_price_sp.update_layout(xaxis_title="Species", yaxis_title=f"Avg Price (USD/{target_unit})")
                st.plotly_chart(fig_price_sp, use_container_width=True)
        else:
            st.warning("暂无数据")

        st.divider()

        # ============================================
        # 4. 贸易商排名 (Top Traders - by Value USD) - 使用 Full DF
        # ============================================
        st.subheader("🏆 贸易商排名 (Top Traders - by Value USD)")
        
        df['importer_name'] = df['importer_name'].fillna('Unknown').replace('', 'Unknown')
        df['exporter_name'] = df['exporter_name'].fillna('Unknown').replace('', 'Unknown')
        
        trader_c1, trader_c2 = st.columns(2)
        
        with trader_c1:
            # Top Exporters (按金额 USD)
            top_exporters = df.groupby('exporter_name')['total_value_usd'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_exp = px.bar(
                top_exporters, y="exporter_name", x="total_value_usd", 
                orientation='h',
                title="🔥 Top 10 Exporters (供应商) - USD",
                color="total_value_usd", 
                color_continuous_scale="Oranges", 
                text_auto='.2s' 
            )
            fig_exp.update_layout(xaxis_title="Total Value (USD)")
            st.plotly_chart(fig_exp, use_container_width=True)
            
        with trader_c2:
            # Top Buyers (按金额 USD)
            top_importers = df.groupby('importer_name')['total_value_usd'].sum().nlargest(10).sort_values(ascending=True).reset_index()
            fig_imp = px.bar(
                top_importers, y="importer_name", x="total_value_usd", 
                orientation='h',
                title="🛒 Top 10 Buyers (采购商) - USD",
                color="total_value_usd", 
                color_continuous_scale="Teal", 
                text_auto='.2s'
            )
            fig_imp.update_layout(xaxis_title="Total Value (USD)")
            st.plotly_chart(fig_imp, use_container_width=True)

        st.divider()

        # ============================================
        # 5. 港口分析 (Port Analysis)
        # ============================================
        st.subheader("⚓ 港口分析 (Port Analysis)")
        
        df['port_of_arrival'] = df['port_of_arrival'].fillna('Unknown').replace('', 'Unknown')

        # --- Top 10 ---
        st.markdown("##### 🏆 Top 10 港口排名")
        t1, t2 = st.columns(2)
        with t1:
            # 按金额 (Value) - 使用 Full DF
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
            # [修正] 按数量 (Volume) - 必须使用 df_clean_qty 防止单位污染
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
                st.info("无有效数量单位数据")

        st.divider()

        # --- Map & Inspector ---
        st.markdown("##### 🌏 港口透视 (Port Inspector & Map)")
        
        # 地图逻辑继续使用 df_clean_qty 来显示气泡大小 (Size)，防止 KG 数据生成巨大气泡
        if not df_clean_qty.empty:
            map_df = df_clean_qty.groupby('port_of_arrival')['quantity'].sum().reset_index()
            # 合并 Value 信息 (从 Full DF 获取该港口的总金额)
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
                        title=f"全球港口分布 (Size: Volume {target_unit})",
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
                    
                    # 详情也区分 DF
                    port_df_qty = df_clean_qty[df_clean_qty['port_of_arrival'] == selected_port]
                    port_df_val = df[df['port_of_arrival'] == selected_port]
                    
                    p_qty = port_df_qty['quantity'].sum()
                    p_val = port_df_val['total_value_usd'].sum()
                    
                    c1p, c2p = st.columns(2)
                    c1p.metric(f"Volume ({target_unit})", f"{p_qty:,.0f}")
                    c2p.metric("Value (USD)", f"${p_val:,.0f}")
                    
                    st.markdown(f"**{selected_port} - 材种分布 ({target_unit})**")
                    port_sp_pie = port_df_qty.groupby('Species')['quantity'].sum().reset_index()
                    fig_pie = px.pie(port_sp_pie, names='Species', values='quantity', hole=0.3)
                    fig_pie.update_layout(height=250, margin={"r":0,"t":0,"l":0,"b":0}, showlegend=False)
                    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("无港口数据")
        else:
            st.warning("无有效单位数据，无法显示地图")

        st.divider()
        
        # 详情表
        st.subheader("📋 详细数据 (Details)")
        
        # [NEW] 加上 unit_price, importer_name, unique_record_id
        cols = ['transaction_date', 'hs_code', 'Species', 'origin_name', 'dest_name', 'port_of_arrival', 'quantity', 'quantity_unit', 'total_value_usd', 'unit_price', 'exporter_name', 'importer_name']
        final_cols = [c for c in cols if c in df.columns]
        st.dataframe(df[final_cols], use_container_width=True)

elif start_d and end_d:
    st.info("👈 请点击“加载分析报告”按钮开始分析")
else:
    st.info("请选择日期范围")