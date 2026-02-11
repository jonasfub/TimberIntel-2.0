# config.py
# 更新时间：2026-01-19 (Vizag修正版)
# 修复内容：
# 1. 完善 Wood Chip 港口映射 (Vizag, Goa, Kakinada, Karaikal)
# 2. 确保坐标库 Key 与映射后的英文名一致

# ==========================================
# 1. HS Code 映射表 (严格区分软硬木)
# ==========================================
HS_CODES_MAP = {
    "Softwood Lumber": ["440710", "440711", "440712", "440713", "440714", "440719"],
    "Softwood Logs": ["440320", "440321", "440322", "440323", "440324", "440325", "440326"],
    "Hardwood Logs": ["440391", "440393", "440394", "440395", "440396", "440397", "440398", "440399", "440341", "440342", "440349"],
    "Hardwood Lumber": ["440791", "440792", "440793", "440794", "440795", "440796", "440797", "440799", "440721", "440722", "440723", "440725", "440726", "440727", "440728", "440729"],
    "Wood Chips": ["440121", "440122"],
    "Wood Pulp": ["4701", "4702", "4703", "4704", "4705", "4706"],
    "Recovered Paper": ["4707"],
    "Veneer (单板)": ["4408"],
    "Plywood (胶合板)": ["4412"],
    "MDF/HDF (纤维板)": ["4411"],
    "Particle Board (刨花板)": ["4410"],
    "Other Products": ["4404", "4405", "4406", "4409", "4413", "4414", "4415", "4416", "4417", "4418", "4419", "4420", "4421"]
}

# ==========================================
# 2. 树种关键词映射
# ==========================================
SPECIES_KEYWORDS = {
    "Radiata":    ["RADIATA", "RAD PINE", "MONTEREY", "INSIGNIS"],
    "SYP / Taeda": ["SOUTHERN YELLOW", "SYP", "S.Y.P", "SOUTHEN YELLOW", "SOUTERN YELLOW", "SOUHERN YELLOW", "TAEDA", "ELLIOTII", "LOBLOLLY", "SLASH PINE", "LONGLEAF", "SHORTLEAF", "CARIBAEA", "HONDURENSIS"],
    "Spruce":     ["SPRUCE", "PICEA", "WHITEWOOD", "SPF"],
    "Fir":        ["FIR ", "ABIES", "DOUGLAS", "HEMLOCK"],
    "Pine (Gen)": ["PINE", "PINUS"], 
    "Larch":      ["LARCH", "LARIX"],
    "Oak":        ["OAK", "QUERCUS", "RED OAK", "WHITE OAK"],
    "Birch":      ["BIRCH", "BETULA"],
    "Beech":      ["BEECH", "FAGUS"],
    "Poplar":     ["POPLAR", "POPULUS", "ASPEN", "COTTONWOOD"],
    "Eucalyptus": ["EUCALYPTUS", "EUCA", "GUM", "GRANDIS"],
    "Acacia":     ["ACACIA", "MANGIUM"],
    "Rubberwood": ["RUBBERWOOD", "HEVEA"],
    "Teak":       ["TEAK", "TECTONA"],
    "Ash":        ["ASH ", "FRAXINUS"],
    "Maple":      ["MAPLE", "ACER"],
    "Cherry":     ["CHERRY", "PRUNUS"],
    "Walnut":     ["WALNUT", "JUGLANS"],
    "Meranti":    ["MERANTI", "LAUAN", "SHOREA"]
}

# ==========================================
# 3. 快捷区域分组
# ==========================================
REGION_ASIA_ALL = ["CHN", "IND", "JPN", "KOR", "TWN", "VNM", "THA", "MYS", "KHM", "LKA", "IDN", "PHL", "ARE", "SAU"]
REGION_EUROPE_NO_RUS = ["DEU", "SWE", "FIN", "AUT", "BEL", "FRA", "ESP", "ITA", "POL", "LVA", "EST", "LTU", "CZE", "SVK", "ROU", "PRT", "IRL", "GBR", "NOR", "NLD", "SVN", "HRV", "DNK"]
REGION_AFRICA = ["ZAF", "MOZ", "GAB", "CMR", "COG", "GNQ", "GHA", "NGA", "TZA", "UGA", "KEN"]
REGION_OCEANIA = ["NZL", "AUS", "PNG"]
REGION_NORTH_AMERICA = ["USA", "CAN"]
REGION_SOUTH_AMERICA = ["BRA", "URY", "ARG", "CHL", "ECU", "SUR", "GUY"]
REGION_CENTRAL_AMERICA = ["CRI", "PAN", "GTM"]

