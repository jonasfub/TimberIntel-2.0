import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
from supabase import create_client, Client
import config  # 引用 config.py

import os
import pathlib
import tomllib

# --- 核心配置 ---
# 从 .streamlit/secrets.toml 或环境变量读取密钥，避免明文上传 GitHub 导致密钥被自动吊销
def _load_secret(key_name, default=""):
    if key_name in os.environ:
        return os.environ[key_name]
    secrets_path = pathlib.Path(__file__).resolve().parent / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            with open(secrets_path, "rb") as f:
                data = tomllib.load(f)
                if key_name in data:
                    return data[key_name]
        except Exception:
            pass
    try:
        if key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
    return default

SUPABASE_URL = _load_secret("SUPABASE_URL", "https://ajfmhcustdzdmcbgowgx.supabase.co")
SUPABASE_KEY = _load_secret("SUPABASE_KEY", "")
TENDATA_API_KEY = _load_secret("TENDATA_API_KEY", "42127b0db5597b4a0d7063b99900c0eb")

# ✅ 新增：账户信息查询接口 (用于获取余额和会员有效期)
ACCOUNT_INFO_URL = "https://open-api.tendata.cn/v2/account"

# --- 1. 数据库连接 (使用缓存，避免重复连接) ---
@st.cache_resource
def init_supabase(url: str = SUPABASE_URL, key: str = SUPABASE_KEY):
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ 数据库连接失败: {e}")
        return None

supabase = init_supabase(SUPABASE_URL, SUPABASE_KEY)

# --- 2. 自动 Token 管理 ---
def get_auto_token(force_refresh=False):
    """
    获取访问 Token (Access Token)。
    修复说明：只负责获取 Token 和临时有效期 (7200s)，不再强制获取余额。
    :param force_refresh: 如果为 True，将忽略缓存，强制向 API 请求新 Token
    """
    # 1. 缓存检查
    if not force_refresh and 'access_token' in st.session_state and 'token_expiry' in st.session_state:
        if time.time() < st.session_state['token_expiry']:
            return st.session_state['access_token']

    # --- 请求新 Token ---
    auth_url = "https://open-api.tendata.cn/v2/access-token" 
    params = { "apiKey": TENDATA_API_KEY }
    
    try:
        res = requests.get(auth_url, params=params)
        res_json = res.json()
        
        # 检查是否成功 (Code 200)
        if str(res_json.get('code')) == '200':
            data = res_json.get('data', {})
            new_token = data.get('accessToken')
            
            # --- 有效期解析 ---
            # API 返回的是 expiresIn: 7200 (秒)
            expires_in_seconds = data.get('expiresIn', 7200)
            
            # 兼容性处理：如果返回的是字符串且是数字
            if isinstance(expires_in_seconds, str) and expires_in_seconds.isdigit():
                expires_in_seconds = int(expires_in_seconds)
            
            # 存入 Session
            st.session_state['access_token'] = new_token
            # 设置本地过期时间 (当前时间 + 有效期秒数 - 60秒缓冲)
            st.session_state['token_expiry'] = time.time() + expires_in_seconds - 60 
            
            return new_token
        else:
            st.error(f"🔐 自动登录失败: {res_json}")
            if 'access_token' in st.session_state: del st.session_state['access_token']
            return None
    except Exception as e:
        st.error(f"🔐 认证网络错误: {e}")
        return None

# --- 3. 新增：获取账户详细信息 ---
def get_remote_account_info(token):
    """
    使用 Token 查询真实的账户余额和会员有效期。
    调用接口: /v2/account
    """
    if not token: return None
        
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # 发送 GET 请求
        res = requests.get(ACCOUNT_INFO_URL, headers=headers)
        res_json = res.json()
        
        # print(f"💰 [DEBUG] Account Info Response: {res_json}") # 调试用
        
        if str(res_json.get('code')) == '200':
            # 返回 data 数据块，里面包含 balance, expireTime 等
            return res_json.get('data', {})
        else:
            # 如果 Token 过期等原因导致失败，不报错，只返回 None
            return None
            
    except Exception as e:
        st.error(f"❌ 账户查询网络错误: {e}")
        return None

# --- 4. 业务逻辑函数 ---

