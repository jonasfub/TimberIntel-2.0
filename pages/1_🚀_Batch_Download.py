import streamlit as st
import pandas as pd
import time
import plotly.express as px
from datetime import datetime, timedelta
import config
import utils # 引用公共库

st.set_page_config(page_title="Data Download / 批量下载", page_icon="🚀", layout="wide")

st.title("🚀 Batch Download Center (批量下载中心)")

# 初始化状态
if 'show_heatmap' not in st.session_state:
    st.session_state['show_heatmap'] = False

# --- 侧边栏 (独立于主页) ---
with st.sidebar:
    st.header("⚙️ Settings (参数设置)")
    # 自动获取 Token
    token = utils.get_auto_token()
    if token:
        remaining = int((st.session_state['token_expiry'] - time.time()) / 60)
        st.success(f"✅ API Connected (剩余 {remaining} min)")
    else:
        st.error("❌ Connection Failed (连接失败)")
        
    st.divider()
    selected_category = st.selectbox("Product Group (产品分类)", list(config.HS_CODES_MAP.keys()))
    target_hs_codes = config.HS_CODES_MAP[selected_category]

# --- 界面 ---
st.markdown("### 🛠️ Task Configuration (任务配置)")

c_dl1, c_dl2 = st.columns(2)
with c_dl1: 
    st.caption("Quick Select - Origin (快捷选择-出口国):")
    utils.render_region_buttons("dl_o", c_dl1)
    dl_origins = st.multiselect("Exporting Countries (出口国)", utils.get_all_country_codes(), format_func=utils.country_format_func, key="dl_o")
with c_dl2: 
    st.caption("Quick Select - Dest (快捷选择-进口国):")
    utils.render_region_buttons("dl_d", c_dl2)
    dl_dests = st.multiselect("Importing Countries (进口国)", utils.get_all_country_codes(), format_func=utils.country_format_func, key="dl_d")

c_api1, c_api2, c_api3 = st.columns(3)
with c_api1: selected_hs = st.multiselect("HS Codes (海关编码)", target_hs_codes, key="dl_h")
with c_api2: 
    species_options = list(config.SPECIES_KEYWORDS.keys()) + ["Other", "Unknown"]
    dl_species = st.multiselect("Species Filter (树种 - API筛选)", species_options, key="dl_sp", help="选中后，API请求将只返回包含这些树种关键词的数据。")
with c_api3: selected_dirs = st.multiselect("Trade Flow (贸易方向)", ["imports", "exports"], key="dl_dr")

final_hs = selected_hs if selected_hs else target_hs_codes
final_dirs = selected_dirs if selected_dirs else ["imports", "exports"]

# --- 关键词生成逻辑 ---
api_keyword_str = None
if dl_species:
    # 提取选中树种的第一个关键词，作为 API 搜索词
    kws = []
    for s in dl_species:
        if s in config.SPECIES_KEYWORDS:
            # 取该树种配置列表中的第一个词 (例如 Radiata -> RADIATA)
            kws.append(config.SPECIES_KEYWORDS[s][0])
    
    if len(kws) > 1:
        # 如果选了多个，用空格连接。警告用户 API 可能将其视为 AND 关系
        api_keyword_str = " ".join(kws)
        st.warning(f"⚠️ Multi-Species Filter: Searching for '{api_keyword_str}'. (API likely treats this as 'AND' logic. For volume check, recommend selecting ONE species at a time.)")
    elif kws:
        # 单个选择，正常搜索
        api_keyword_str = kws[0]
        st.success(f"🧬 Species Filter Active: '{api_keyword_str}' (Will be applied to API requests)")

st.divider()

# --- 1. 本地库存检查 ---
st.markdown("#### 1️⃣ Local Stock Check (本地库存检查)")

c_inv_yr, c_inv_btn = st.columns([1, 2])
with c_inv_yr:
    check_year = st.selectbox("Select Year (选择年份)", [2024, 2025, 2026], index=2, key="check_year_box")

with c_inv_btn:
    st.write("") 
    st.write("") 
    if st.button("📊 Show Heatmap (显示库存热力图)"):
        st.session_state['show_heatmap'] = True
        st.rerun()

if st.session_state.get('show_heatmap', False):
    st.divider()
    check_start = f"{check_year}-01-01"
    check_end = f"{check_year}-12-31"
    sp_msg = f"Species: {dl_species}" if dl_species else "Species: All"
    
    with st.spinner(f"Scanning Database for {check_year}... (正在扫描数据库)"):
        # 本地检查依然使用精确的 Python 逻辑
        coverage_df = utils.check_data_coverage(final_hs, check_start, check_end, origin_codes=dl_origins, dest_codes=dl_dests, target_species_list=dl_species)
        
        if not coverage_df.empty:
            full_range = pd.date_range(start=check_start, end=check_end)
            full_df = pd.DataFrame({'date': full_range}).merge(coverage_df, on='date', how='left').fillna(0)
            
            fig = px.scatter(
                full_df, x="date", y=[1]*len(full_df), 
                size="count", color="count", 
                color_continuous_scale=["#e0e0e0", "green"], 
                title=f"Stock Distribution {check_year} (库存分布) | Total: {coverage_df['count'].sum()} records", 
                height=250
            )
            fig.update_yaxes(visible=False, showticklabels=False)
            fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"⚠️ No Data found for {check_year} (该年份无数据)")
    
    if st.button("❌ Close Chart (关闭图表)"):
        st.session_state['show_heatmap'] = False
        st.rerun()