COUNTRY_GROUPS = {
    "Markets_Main_Asia": ["CHN", "IND", "JPN", "KOR", "TWN"],
    "Markets_SE_Asia":   ["VNM", "THA", "MYS", "KHM", "LKA", "IDN", "PHL"],
    "Markets_MiddleEast":["ARE", "SAU"],
    "Sources_SE_Asia":   ["VNM", "THA", "IDN", "MYS"],
    "Sources_Africa":    REGION_AFRICA,
    "Sources_SouthAmerica":REGION_SOUTH_AMERICA,
    "Sources_CentralAmerica":REGION_CENTRAL_AMERICA,
    "Sources_Pulp_Majors":["NZL", "CAN", "SWE", "FIN", "USA", "BRA", "IDN", "CHL"],
    "Sources_Oceania":   ["NZL", "AUS"],
    "Sources_NorthAmerica":["USA", "CAN", "MEX"],
    "Sources_Europe":    ["RUS", "DEU", "SWE", "FIN"]
}

# ==========================================
# 4. 国家代码名称对照表
# ==========================================
COUNTRY_NAME_MAP = {
    "TZA": "Tanzania", "UGA": "Uganda", "KEN": "Kenya",
    "CRI": "Costa Rica", "PAN": "Panama", "ECU": "Ecuador", "GTM": "Guatemala",
    "CHN": "China", "IND": "India", "JPN": "Japan", "KOR": "South Korea", "TWN": "Taiwan",
    "VNM": "Vietnam", "THA": "Thailand", "MYS": "Malaysia", "KHM": "Cambodia", "LKA": "Sri Lanka",
    "ARE": "UAE", "SAU": "Saudi Arabia", "IDN": "Indonesia", "PHL": "Philippines",
    "ZAF": "South Africa", "MOZ": "Mozambique", "GAB": "Gabon", "CMR": "Cameroon", "COG": "Congo",
    "GNQ": "Eq. Guinea", "GHA": "Ghana", "NGA": "Nigeria",
    "BRA": "Brazil", "URY": "Uruguay", "ARG": "Argentina", "CHL": "Chile", "SUR": "Suriname", "GUY": "Guyana",
    "NZL": "New Zealand", "AUS": "Australia", "USA": "USA", "CAN": "Canada", "MEX": "Mexico",
    "RUS": "Russia", "DEU": "Germany", "SWE": "Sweden", "FIN": "Finland", "AUT": "Austria",
    "BEL": "Belgium", "FRA": "France", "ESP": "Spain", "ITA": "Italy", "POL": "Poland",
    "LVA": "Latvia", "EST": "Estonia", "LTU": "Lithuania", "CZE": "Czechia", "SVK": "Slovakia",
    "ROU": "Romania", "PRT": "Portugal", "IRL": "Ireland", "GBR": "UK", "NOR": "Norway",
    "NLD": "Netherlands", "SVN": "Slovenia", "HRV": "Croatia", "DNK": "Denmark"
}

