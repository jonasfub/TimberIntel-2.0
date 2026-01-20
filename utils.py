# utils.py 中的 check_data_coverage 函数

def check_data_coverage(target_hs_codes, check_start_date, check_end_date, origin_codes=None, dest_codes=None, target_species_list=None):
    if not supabase: return pd.DataFrame()
    try:
        # --- 1. 智能列选择 ---
        # 对于库存检查，我们只需要日期和HS编码。
        # 除非必须筛选树种，否则绝不请求 product_desc_text (大文本字段)
        select_cols = "transaction_date, hs_code"
        needs_text_filter = target_species_list and len(target_species_list) > 0
        
        # 如果是印度，强制关闭文本字段查询 (防止传输超时)
        is_heavy_country = origin_codes and ('IND' in origin_codes)
        
        if needs_text_filter and not is_heavy_country:
            select_cols += ", product_desc_text"

        # --- 2. 构建查询 ---
        query = supabase.table('trade_records')\
            .select(select_cols)\
            .gte('transaction_date', check_start_date)\
            .lte('transaction_date', check_end_date)\
            .order("transaction_date", desc=True)
            
        # [核心优化] 针对印度启用“极速模式”
        if is_heavy_country:
            # 印度数据量太大，10万条排序会超时。
            # 降级为 15,000 条，足够看清最近是否有库存。
            query = query.limit(15000)
            if needs_text_filter:
                st.toast("⚠️ 印度数据量过大，已自动关闭树种关键词筛选以加速库存检查。", icon="🚀")
                # 印度模式下，强制不查文本，防止卡死
                needs_text_filter = False 
        else:
            # 其他国家保持 10万条，保证样本丰富度
            query = query.limit(100000)
            
        if origin_codes: query = query.in_('origin_country_code', origin_codes)
        if dest_codes: query = query.in_('dest_country_code', dest_codes)
        
        # 执行查询
        response = query.execute()
        rows = response.data
        if not rows: return pd.DataFrame()
        
        df = pd.DataFrame(rows)
        
        # 3. Python 端过滤 HS Code
        df['hs_str'] = df['hs_code'].astype(str)
        df['match_hs'] = df['hs_str'].apply(lambda x: any(x.startswith(str(t)) for t in target_hs_codes))
        df = df[df['match_hs']]
        
        if df.empty: return pd.DataFrame()
        
        # 4. 如果需要，过滤树种
        if needs_text_filter and 'product_desc_text' in df.columns:
            df['Species'] = df['product_desc_text'].apply(identify_species)
            df = df[df['Species'].isin(target_species_list)]
            if df.empty: return pd.DataFrame()

        # 5. 聚合统计
        daily_counts = df['transaction_date'].value_counts().reset_index()
        daily_counts.columns = ['date', 'count']
        daily_counts['date'] = pd.to_datetime(daily_counts['date'])
        return daily_counts

    except Exception as e:
        st.error(f"⚠️ Check Logic Error: {str(e)}")
        return pd.DataFrame()