import streamlit as st
import pandas as pd
import requests
import time
from supabase import create_client, Client
import config  # 引用你的配置

# --- 核心配置 ---
# ⚠️ 请确保这里的 URL 和 Key 是正确的
SUPABASE_URL = "https://ajfmhcustdzdmcbgowgx.supabase.co"
SUPABASE_KEY = "sb_secret_UdSZUH99OqFQ0Irca_LUWg_a7Sp-j_7"
TENDATA_API_KEY = "42127b0db5597b4a0d7063b99900c0eb"

# --- 1. 数据库连接 (使用缓存，避免重复连接) ---
@st.cache_resource
def init_supabase():
    try:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None

supabase = init_supabase()

# --- 2. 自动 Token 管理 (包含自动刷新逻辑) ---
def get_auto_token(force_refresh=False):
    """
    获取 Token。
    :param force_refresh: 如果为 True，将忽略缓存，强制向 API 请求新 Token
    """
    # 如果不是强制刷新，且 Session 中有不过期的 Token，直接返回
    if not force_refresh and 'access_token' in st.session_state and 'token_expiry' in st.session_state:
        # 预留 60 秒缓冲期
        if time.time() < st.session_state['token_expiry']:
            return st.session_state['access_token']

    # --- 请求新 Token ---
    auth_url = "https://open-api.tendata.cn/v2/access-token" 
    params = { "apiKey": TENDATA_API_KEY }
    
    try:
        res = requests.get(auth_url, params=params)
        res_json = res.json()
        if str(res_json.get('code')) == '200':
            token_data = res_json.get('data', {})
            new_token = token_data.get('accessToken')
            expires_in = token_data.get('expiresIn', 7200)
            
            # 更新 Session State
            st.session_state['access_token'] = new_token
            st.session_state['token_expiry'] = time.time() + expires_in - 60 
            return new_token
        else:
            st.error(f"🔐 自动登录失败: {res_json}")
            # 如果失败，清除 Session 里的脏数据
            if 'access_token' in st.session_state: del st.session_state['access_token']
            return None
    except Exception as e:
        st.error(f"🔐 认证网络错误: {e}")
        return None

# --- 3. 业务逻辑函数 ---

def identify_species(description_text):
    if not description_text: return "Unknown"
    desc_upper = str(description_text).upper()
    for species, keywords in config.SPECIES_KEYWORDS.items():
        for keyword in keywords:
            if keyword in desc_upper:
                return species
    return "Other"

def fetch_tendata_api(hs_code, start_date, end_date, token, trade_type="imports", origin_codes=None, dest_codes=None, just_checking=False, page_no=1, keyword=None, retry_count=0):
    """获取数据，包含自动重试机制 (40302 Token失效自动修复)"""
    url = "https://open-api.tendata.cn/v2/trade"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    
    payload = {
        "pageNo": page_no, 
        "pageSize": 1 if just_checking else 100, 
        "catalog": trade_type,
        "startDate": str(start_date), 
        "endDate": str(end_date), 
        "hsCode": hs_code
    }
    if origin_codes: payload['countryOfOriginCode'] = ";".join(origin_codes)
    if dest_codes: payload['countryOfDestinationCode'] = ";".join(dest_codes)
    
    if keyword:
        payload['goodsDesc'] = keyword   
        payload['keyword'] = keyword      
        payload['productDesc'] = keyword  
        payload['desc'] = keyword         
        
        if just_checking and retry_count == 0:
            try:
                import streamlit as st
                st.toast(f"📡 发送筛选词: {keyword}", icon="🔍")
            except:
                pass

    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        # 🔥 检测 40302 Token 无效错误并自动重试
        if str(res_json.get('code')) == '40302':
            if retry_count < 1: # 只重试一次
                print(f"⚠️ Token Invalid (40302). Refreshing and Retrying... (HS: {hs_code})")
                new_token = get_auto_token(force_refresh=True)
                if new_token:
                    return fetch_tendata_api(
                        hs_code, start_date, end_date, 
                        new_token, 
                        trade_type, origin_codes, dest_codes, just_checking, page_no, keyword, 
                        retry_count=1
                    )
                else:
                    return {"code": 40302, "msg": "Token refresh failed"}
            else:
                return {"code": 40302, "msg": "Token invalid after retry"}

        return res_json

    except Exception as e:
        return {"code": 500, "msg": str(e)}


def save_to_supabase(api_json_data):
    if not supabase: return 0, 0
    data_node = api_json_data.get('data', {})
    records = data_node.get('content', []) if isinstance(data_node, dict) else []
    
    if not records: return 0, 0
    
    db_rows = []
    for item in records:
        hs_code_val = item.get('hsCode')[0] if item.get('hsCode') else None
        goods_desc_list = item.get('goodsDesc') or []
        goods_desc_str = "; ".join([str(x) for x in goods_desc_list])
        
        row = {
            "unique_record_id": item.get('id'),
            "transaction_date": item.get('date'),
            "hs_code": hs_code_val,
            "product_desc_text": goods_desc_str,
            "origin_country_code": item.get('countryOfOriginCode'),
            "dest_country_code": item.get('countryOfDestinationCode'),
            "port_of_departure": item.get('portOfDeparture'),
            "port_of_arrival": item.get('portOfArrival'),
            "importer_name": item.get('importer'),
            "exporter_name": item.get('exporter'),
            "quantity": item.get('quantity'),
            "quantity_unit": item.get('quantityUnit'),
            "total_value_usd": item.get('sumOfUsd'),
            "raw_data": item
        }
        db_rows.append(row)
    
    try:
        supabase.table('trade_records').upsert(db_rows, on_conflict='unique_record_id').execute()
        return len(db_rows), len(records)
    except Exception as e:
        st.error(f"Error saving DB: {e}")
        return 0, len(records)

