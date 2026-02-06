import streamlit as st
import utils
import pandas as pd
from datetime import datetime

# --- 页面配置 ---
st.set_page_config(page_title="Account Info", page_icon="💳", layout="centered")

st.title("💳 API Account Status - 账户状态")
st.caption("实时查看 Tendata API 的剩余点数和会员有效期。")

st.divider()

# --- 刷新逻辑 ---
col_info, col_btn = st.columns([3, 1])
with col_info:
    st.info("💡 提示：点击刷新将请求 `/v2/account` 接口获取最新数据。")
with col_btn:
    if st.button("🔄 强制刷新 (Refresh)", type="primary", use_container_width=True):
        # 清除缓存
        if 'token_expiry' in st.session_state: del st.session_state['token_expiry']
        if 'account_data_cache' in st.session_state: del st.session_state['account_data_cache']
        st.rerun()

# --- 1. 获取 Token (登录) ---
token = utils.get_auto_token()

if token:
    # --- 2. 获取账户详情 (余额) ---
    # 使用 Session 缓存避免每次切页面都请求，除非强制刷新
    if 'account_data_cache' not in st.session_state:
        with st.spinner("📡 正在同步账户信息..."):
            st.session_state['account_data_cache'] = utils.get_remote_account_info(token)
    
    account_data = st.session_state['account_data_cache']

    # --- 3. 解析数据 ---
    # 默认值
    real_balance = "Unknown"
    real_expiry = "Unknown"
    
    if account_data:
        # 尝试自动寻找可能的字段名 (Tendata 常见的字段名)
        # 余额字段可能叫: balance, money, points, surplus
        real_balance = account_data.get('balance', 
                       account_data.get('money', 
                       account_data.get('points', '未找到余额字段')))
                       
        # 有效期字段可能叫: expireTime, vipExpireDate, endDate, serviceEndTime
        real_expiry = account_data.get('expireTime', 
                      account_data.get('vipExpireDate', 
                      account_data.get('serviceEndTime', '未找到日期字段')))

    # --- 4. 核心指标展示 ---
    st.markdown("### 📊 账户核心指标")
    
    with st.container():
        c1, c2 = st.columns(2)
        
        with c1:
            # 余额显示处理
            val_display = str(real_balance)
            if isinstance(real_balance, (int, float)):
                val_display = f"{real_balance:,}" # 加千分位
            
            st.metric(
                label="💰 剩余点数 (Balance)", 
                value=val_display, 
                delta="服务端实时数据" if account_data else "获取失败",
                delta_color="normal" if account_data else "off"
            )
            
        with c2:
            # 有效期显示处理
            days_str = ""
            delta_col = "off"
            
            # 尝试计算剩余天数
            try:
                # 假设格式是 "2025-xx-xx" 或 "2025-xx-xx HH:mm:ss"
                if real_expiry and str(real_expiry) != 'Unknown':
                    exp_date_str = str(real_expiry)
                    # 简单的格式清洗
                    if len(exp_date_str) > 19: exp_date_str = exp_date_str[:19]
                    
                    try:
                        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d") # 备选格式
                        
                    days = (exp_date - datetime.now()).days
                    days_str = f"剩 {days} 天"
                    if days < 30: delta_col = "inverse"
                    else: delta_col = "normal"
            except:
                pass

            st.metric(
                label="📅 会员到期时间 (Expires)", 
                value=str(real_expiry),
                delta=days_str,
                delta_color=delta_col
            )

    st.divider()

    # --- 5. 调试：展示原始 JSON ---
    # 这非常重要，因为我们还不知道字段的确切名称
    st.subheader("🔍 原始 API 响应数据")
    st.caption("如果上面的余额显示不正确，请查看下方的 JSON 数据，确认正确的字段名。")
    
    if account_data:
        st.json(account_data)
    else:
        st.warning("⚠️ 未能获取到账户数据，请检查 utils.py 中的 ACCOUNT_INFO_URL 配置。")
        
    # --- 6. 状态表 ---
    with st.expander("查看连接详情"):
        status_data = [
            {"Item": "Token 状态", "Value": "✅ Active"},
            {"Item": "Token 预览", "Value": f"{token[:15]}..."},
            {"Item": "API 接口", "Value": utils.ACCOUNT_INFO_URL},
            {"Item": "更新时间", "Value": datetime.now().strftime("%H:%M:%S")}
        ]
        st.table(pd.DataFrame(status_data))

else:
    st.error("❌ 无法登录 (Access Token 获取失败)，请检查 API Key 配置。")