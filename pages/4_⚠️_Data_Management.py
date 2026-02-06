import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import config
import utils

# --- 页面配置 ---
st.set_page_config(page_title="Data Management", page_icon="🗑️", layout="wide")

st.title("🗑️ Data Management - 数据管理工具")
st.markdown("""
<div style="background-color:#ffe6e6; padding:15px; border-radius:10px; border:1px solid #ff4d4d; margin-bottom: 20px;">
    <h4 style="color:#cc0000; margin:0;">⚠️ 警告：高风险区域 (DANGER ZONE)</h4>
    <p style="color:#cc0000; margin:5px 0 0 0;">
        此页面执行的是<b>物理删除</b>操作，数据一旦删除将<b>无法恢复</b>！<br>
        请务必先点击“🔍 扫描数据”确认筛选范围是否正确。
    </p>
</div>
""", unsafe_allow_html=True)

# --- 1. 筛选条件区域 ---
st.subheader("1️⃣ 定义删除范围 (Define Scope)")

c1, c2 = st.columns(2)
with c1:
    # 地区筛选
    all_codes = utils.get_all_country_codes()
    del_origins = st.multiselect("出口国 (Origin)", all_codes, format_func=utils.country_format_func, help="留空表示不限制出口国（匹配所有）")
    del_dests = st.multiselect("进口国 (Dest)", all_codes, format_func=utils.country_format_func, help="留空表示不限制进口国（匹配所有）")

with c2:
    # 产品与时间
    # 获取所有 HS Codes
    all_hs_flat = []
    for cat, codes in config.HS_CODES_MAP.items():
        all_hs_flat.extend(codes)
    all_hs_flat = sorted(list(set(all_hs_flat)))
    
    del_hs_codes = st.multiselect("HS Codes / 产品", all_hs_flat, help="留空表示不限制产品（匹配所有 HS Code）")
    
    # 日期范围 (用于月份删除)
    del_date_range = st.date_input(
        "日期范围 (Date Range)", 
        value=(datetime.today() - timedelta(days=30), datetime.today()),
        help="选择你要删除的时间段 (例如: 选中 1月1日 到 1月31日 即可删除整个一月)"
    )

# 简单的逻辑检查
start_d, end_d = None, None
if isinstance(del_date_range, tuple) and len(del_date_range) == 2:
    start_d, end_d = del_date_range

st.divider()

# --- 2. 扫描与预览 ---
st.subheader("2️⃣ 扫描与确认 (Scan & Confirm)")

# 初始化 Session State 用于存储待删除的数量
if 'delete_preview_count' not in st.session_state:
    st.session_state['delete_preview_count'] = 0
if 'delete_ready' not in st.session_state:
    st.session_state['delete_ready'] = False

# 构建查询条件的辅助函数
def build_query(base_query):
    # 时间必须有
    if start_d and end_d:
        base_query = base_query.gte('transaction_date', start_d).lte('transaction_date', end_d)
    
    # 可选条件
    if del_origins:
        base_query = base_query.in_('origin_country_code', del_origins)
    if del_dests:
        base_query = base_query.in_('dest_country_code', del_dests)
    if del_hs_codes:
        base_query = base_query.in_('hs_code', del_hs_codes)
    
    return base_query

# 扫描按钮
col_scan, col_info = st.columns([1, 3])
with col_scan:
    if st.button("🔍 扫描匹配数据 (Scan)", type="primary", use_container_width=True):
        if not (start_d and end_d):
            st.error("请先选择完整的日期范围")
        else:
            with st.spinner("正在扫描数据库..."):
                try:
                    # 使用 count='exact', head=True 只获取数量不获取内容，速度快
                    query = utils.supabase.table('trade_records').select("*", count='exact', head=True)
                    query = build_query(query)
                    response = query.execute()
                    
                    count = response.count
                    st.session_state['delete_preview_count'] = count
                    st.session_state['delete_ready'] = True
                    
                    if count == 0:
                        st.warning("未找到匹配的数据 (0 条)")
                        st.session_state['delete_ready'] = False
                    else:
                        st.success(f"✅ 扫描完成")
                
                except Exception as e:
                    st.error(f"扫描出错: {e}")

# 显示扫描结果
with col_info:
    if st.session_state.get('delete_ready'):
        count = st.session_state['delete_preview_count']
        st.markdown(f"### 🎯 匹配记录数: **{count}** 条")
        
        # 生成人类可读的摘要
        summary = []
        if del_origins: summary.append(f"出口国: {', '.join(del_origins)}")
        else: summary.append("出口国: 全部")
        
        if del_dests: summary.append(f"进口国: {', '.join(del_dests)}")
        else: summary.append("进口国: 全部")
        
        if del_hs_codes: summary.append(f"HS Codes: {len(del_hs_codes)} 个")
        else: summary.append("HS Codes: 全部")
        
        summary.append(f"时间段: {start_d} 至 {end_d}")
        
        st.info(" | ".join(summary))

st.divider()

# --- 3. 执行删除 ---
st.subheader("3️⃣ 执行删除 (Execute Delete)")

if st.session_state.get('delete_ready') and st.session_state['delete_preview_count'] > 0:
    
    with st.form("delete_form"):
        confirm_check = st.checkbox("🚩 我已知晓操作不可逆，并确认删除上述所有数据")
        
        # 红色删除按钮
        submit_del = st.form_submit_button("❌ 立即删除 (Delete Now)", type="secondary")
        
        if submit_del:
            if not confirm_check:
                st.error("请先勾选确认框！")
            else:
                try:
                    with st.spinner("🗑️ 正在执行物理删除..."):
                        # 构建删除查询
                        query = utils.supabase.table('trade_records').delete()
                        query = build_query(query)
                        
                        # 执行删除
                        # 注意：Supabase delete 操作返回的是被删除的数据列表
                        response = query.execute()
                        
                        deleted_data = response.data
                        deleted_count = len(deleted_data) if deleted_data else 0
                        
                        # 实际上 Supabase 有时对于大量删除不会返回所有 data，但操作是成功的
                        # 如果是大量删除，可能需要依赖之前的 count
                        
                        st.success(f"✅ 删除成功！")
                        st.markdown(f"**操作反馈:** 数据库响应已清理相关记录。")
                        
                        # 重置状态
                        st.session_state['delete_ready'] = False
                        st.session_state['delete_preview_count'] = 0
                        
                except Exception as e:
                    st.error(f"❌ 删除失败: {e}")
else:
    st.caption("请先完成步骤 2 (扫描数据) 以解锁删除功能。")