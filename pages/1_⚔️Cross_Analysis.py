import streamlit as st
import pandas as pd
import plotly.express as px
import config
import utils

# --- 页面配置 ---
st.set_page_config(page_title="Cross Analysis", page_icon="⚔️", layout="wide")

st.title("⚔️ Cross Analysis - 交叉对比分析")

# --- 1. 数据守门员：检查是否有数据 ---
if 'analysis_df' not in st.session_state or st.session_state['analysis_df'].empty:
    st.warning("⚠️ 请先在【首页 (Timber Intel Core)】加载数据。")
    st.info("💡 提示：此页面依赖首页提取的缓存数据，无需重复查询数据库。")
    st.stop() 

# 获取数据
df = st.session_state['analysis_df'].copy()

# --- 定义默认国家列表 (亚洲六国) ---
DEFAULT_ASIA_MARKETS = ["China", "India", "Vietnam", "Thailand", "Malaysia", "Indonesia"]

# --- 2. 基础数据清洗 ---
# 🔥 [修复核心] 安全的国家名称转换函数 (防止空值报错)
def get_country_name_en(code):
    # 1. 如果代码本身是空的，直接返回 Unknown
    if pd.isna(code) or code == "" or code is None:
        return "Unknown"
        
    # 2. 获取全名，如果找不到则返回原代码
    full_name = config.COUNTRY_NAME_MAP.get(code, code)
    
    # 3. 强制转为字符串，防止非 String 类型导致报错
    full_name_str = str(full_name)
    
    # 4. 安全进行切割
    if '(' in full_name_str: 
        return full_name_str.split(' (')[0]
        
    return full_name_str

df['origin_name'] = df['origin_country_code'].apply(get_country_name_en)
df['dest_name'] = df['dest_country_code'].apply(get_country_name_en)

if 'Species' not in df.columns:
    df['Species'] = df['product_desc_text'].apply(utils.identify_species)

# ==========================================
# 🆕 辅助函数：HS Code 形态分类 (Logs vs Lumber)
# ==========================================
def classify_form(hs_code_val):
    hs_str = str(hs_code_val)
    for category, codes in config.HS_CODES_MAP.items():
        if any(hs_str.startswith(c) for c in codes):
            if "Softwood Logs" in category: return "Softwood", "Logs"
            if "Softwood Lumber" in category: return "Softwood", "Lumber"
            if "Hardwood Logs" in category: return "Hardwood", "Logs"
            if "Hardwood Lumber" in category: return "Hardwood", "Lumber"
    return "Other", "Other"

df[['Wood_Type', 'Product_Form']] = df['hs_code'].apply(
    lambda x: pd.Series(classify_form(x))
)

# --- 3. 顶部筛选栏 (Global Filter) ---
with st.container():
    st.markdown("### 🛠️ 数据预处理 (Preprocessing)")
    c1, c2, c3 = st.columns([1.5, 1, 1.5])
    
    raw_units = df['quantity_unit'].fillna('Unknown').unique().tolist()
    
    with c1:
        # 1. 默认清空（即全选）
        target_units = st.multiselect(
            "1️⃣ 包含的单位 (多选) / Included Units", 
            raw_units, 
            default=[], 
            placeholder="留空即全选 (Select All)",
            help="留空表示不过滤单位（显示所有）。如果只想看 M3，请手动选择。"
        )
        
    with c2:
        min_price = st.number_input("2️⃣ 最低单价清洗 ($) / Min Price Filter", value=0.0, step=1.0, help="设为 0 可查看所有数据")
    
    with c3:
        # 2. 默认按金额 (Value) -> index=1
        measure_metric = st.radio(
            "3️⃣ 分析指标 (Metric)", 
            ["Volume (数量)", "Value (金额 USD)"], 
            index=1, 
            horizontal=True
        )
        y_col = 'quantity' if "Volume" in measure_metric else 'total_value_usd'
        
        if "Volume" in measure_metric:
            unit_str = ",".join([str(u) for u in target_units]) if target_units else "All Units"
            y_title = f"Total Volume ({unit_str})"
        else:
            y_title = "Total USD"

    # --- 执行清洗 ---
    if target_units:
        df_clean = df[df['quantity_unit'].isin(target_units)].copy()
    else:
        df_clean = df.copy() 

    df_clean['calc_price'] = df_clean.apply(lambda x: x['total_value_usd']/x['quantity'] if x['quantity'] > 0 else 0, axis=1)
    df_clean = df_clean[df_clean['calc_price'] >= min_price]

    # --- 🚨 全局数据丢失雷达 ---
    if not df_clean.empty:
        countries_raw = set(df['dest_name'].unique())
        countries_clean = set(df_clean['dest_name'].unique())
        lost_countries = countries_raw - countries_clean
        
        if lost_countries:
            lost_details = []
            for c in list(lost_countries)[:5]: 
                c_units = df[df['dest_name'] == c]['quantity_unit'].unique().tolist()
                lost_details.append(f"{c} (单位: {c_units})")
            
            error_msg = f"⚠️ **注意：** 检测到 **{len(lost_countries)}** 个国家的数据被完全过滤掉。"
            if len(lost_countries) > 5: error_msg += f" 包括: {', '.join(lost_details)} 等..."
            else: error_msg += f" 详情: {', '.join(lost_details)}"
            st.warning(error_msg)

