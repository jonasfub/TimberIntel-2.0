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
        # 简单计算剩余时间
        expiry = st.session_state.get('token_expiry', time.time())
        remaining = int((expiry - time.time()) / 60)
        if remaining < 0: remaining = 0
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
    kws = []
    for s in dl_species:
        if s in config.SPECIES_KEYWORDS:
            kws.append(config.SPECIES_KEYWORDS[s][0])
    
    if len(kws) > 1:
        api_keyword_str = " ".join(kws)
        st.warning(f"⚠️ Multi-Species Filter: Searching for '{api_keyword_str}'. (API likely treats this as 'AND' logic. For volume check, recommend selecting ONE species at a time.)")
    elif kws:
        api_keyword_str = kws[0]
        st.success(f"🧬 Species Filter Active: '{api_keyword_str}' (Will be applied to API requests)")

st.divider()

# ========================================================
# 1. [核心更新] 本地库存检查 (Local Stock Check) - 支持日期范围
# ========================================================
st.markdown("#### 1️⃣ Local Stock Check (本地库存检查)")

# 改为两列：日期选择 + 按钮
c_inv_date, c_inv_btn = st.columns([2, 1])

with c_inv_date:
    # 默认查看过去 30 天
    default_start = datetime.today() - timedelta(days=30)
    default_end = datetime.today()
    
    check_range = st.date_input(
        "📅 Select Date Range (选择检查范围)", 
        value=(default_start, default_end), 
        key="stock_check_date_range",
        help="对于印度等数据量巨大的国家，请尽量缩小日期范围（如只查最近1个月），以防止数据库查询超时。"
    )

with c_inv_btn:
    st.write("") 
    st.write("") 
    # 只有选好日期才能点
    if st.button("📊 Show Heatmap (显示库存热力图)", type="secondary"):
        st.session_state['show_heatmap'] = True
        st.rerun()

# 渲染热力图逻辑
if st.session_state.get('show_heatmap', False):
    st.divider()
    
    # 处理日期范围
    check_start, check_end = None, None
    if isinstance(check_range, tuple):
        if len(check_range) == 2:
            check_start, check_end = check_range
        elif len(check_range) == 1:
            check_start = check_range[0]
            check_end = check_range[0]
    
    if check_start and check_end:
        with st.spinner(f"Scanning Database from {check_start} to {check_end}..."):
            # 调用 utils 里的智能检查函数
            coverage_df = utils.check_data_coverage(
                final_hs, 
                str(check_start), 
                str(check_end), 
                origin_codes=dl_origins, 
                dest_codes=dl_dests, 
                target_species_list=dl_species
            )
            
            if not coverage_df.empty:
                # 补全日期确保图表连续
                full_range = pd.date_range(start=check_start, end=check_end)
                full_df = pd.DataFrame({'date': full_range}).merge(coverage_df, on='date', how='left').fillna(0)
                
                # 渲染图表
                fig = px.scatter(
                    full_df, x="date", y=[1]*len(full_df), 
                    size="count", color="count", 
                    color_continuous_scale=["#e0e0e0", "green"], 
                    title=f"Stock Heatmap ({check_start} ~ {check_end}) | Total: {int(coverage_df['count'].sum())} records", 
                    height=250
                )
                fig.update_yaxes(visible=False, showticklabels=False)
                fig.update_layout(plot_bgcolor='white', xaxis=dict(showgrid=False))
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning(f"⚠️ No Data found between {check_start} and {check_end} (该时间段无数据)")
    else:
        st.error("请选择完整的起始和结束日期")
    
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
                    # 显示具体的错误信息
                    error_msg = res.get('msg', 'Unknown Error') if res else 'No Response'
                    error_code = res.get('code', 'N/A') if res else 'N/A'
                    results.append({"HS Code": hs, "Flow": d, "API Count": f"Err {error_code}: {error_msg}"})
                    
        status.update(label="Complete (完成)", state="complete")
        if results:
            st.table(pd.DataFrame(results))
            if total_count > 0: st.success(f"✅ Total found on API: {total_count} records.")

# --- 3. 执行下载 (包含断点续传逻辑) ---
st.markdown("#### 3️⃣ Execute Download (执行下载)")

c_exec1, c_exec2 = st.columns([1, 4])
with c_exec1:
    start_page_val = st.number_input("Start Page (起始页码)", min_value=1, value=1, help="用于断点续传。")
with c_exec2:
    st.write("") 
    st.write("") 
    start_btn = st.button("🚀 Start Download (开始下载 - 自动翻页)", type="primary")

if start_btn:
    with st.status("Downloading... (下载中)", expanded=True) as status:
        if not token: status.update(label="Auth Failed (认证失败)", state="error"); st.stop()
        progress_bar = st.progress(0); log_box = st.expander("Process Log (运行日志)", expanded=True)
        total_ops = len(final_hs) * len(final_dirs); current_op = 0; stats = {"saved": 0}
        
        for hs in final_hs:
            for d in final_dirs:
                current_op += 1; progress_bar.progress(int(current_op/total_ops*100))
                
                page = start_page_val
                if page > 1:
                    log_box.info(f"⏭️ Resuming {hs} ({d}) from Page {page}...")
                
                has_more_data = True
                total_saved_for_this_hs = 0
                
                while has_more_data:
                    res = utils.fetch_tendata_api(hs, dl_date_range[0], dl_date_range[1], token, d, dl_origins, dl_dests, just_checking=False, page_no=page, keyword=api_keyword_str)
                    if res and str(res.get('code')) == '200':
                        saved_count, api_count = utils.save_to_supabase(res) # 调用 utils
                        total_saved_for_this_hs += saved_count
                        stats['saved'] += saved_count
                        log_box.write(f"🔄 HS {hs} ({d}) - P{page}: Fetched {api_count} records")
                        if api_count < 50: has_more_data = False
                        else: page += 1; time.sleep(0.3)
                    else:
                        err_msg = res.get('msg', 'Unknown') if res else 'No Resp'
                        log_box.error(f"HS {hs}: Error - {err_msg}"); has_more_data = False
                
                if total_saved_for_this_hs > 0: log_box.success(f"✅ HS {hs} ({d}) Done: Saved {total_saved_for_this_hs}")
                else: log_box.warning(f"HS {hs} ({d}): No Data")
        
        status.update(label="All Done (全部完成)", state="complete")
        st.success(f"🎉 Total Saved (累计入库): {stats['saved']} records")