# --- 4. 库存检查函数 (包含防超时优化) ---
def check_data_coverage(target_hs_codes, check_start_date, check_end_date, origin_codes=None, dest_codes=None, target_species_list=None):
    if not supabase: return pd.DataFrame()
    try:
        # --- 1. 智能列选择 ---
        select_cols = "transaction_date, hs_code"
        
        # 判断是否正在筛选特定国家
        is_filtering_country = (origin_codes is not None and len(origin_codes) > 0)
        
        # 判断是否需要文本筛选
        needs_text_filter = target_species_list and len(target_species_list) > 0
        
        # [优化策略]：如果正在筛选特定国家（如印度），为了速度和稳定性，牺牲文本字段扫描
        # 因为带 WHERE origin='IND' 的大文本扫描极易超时
        if needs_text_filter and is_filtering_country:
             needs_text_filter = False 
        
        if needs_text_filter:
            select_cols += ", product_desc_text"

        # --- 2. 构建查询 ---
        query = supabase.table('trade_records')\
            .select(select_cols)\
            .gte('transaction_date', check_start_date)\
            .lte('transaction_date', check_end_date)\
            .order("transaction_date", desc=True)
            
        # --- 3. 智能限流 (核心防超时) ---
        if is_filtering_country:
            # 筛选特定国家（如印度）：limit 降级为 2万条
            query = query.limit(20000)
        else:
            # 全选模式（不筛国家）：limit 保持 10万条（利用时间索引，速度快）
            query = query.limit(100000)
            
        if origin_codes: query = query.in_('origin_country_code', origin_codes)
        if dest_codes: query = query.in_('dest_country_code', dest_codes)
        
        # 执行查询
        response = query.execute()
        rows = response.data
        if not rows: return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # 4. Python 端过滤 HS Code
        df['hs_str'] = df['hs_code'].astype(str)
        df['match_hs'] = df['hs_str'].apply(lambda x: any(x.startswith(str(t)) for t in target_hs_codes))
        df = df[df['match_hs']]
        
        if df.empty: return pd.DataFrame()
        
        # 5. 过滤树种 (如果开启)
        if needs_text_filter and 'product_desc_text' in df.columns:
            df['Species'] = df['product_desc_text'].apply(identify_species)
            df = df[df['Species'].isin(target_species_list)]
            if df.empty: return pd.DataFrame()

        # 6. 聚合统计
        daily_counts = df['transaction_date'].value_counts().reset_index()
        daily_counts.columns = ['date', 'count']
        daily_counts['date'] = pd.to_datetime(daily_counts['date'])
        return daily_counts

    except Exception as e:
        # 捕获超时错误并友好提示
        err_str = str(e)
        if '57014' in err_str or 'timeout' in err_str.lower():
            st.error("⚠️ 查询超时：该国家数据量过大。系统已自动限制查询样本，请尝试缩短日期范围或联系管理员添加索引。")
        else:
            st.error(f"⚠️ Check Logic Error: {err_str}")
        return pd.DataFrame()

# --- 5. 辅助 UI 函数 ---
def country_format_func(code):
    name = config.COUNTRY_NAME_MAP.get(code, code)
    return f"{code} - {name}"

def get_all_country_codes():
    return sorted(list(set(
        [code for group in config.COUNTRY_GROUPS.values() for code in group] + 
        config.REGION_EUROPE_NO_RUS + 
        config.REGION_SOUTH_AMERICA + 
        config.REGION_ASIA_ALL
    )))

def render_region_buttons(target_key, col_obj):
    rc1, rc2, rc3, rc4, rc5, rc6 = col_obj.columns([1,1,1,1,1,1])
    current_selection = st.session_state.get(target_key, [])
    if not isinstance(current_selection, list): current_selection = []

    def add_region_codes(new_codes):
        merged_set = set(current_selection) | set(new_codes)
        st.session_state[target_key] = sorted(list(merged_set))
        st.rerun()

    if rc1.button("亚洲 (AS)", key=f"btn_as_{target_key}"): add_region_codes(config.REGION_ASIA_ALL)
    if rc2.button("欧洲 (EU)", key=f"btn_eu_{target_key}"): add_region_codes(config.REGION_EUROPE_NO_RUS)
    if rc3.button("🇦🇺 澳新", key=f"btn_oc_{target_key}"): add_region_codes(config.REGION_OCEANIA)
    if rc4.button("北美 (NA)", key=f"btn_na_{target_key}"): add_region_codes(config.REGION_NORTH_AMERICA)
    if rc5.button("南美 (SA)", key=f"btn_sa_{target_key}"): add_region_codes(config.REGION_SOUTH_AMERICA)
    if rc6.button("🗑️ 清空", key=f"btn_cls_{target_key}"):
        st.session_state[target_key] = []
        st.rerun()