# ==========================================
# 5. 港口经纬度映射表 (Key为标准英文名)
# ==========================================
PORT_COORDINATES = {
    # --- Wood Chip 关键港口 ---
    "KAKINADA": {"lat": 16.9604, "lon": 82.2381},
    "KARAIKAL": {"lat": 10.9254, "lon": 79.8380},
    "MORMUGAO (GOA)": {"lat": 15.4026, "lon": 73.8033}, # 标准名
    
    # --- 印度主要港口 ---
    "MUNDRA": {"lat": 22.8396, "lon": 69.7203},
    "NHAVA SHEVA": {"lat": 18.9511, "lon": 72.9567},
    "CHENNAI": {"lat": 13.0827, "lon": 80.2707},
    "VISAKHAPATNAM": {"lat": 17.6868, "lon": 83.2185}, # Vizag 标准名
    "COCHIN": {"lat": 9.9656, "lon": 76.2625},
    "COCHIN (ICTT)": {"lat": 10.1518, "lon": 76.4019},
    "KATTUPALLI": {"lat": 13.3069, "lon": 80.3392},
    "ENNORE": {"lat": 13.2667, "lon": 80.3333},
    "TUTICORIN": {"lat": 8.7642, "lon": 78.1348},
    "KANDLA": {"lat": 23.0768, "lon": 70.1343},
    "HAZIRA": {"lat": 21.0922, "lon": 72.6186},
    "KOLKATA": {"lat": 22.5478, "lon": 88.3182},
    "MUMBAI (AIR)": {"lat": 19.0886, "lon": 72.8680},
    
    # --- 其他区域 (保持原有) ---
    "MOMBASA": {"lat": -4.0547, "lon": 39.6636},
    "LAMU": {"lat": -2.2717, "lon": 40.9020},
    "DAR ES SALAAM": {"lat": -6.8235, "lon": 39.2695},
    "TANGA": {"lat": -5.0559, "lon": 39.1121},
    "ZANZIBAR": {"lat": -6.1629, "lon": 39.1919},
    "KAMPALA": {"lat": 0.3163, "lon": 32.5822}, 
    "JINJA": {"lat": 0.4244, "lon": 33.2042},
    "GUAYAQUIL": {"lat": -2.2885, "lon": -79.9167},
    "ESMERALDAS": {"lat": 0.9856, "lon": -79.6583},
    "PUERTO LIMON": {"lat": 9.9913, "lon": -83.0240},
    "MOIN": {"lat": 10.0000, "lon": -83.0786},
    "CALDERA": {"lat": 9.9136, "lon": -84.7176},
    "BALBOA": {"lat": 8.9565, "lon": -79.5663},
    "COLON": {"lat": 9.3596, "lon": -79.9001},
    "MANZANILLO": {"lat": 9.3639, "lon": -79.8804},
    "CRISTOBAL": {"lat": 9.3499, "lon": -79.9079},
    "PUERTO QUETZAL": {"lat": 13.9167, "lon": -90.7833},
    "SANTO TOMAS DE CASTILLA": {"lat": 15.6888, "lon": -88.6086},
    "SHANGHAI": {"lat": 31.2304, "lon": 121.4737},
    "QINGDAO": {"lat": 36.0671, "lon": 120.3826},
    "TIANJIN": {"lat": 39.3434, "lon": 117.3616},
    "XIAMEN": {"lat": 24.4798, "lon": 118.0894},
    "NANSHA": {"lat": 22.7535, "lon": 113.6264},
    "DALIAN": {"lat": 38.9140, "lon": 121.6147},
    "NINGBO": {"lat": 29.8683, "lon": 121.5440},
    "ZHANGJIAGANG": {"lat": 31.8773, "lon": 120.5562},
    "TAICANG": {"lat": 31.4505, "lon": 121.1306},
    "LANSHAN": {"lat": 35.1228, "lon": 119.3496},
    "PUTIAN": {"lat": 25.4326, "lon": 119.0159},
    "YAN TIAN": {"lat": 22.575, "lon": 114.276},
    "TOKYO": {"lat": 35.6762, "lon": 139.6503},
    "YOKOHAMA": {"lat": 35.4437, "lon": 139.6380},
    "OSAKA": {"lat": 34.6937, "lon": 135.5023},
    "KOBE": {"lat": 34.6901, "lon": 135.1955},
    "NAGOYA": {"lat": 35.1815, "lon": 136.9066},
    "BUSAN": {"lat": 35.1796, "lon": 129.0756},
    "INCHON": {"lat": 37.4563, "lon": 126.7052},
    "GWANGYANG": {"lat": 34.9407, "lon": 127.6959},
    "HO CHI MINH": {"lat": 10.8231, "lon": 106.6297},
    "HAIPHONG": {"lat": 20.8449, "lon": 106.6881},
    "PORT KLANG": {"lat": 3.00, "lon": 101.40},
    "PENANG": {"lat": 5.4164, "lon": 100.3327},
    "BANGKOK": {"lat": 13.7563, "lon": 100.5018},
    "LAEM CHABANG": {"lat": 13.0825, "lon": 100.9108},
    "JAKARTA": {"lat": -6.2088, "lon": 106.8456},
    "SURABAYA": {"lat": -7.2575, "lon": 112.7521},
    "SEMARANG": {"lat": -6.9667, "lon": 110.4167},
    "BELAWAN": {"lat": 3.7853, "lon": 98.6860},
    "ICD WHITEFIELD": {"lat": 12.9866, "lon": 77.7499},
    "ICD PITHAMPUR": {"lat": 22.6841, "lon": 75.8770},
    "ICD DHANNAD": {"lat": 22.6622, "lon": 75.5684},
    "ICD GARHI HARSARU": {"lat": 28.4357, "lon": 76.9238},
    "ICD SANATHNAGAR": {"lat": 17.4649, "lon": 78.4355},
    "ICD TUGHLAKABAD": {"lat": 28.5134, "lon": 77.2662},
    "ICD MORADABAD": {"lat": 28.8683, "lon": 78.7291},
    "ICD PANKI": {"lat": 26.4385, "lon": 80.2222},
    "ICD PATLI": {"lat": 28.9197, "lon": 76.9200},
    "ICD BADDI": {"lat": 29.0200, "lon": 77.0500},
    "ICD TIMMAPUR": {"lat": 17.2000, "lon": 78.2000},
    "ICD SACHIN": {"lat": 20.2000, "lon": 72.8000},
    "ICD ANKLESHWAR": {"lat": 17.6800, "lon": 83.2000},
    "ICD AJMER": {"lat": 26.4499, "lon": 74.6399},
    "ICD NOIDA": {"lat": 28.5355, "lon": 77.3910}
}