def identify_species(description_text):
    if not description_text: return "Unknown"
    desc_upper = str(description_text).upper()
    for species, keywords in config.SPECIES_KEYWORDS.items():
        for keyword in keywords:
            if keyword in desc_upper:
                return species
    return "Other"

# 提单特定数据源与 ISO 国家代码映射表 (用于补全如美单进口缺失的 dest_country_code)
SPECIFIC_COUNTRY_ISO_MAP = {
    "america": "USA", "usa": "USA",
    "india": "IND", "vietnam": "VNM",
    "new_zealand": "NZL", "nzl": "NZL",
    "australia": "AUS", "aus": "AUS",
    "mexico": "MEX", "chile": "CHL",
    "brazil": "BRA",
    "panama": "PAN", "peru": "PER",
    "pakistan": "PAK", "turkey": "TUR", "philippines": "PHL"
}

def fetch_tendata_api(hs_code, start_date, end_date, token, trade_type="imports", origin_codes=None, dest_codes=None, just_checking=False, page_no=1, keyword=None, specific_country=None, retry_count=0):
    """获取数据，支持海关关单 (/v2/trade) 与海运提单/指定数据源 (/v2/trade/specific)"""
    if specific_country:
        url = "https://open-api.tendata.cn/v2/trade/specific"
    else:
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
    if specific_country:
        payload['country'] = str(specific_country).strip().lower()
    if origin_codes: payload['countryOfOriginCode'] = ";".join(origin_codes)
    if dest_codes: payload['countryOfDestinationCode'] = ";".join(dest_codes)
    
    if keyword:
        payload['goodsDesc'] = keyword   
        payload['keyword'] = keyword      
        payload['productDesc'] = keyword  
        payload['desc'] = keyword         
        
        if just_checking and retry_count == 0:
            try:
                st.toast(f"📡 发送筛选词: {keyword}", icon="🔍")
            except:
                pass

    try:
        response = requests.post(url, headers=headers, json=payload)
        res_json = response.json()
        
        # 🔥 检测 40302 Token 无效错误并自动重试
        if str(res_json.get('code')) == '40302':
            if retry_count < 1: # 只重试一次
                new_token = get_auto_token(force_refresh=True)
                if new_token:
                    return fetch_tendata_api(
                        hs_code, start_date, end_date, 
                        new_token, 
                        trade_type, origin_codes, dest_codes, just_checking, page_no, keyword, 
                        specific_country=specific_country,
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
        
        origin_code = item.get('countryOfOriginCode')
        dest_code = item.get('countryOfDestinationCode')
        db_source = str(item.get('database', '')).lower()
        catalog_flow = str(item.get('catalog', 'imports')).lower()

        # 提单数据源自动补全对应国别码 (如美国进口提单自身无 dest_code，自动填充 USA)
        if db_source in SPECIFIC_COUNTRY_ISO_MAP:
            mapped_iso = SPECIFIC_COUNTRY_ISO_MAP[db_source]
            if catalog_flow == 'imports' and not dest_code:
                dest_code = mapped_iso
            elif catalog_flow == 'exports' and not origin_code:
                origin_code = mapped_iso

        row = {
            "unique_record_id": item.get('id'),
            "transaction_date": item.get('date'),
            "hs_code": hs_code_val,
            "product_desc_text": goods_desc_str,
            "origin_country_code": origin_code,
            "dest_country_code": dest_code,
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

# --- 5. 库存检查函数 ---
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
            
        # --- 3. 智能限流 ---
        if is_filtering_country:
            query = query.limit(20000)
        else:
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

# --- 6. 辅助 UI 函数 ---
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
    if rc3.button("澳新 (OC)", key=f"btn_oc_{target_key}"): add_region_codes(config.REGION_OCEANIA)
    if rc4.button("北美 (NA)", key=f"btn_na_{target_key}"): add_region_codes(config.REGION_NORTH_AMERICA)
    if rc5.button("南美 (SA)", key=f"btn_sa_{target_key}"): add_region_codes(config.REGION_SOUTH_AMERICA)
    if rc6.button("🗑️ 清空", key=f"btn_cls_{target_key}"):
        st.session_state[target_key] = []
        st.rerun()