st.divider()

# --- 2. API 预检 ---
st.markdown("#### 2️⃣ API Volume Check (API 预检)")

dl_date_range = st.date_input("Date Range (下载日期范围)", value=(datetime.today() - timedelta(days=7), datetime.today()), key="dl_date_key")

if st.button("🔍 Check Volume (查询数据量)"):
    with st.status(f"Querying Tendata API... (Keyword: {api_keyword_str if api_keyword_str else 'None'})", expanded=True) as status:
        if not token: status.update(label="Auth Failed (认证失败)", state="error"); st.stop()
        results = []
        total_count = 0
        for hs in final_hs:
            for d in final_dirs:
                # 调用 utils, 传入 keyword
                res = utils.fetch_tendata_api(hs, dl_date_range[0], dl_date_range[1], token, d, dl_origins, dl_dests, just_checking=True, keyword=api_keyword_str)
                if res and str(res.get('code')) == '200':
                    data_node = res.get('data', {})
                    count = data_node.get('total', 0)
                    if count == 0: count = data_node.get('totalElements', 0)
                    results.append({"HS Code": hs, "Flow": d, "API Count": count})
                    total_count += count
                else:
                    # [修复] 显示具体的错误信息，方便云端排查
                    error_msg = res.get('msg', 'Unknown Error') if res else 'No Response'
                    error_code = res.get('code', 'N/A') if res else 'N/A'
                    results.append({"HS Code": hs, "Flow": d, "API Count": f"Err {error_code}: {error_msg}"})
                    
        status.update(label="Complete (完成)", state="complete")
        if results:
            st.table(pd.DataFrame(results))
            if total_count > 0: st.success(f"✅ Total found on API: {total_count} records.")

# --- 3. 执行下载 (包含断点续传逻辑) ---
st.markdown("#### 3️⃣ Execute Download (执行下载)")

# [NEW] 布局调整：增加起始页输入框
c_exec1, c_exec2 = st.columns([1, 4])
with c_exec1:
    start_page_val = st.number_input("Start Page (起始页码)", min_value=1, value=1, help="用于断点续传。注意：此页码将应用于所有选中的 HS Code，建议续传时只勾选单个任务。")
with c_exec2:
    st.write("") # Spacer
    st.write("") # Spacer
    start_btn = st.button("🚀 Start Download (开始下载 - 自动翻页)", type="primary")

if start_btn:
    with st.status("Downloading... (下载中)", expanded=True) as status:
        if not token: status.update(label="Auth Failed (认证失败)", state="error"); st.stop()
        progress_bar = st.progress(0); log_box = st.expander("Process Log (运行日志)", expanded=True)
        total_ops = len(final_hs) * len(final_dirs); current_op = 0; stats = {"saved": 0}
        
        for hs in final_hs:
            for d in final_dirs:
                current_op += 1; progress_bar.progress(int(current_op/total_ops*100))
                
                # [NEW] 使用用户定义的起始页
                page = start_page_val
                if page > 1:
                    log_box.info(f"⏭️ Resuming {hs} ({d}) from Page {page}...")
                
                has_more_data = True
                total_saved_for_this_hs = 0
                
                while has_more_data:
                    # 调用 utils, 传入 keyword
                    res = utils.fetch_tendata_api(hs, dl_date_range[0], dl_date_range[1], token, d, dl_origins, dl_dests, just_checking=False, page_no=page, keyword=api_keyword_str)
                    if res and str(res.get('code')) == '200':
                        saved_count, api_count = utils.save_to_supabase(res) # 调用 utils
                        total_saved_for_this_hs += saved_count
                        stats['saved'] += saved_count
                        log_box.write(f"🔄 HS {hs} ({d}) - P{page}: Fetched {api_count} records")
                        if api_count < 50: has_more_data = False
                        else: page += 1; time.sleep(0.3)
                    else:
                        # 记录具体的下载错误
                        err_msg = res.get('msg', 'Unknown') if res else 'No Resp'
                        log_box.error(f"HS {hs}: Error - {err_msg}"); has_more_data = False
                
                if total_saved_for_this_hs > 0: log_box.success(f"✅ HS {hs} ({d}) Done: Saved {total_saved_for_this_hs}")
                else: log_box.warning(f"HS {hs} ({d}): No Data")
        
        status.update(label="All Done (全部完成)", state="complete")
        st.success(f"🎉 Total Saved (累计入库): {stats['saved']} records")