st.divider()

# ==========================================
# 📊 1. Monthly Trend: Logs vs Lumber
# ==========================================
st.subheader("📈 1. 月度进口趋势：原木 vs 板材 (Monthly Trend: Logs vs Lumber)")
st.caption("选择一个国家，查看其 Logs (原木) 与 Lumber (板材) 的月度进口趋势。")

# 筛选出只有 Logs 和 Lumber 的数据
df_form = pd.DataFrame()
if not df_clean.empty:
    df_form = df_clean[df_clean['Product_Form'].isin(['Logs', 'Lumber'])]

if not df_form.empty:
    country_options = df_form['dest_name'].unique().tolist()
    country_options.sort()
    
    c_trend1, c_trend2 = st.columns([1, 3])
    
    with c_trend1:
        target_country = st.selectbox("👉 选择国家 (Select Country)", country_options, index=0)
        wood_filter = st.radio("木材类型过滤", ["All (全部)", "Softwood (仅软木)", "Hardwood (仅硬木)"], horizontal=True)

        # 🆕 1. 预先按照“国家”和“木材类型”过滤数据，以便获取准确的树种列表
        df_temp = df_form[df_form['dest_name'] == target_country].copy()
        
        if "Softwood" in wood_filter:
            df_temp = df_temp[df_temp['Wood_Type'] == 'Softwood']
        elif "Hardwood" in wood_filter:
            df_temp = df_temp[df_temp['Wood_Type'] == 'Hardwood']
            
        # 🆕 2. 获取当前条件下的可用树种列表
        available_species = df_temp['Species'].dropna().unique().tolist()
        available_species.sort()
        
        # 🆕 3. 添加树种多选筛选器 (Multiselect)
        selected_species = st.multiselect(
            "🌳 树种筛选 (Select Species)", 
            options=available_species, 
            default=[], 
            help="留空表示查看所有树种 (Select specific species or leave blank for all)"
        )

    with c_trend2:
        # 🆕 4. 继承前面过滤好的数据
        df_trend = df_temp.copy()
        
        # 🆕 5. 如果用户选择了特定树种，则应用二次过滤
        if selected_species:
            df_trend = df_trend[df_trend['Species'].isin(selected_species)]
            
        # 👇 以下绘图逻辑保持原样
        if not df_trend.empty:
            df_trend['Month'] = pd.to_datetime(df_trend['transaction_date']).dt.to_period('M').astype(str)
            chart_trend = df_trend.groupby(['Month', 'Product_Form'])[y_col].sum().reset_index()
            
            # 🍬 糖果配色：Coral Pink vs Mint Blue
            fig_trend = px.bar(
                chart_trend,
                x='Month',
                y=y_col,
                color='Product_Form',
                barmode='group',
                title=f"{target_country} - 月度进口趋势 (Monthly Logs vs Lumber Trend)",
                color_discrete_map={'Logs': '#FF6B6B', 'Lumber': '#4ECDC4'}, 
                text_auto='.2s'
            )
            fig_trend.update_xaxes(type='category')
            st.plotly_chart(fig_trend, use_container_width=True)
        else:
            st.info(f"该国家 ({target_country}) 在所选条件下无数据。")
else:
    st.warning("无 Logs/Lumber 数据可供分析")

st.divider()

# ==========================================
# 📊 2. Industrial Form: Logs vs Lumber (Snapshot)
# ==========================================
st.subheader("🏭 2. 产业形态对比：原木 vs 板材 (Industrial Form: Logs vs Lumber)")
st.caption("对比各国在 **Softwood (软木)** 和 **Hardwood (硬木)** 领域的进口形态差异。")

