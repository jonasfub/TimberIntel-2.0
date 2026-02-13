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
    st.info("💡 提示：数据直接来自 Tendata `/v2/account` 接口。")
with col_btn:
    if st.button("🔄 刷新数据 (Refresh)", type="primary", use_container_width=True):
        # 清除缓存
        if 'token_expiry' in st.session_state: del st.session_state['token_expiry']
        if 'account_data_cache' in st.session_state: del st.session_state['account_data_cache']
        st.rerun()

# --- 1. 获取 Token (登录) ---
token = utils.get_auto_token()

if token:
    # --- 2. 获取账户详情 (余额) ---
    if 'account_data_cache' not in st.session_state:
        with st.spinner("📡 正在同步最新账户信息..."):
            st.session_state['account_data_cache'] = utils.get_remote_account_info(token)
    
    account_data = st.session_state['account_data_cache']

    # --- 3. 解析数据 (精准匹配) ---
    real_balance = "Unknown"
    real_expiry = "Unknown"
    
    if account_data:
        # ✅ 修复：直接读取 'balance' 和 'expiresIn'
        real_balance = account_data.get('balance', '0')
        real_expiry = account_data.get('expiresIn', 'Unknown')

    # --- 4. 核心指标展示 ---
    st.markdown("### 📊 账户核心指标")
    
    with st.container():
        c1, c2 = st.columns(2)
        
        with c1:
            # --- 余额美化处理 ---
            val_display = str(real_balance)
            
            # 尝试把字符串数字转成带逗号的格式 (例如 "3536108" -> "3,536,108")
            if val_display.isdigit():
                val_display = f"{int(val_display):,}"
            elif isinstance(real_balance, (int, float)):
                val_display = f"{real_balance:,}"
            
            st.metric(
                label="💰 剩余点数 (Balance)", 
                value=val_display, 
                delta="服务端实时数据",
                delta_color="normal"
            )
            
        with c2:
            # --- 有效期美化处理 ---
            days_str = ""
            delta_col = "off"
            
            # 尝试计算剩余天数
            try:
                if real_expiry and str(real_expiry) != 'Unknown':
                    exp_date_str = str(real_expiry)
                    # 格式清洗: 只取前19位 "2028-01-16 23:59:59"
                    if len(exp_date_str) > 19: exp_date_str = exp_date_str[:19]
                    
                    try:
                        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d %H:%M:%S")
                    except:
                        exp_date = datetime.strptime(exp_date_str, "%Y-%m-%d")
                        
                    days = (exp_date - datetime.now()).days
                    
                    if days < 0:
                        days_str = "已过期"
                        delta_col = "inverse"
                    else:
                        days_str = f"剩 {days} 天"
                        if days < 30: delta_col = "inverse" # 少于30天变红
                        else: delta_col = "normal"          # 正常显示
            except:
                pass

            st.metric(
                label="📅 会员到期时间 (Expires)", 
                value=str(real_expiry),
                delta=days_str,
                delta_color=delta_col
            )

    st.divider()

    # --- 5. 底部折叠信息 (保持页面整洁) ---
    with st.expander("🔍 查看技术详情 (Debug Info)"):
        st.caption("原始 API 响应数据：")
        st.json(account_data) # 把 JSON 藏在这里，需要时再看
        
        st.markdown("---")
        status_data = [
            {"Item": "Token 状态", "Value": "✅ Active"},
            {"Item": "Token 预览", "Value": f"{token[:15]}..."},
            {"Item": "数据源接口", "Value": utils.ACCOUNT_INFO_URL},
            {"Item": "本地更新时间", "Value": datetime.now().strftime("%H:%M:%S")}
        ]
        st.table(pd.DataFrame(status_data))

else:
    st.error("❌ 无法登录 (Access Token 获取失败)，请检查 API Key 配置。")