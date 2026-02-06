import streamlit as st
import utils
import pandas as pd
from datetime import datetime

# --- 页面配置 ---
st.set_page_config(page_title="Account Info", page_icon="💳", layout="centered")

st.title("💳 API Account Status - 账户状态")
st.caption("实时查看 Tendata API 的剩余点数和授权有效期。")

st.divider()

# --- 刷新逻辑 ---
col_info, col_btn = st.columns([3, 1])
with col_info:
    st.info("💡 提示：Token 和余额信息默认在本地缓存 1 小时。如刚充值，请点击右侧按钮刷新。")
with col_btn:
    if st.button("🔄 强制刷新 (Refresh)", type="primary", use_container_width=True):
        # 清除缓存，强制 utils 重新请求 API
        if 'token_expiry' in st.session_state:
            del st.session_state['token_expiry']
        # 重新运行脚本，触发下方的 get_auto_token
        st.rerun()

# --- 获取数据 ---
# 调用 utils 获取 Token，这会自动触发 API 请求并更新 Session 中的余额信息
token = utils.get_auto_token()

if token:
    # 从 Session State 提取数据 (由 utils.py 注入)
    balance = st.session_state.get('api_balance', 0)
    expires_str = st.session_state.get('api_expires_str', 'Unknown')
    
    # --- 🎨 漂亮的指标卡片 ---
    st.markdown("### 📊 核心指标")
    
    # 使用容器加边框美化
    with st.container():
        c1, c2 = st.columns(2)
        
        with c1:
            # 余额卡片
            st.metric(
                label="💰 剩余点数 (Balance)", 
                value=f"{balance:,}", # 自动加千分位逗号 (e.g. 5,678)
                delta="Available",
                delta_color="normal"
            )
            
        with c2:
            # 有效期卡片
            days_left_str = "Unknown"
            delta_color = "normal"
            
            # 尝试计算剩余天数
            if expires_str != 'Unknown':
                try:
                    exp_date = datetime.strptime(str(expires_str), "%Y-%m-%d %H:%M:%S")
                    days_left = (exp_date - datetime.now()).days
                    
                    if days_left < 0:
                        days_left_str = "已过期 (Expired)"
                        delta_color = "inverse"
                    else:
                        days_left_str = f"剩 {days_left} 天 (Days Left)"
                        if days_left < 30: delta_color = "inverse" # 少于30天变红
                except Exception:
                    pass

            st.metric(
                label="📅 授权有效期 (Expires In)", 
                value=str(expires_str),
                delta=days_left_str,
                delta_color=delta_color
            )

    st.divider()

    # --- 📝 详细状态表 ---
    st.subheader("🔍 详细信息 (Details)")
    
    # 构造状态数据
    status_data = [
        {"指标 (Metric)": "API Key 状态", "状态 (Status)": "✅ Active (已激活)"},
        {"指标 (Metric)": "当前 Token", "状态 (Status)": f"{token[:10]}...{token[-5:]} (已隐藏)"},
        {"指标 (Metric)": "数据源接口", "状态 (Status)": "OpenAPI v2 (Tendata)"},
        {"指标 (Metric)": "上次更新时间", "状态 (Status)": datetime.now().strftime("%H:%M:%S")}
    ]
    
    df_status = pd.DataFrame(status_data)
    st.table(df_status)
    
    # --- ⚠️ 余额预警逻辑 ---
    if isinstance(balance, (int, float)):
        if balance <= 0:
            st.error("⛔ 错误：您的 API 点数已耗尽 (0)，无法继续请求数据。")
        elif balance < 5000:
            st.warning("⚠️ 警告：您的 API 点数已不足 5,000，请及时充值以免影响使用。")
        else:
            st.success("✅ 账户资金充足，API 运行正常。")

else:
    st.error("❌ 无法获取账户信息，请检查 utils.py 中的 API Key 配置或网络连接。")