if not df_form.empty:
    all_dests = df_form.groupby('dest_name')[y_col].sum().sort_values(ascending=False).index.tolist()
    
    # 3. 默认选中 6 个国家
    default_dests = [c for c in DEFAULT_ASIA_MARKETS if c in all_dests]
    if not default_dests:
        default_dests = all_dests[:6]
    
    selected_dests_form = st.multiselect("选择对比国家 (Select Countries)", all_dests, default=default_dests, key="sel_form_country")
    df_form_final = df_form[df_form['dest_name'].isin(selected_dests_form)]
    
    col_soft, col_hard = st.columns(2)
    
    with col_soft:
        st.markdown("#### 🌲 Softwood (软木)")
        df_soft = df_form_final[df_form_final['Wood_Type'] == 'Softwood']
        if not df_soft.empty:
            chart_soft = df_soft.groupby(['dest_name', 'Product_Form'])[y_col].sum().reset_index()
            fig_soft = px.bar(
                chart_soft, x='dest_name', y=y_col, color='Product_Form',
                title=f"Softwood: 原木 vs 板材 (Logs vs Lumber)", barmode='group', 
                color_discrete_map={'Logs': '#8B4513', 'Lumber': '#DEB887'}, text_auto='.2s'
            )
            st.plotly_chart(fig_soft, use_container_width=True)
        else:
            st.info("无 Softwood 数据")

    with col_hard:
        st.markdown("#### 🌳 Hardwood (硬木)")
        df_hard = df_form_final[df_form_final['Wood_Type'] == 'Hardwood']
        if not df_hard.empty:
            chart_hard = df_hard.groupby(['dest_name', 'Product_Form'])[y_col].sum().reset_index()
            fig_hard = px.bar(
                chart_hard, x='dest_name', y=y_col, color='Product_Form',
                title=f"Hardwood: 原木 vs 板材 (Logs vs Lumber)", barmode='group',
                color_discrete_map={'Logs': '#2E8B57', 'Lumber': '#98FB98'}, text_auto='.2s'
            )
            st.plotly_chart(fig_hard, use_container_width=True)
        else:
            st.info("无 Hardwood 数据")
else:
    st.warning("无数据可展示")

st.divider()

# ==========================================
# 📊 3. Cross Market: 进口国采购结构对比
# ==========================================
st.subheader("🌏 3. 市场结构分析：进口国采购偏好 (Market Structure: Import Preferences)")
st.caption("分析不同国家的采购偏好 (已隐藏 'Other' 树种)")

if not df_clean.empty:
    df_no_other_mkt = df_clean[df_clean['Species'] != 'Other']
    
    if not df_no_other_mkt.empty:
        all_dests_mkt = df_no_other_mkt.groupby('dest_name')[y_col].sum().sort_values(ascending=False).index.tolist()
        
        # 4. 默认选中 6 个国家
        default_dests_mkt = [c for c in DEFAULT_ASIA_MARKETS if c in all_dests_mkt]
        if not default_dests_mkt:
            default_dests_mkt = all_dests_mkt[:6]
        
        c_sel_mkt, _ = st.columns([2, 1])
        with c_sel_mkt:
            selected_dests_mkt = st.multiselect(
                "👉 选择要对比的进口国 (Select Markets)", 
                all_dests_mkt, 
                default=default_dests_mkt,
                key="sel_mkt_country"
            )

        df_market_view = df_no_other_mkt[df_no_other_mkt['dest_name'].isin(selected_dests_mkt)]
        
        if not df_market_view.empty:
            chart_data_1 = df_market_view.groupby(['dest_name', 'Species'])[y_col].sum().reset_index()

            c_chart1, c_settings1 = st.columns([3, 1])
            with c_settings1:
                st.markdown("#### 图表设置")
                barmode_1 = st.selectbox("堆叠模式", ["stack", "group", "relative"], index=0, key="mode1")
                orientation_1 = st.selectbox("方向", ["v", "h"], index=0, key="orient1")

            with c_chart1:
                fig1 = px.bar(
                    chart_data_1, 
                    x='dest_name' if orientation_1 == 'v' else y_col,
                    y=y_col if orientation_1 == 'v' else 'dest_name',
                    color='Species',
                    title=f"进口国采购结构 (Import Structure by Country)",
                    barmode=barmode_1,
                    orientation=orientation_1,
                    text_auto='.2s',
                    height=500
                )
                st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("请选择至少一个国家")
    else:
        st.info("过滤 'Other' 后无数据")