# ==========================================
# 6. 树种分类归属
# ==========================================
SPECIES_CATEGORY_MAP = {
    "Softwood": ["Radiata", "Spruce", "Fir", "Pine (Gen)", "Larch", "SYP / Taeda"],
    "Hardwood": ["Oak", "Birch", "Beech", "Poplar", "Eucalyptus", "Acacia", "Rubberwood", "Teak", "Ash", "Maple", "Cherry", "Walnut", "Meranti"]
}

# ==========================================
# 7. 港口代码转名称映射 (Code -> Name)
# ==========================================
PORT_CODE_TO_NAME = {
    # 截图中的 Wood Chip 港口
    "INKAK1": "Kakinada",
    "INKRK1": "Karaikal",
    "INMRM1": "Mormugao (Goa)",
    "INVTZ1": "Visakhapatnam", # [Fix] 将 INVTZ1 映射为 Visakhapatnam
    
    # 其他常用港口
    "INMUN1": "Mundra",
    "INNSA1": "Nhava Sheva",
    "INMAA1": "Chennai",
    "INCOK1": "Cochin",
    "INCOK4": "Cochin (ICTT)",
    "INKAT1": "Kattupalli",
    "INENR1": "Ennore",
    "INTUT1": "Tuticorin",
    "INTUT6": "Tuticorin",
    "INIXY1": "Kandla",
    "INHZA1": "Hazira",
    "INCCU1": "Kolkata",
    "INBOM4": "Mumbai (Air)",
    
    # ICDs
    "INTKD6": "ICD Tughlakabad", "INWFD6": "ICD Whitefield", "INCPL6": "ICD Pithampur",
    "INDHA6": "ICD Dhannad", "INGHR6": "ICD Garhi Harsaru", "INSNF6": "ICD Sanathnagar",
    "INMBD6": "ICD Moradabad", "INPNK6": "ICD Panki", "INPTL6": "ICD Patli",
    "INBDM6": "ICD Baddi", "INTMX6": "ICD Timmapur", "INSAJ6": "ICD Sachin",
    "INAKP6": "ICD Ankleshwar", "INAJM6": "ICD Ajmer", "INNDA6": "ICD Noida"
}