else:
    st.warning("无数据可展示")

st.divider()

# ==========================================
# 📊 4. Cross Product: 树种流向对比
# ==========================================
st.subheader("🌲 4. 产品流向分析：树种市场分布 (Product Flow: Species Distribution)")
st.caption("分析不同树种的市场分布 (已隐藏 'Other' 树种)")

if not df_clean.empty:
    df_no_other_prod = df_clean[df_clean['Species'] != 'Other']
    
    if not df_no_other_prod.empty:
        all_dests_prod = df_no_other_prod.groupby('dest_name')[y_col].sum().sort_values(ascending=False).index.tolist()
        
        # 5. 默认选中 6 个国家
        default_dests_prod = [c for c in DEFAULT_ASIA_MARKETS if c in all_dests_prod]
        if not default_dests_prod:
            default_dests_prod = [] 
            
        c_sel_prod, _ = st.columns([2, 1])
        with c_sel_prod:
            selected_dests_prod = st.multiselect(
                "🔍 筛选进口国 (Filter Destination)", 
                all_dests_prod,
                default=default_dests_prod,
                key="sel_prod_dest",
                help="选择特定进口国，查看该国主要进口的树种结构。留空显示全球。"
            )

        # 应用筛选
        if selected_dests_prod:
            df_product_view = df_no_other_prod[df_no_other_prod['dest_name'].isin(selected_dests_prod)]
            chart_title_suffix = f"销往: {', '.join(selected_dests_prod[:3])}..." if len(selected_dests_prod) > 3 else f"销往: {', '.join(selected_dests_prod)}"
        else:
            df_product_view = df_no_other_prod
            chart_title_suffix = "全球市场 (Global Markets)"

        if not df_product_view.empty:
            # Top 15 树种
            top_species = df_product_view.groupby('Species')[y_col].sum().nlargest(15).index.tolist()
            df_product_view = df_product_view[df_product_view['Species'].isin(top_species)]

            chart_data_2 = df_product_view.groupby(['Species', 'dest_name'])[y_col].sum().reset_index()

            c_chart2, c_settings2 = st.columns([3, 1])
            with c_settings2:
                st.markdown("#### 图表设置")
                barmode_2 = st.selectbox("堆叠模式", ["stack", "group", "relative"], index=0, key="mode2")
                show_percent = st.checkbox("查看百分比占比 (100%)", value=False)

            with c_chart2:
                fig2 = px.bar(
                    chart_data_2, 
                    x='Species',
                    y=y_col,
                    color='dest_name',
                    title=f"Top 15 树种流向 - {chart_title_suffix}",
                    barmode=barmode_2 if not show_percent else 'relative', 
                    text_auto='.2s'
                )
                
                if show_percent:
                    fig2.update_layout(barnorm='percent')
                    fig2.update_yaxes(title="Percent (%)")
                else:
                    fig2.update_layout(yaxis_title=y_title)
                    
                st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("所选进口国无数据")
    else:
        st.info("过滤 'Other' 后无数据")
else:
    st.warning("无数据可展示")

st.divider()

# ==========================================
# 📊 5. Market-Product Matrix (热力图)
# ==========================================
st.subheader("🔥 5. 市场-产品热力矩阵 (Market-Product Heatmap Matrix)")
st.caption("(已隐藏 'Other' 树种)")

if not df_clean.empty:
    df_matrix = df_clean[df_clean['Species'] != 'Other']
    
    if not df_matrix.empty:
        pivot_df = df_matrix.groupby(['dest_name', 'Species'])[y_col].sum().reset_index()
        valid_dests = df_matrix.groupby('dest_name')[y_col].sum().nlargest(15).index.tolist()
        valid_species = df_matrix.groupby('Species')[y_col].sum().nlargest(15).index.tolist()

        pivot_df = pivot_df[
            (pivot_df['dest_name'].isin(valid_dests)) & 
            (pivot_df['Species'].isin(valid_species))
        ]

        fig3 = px.density_heatmap(
            pivot_df, 
            x="dest_name", 
            y="Species", 
            z=y_col, 
            text_auto='.2s',
            color_continuous_scale="Viridis",
            title=f"采购热度矩阵 (Top 15 Countries x Top 15 Species)"
        )
        st.plotly_chart(fig3, use_container_width=True)
    else:
        st.info("过滤 'Other' 后无数据")
else:
    st.warning("无数据可展示")