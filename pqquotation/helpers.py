# coding:utf8
import json
import os
import re
from typing import Union, List, Tuple

import requests

STOCK_CODE_PATH = os.path.join(os.path.dirname(__file__), "stock_codes.conf")

# 股票代码格式正则表达式
STOCK_CODE_PATTERNS = {
    'digital': re.compile(r'^\d{6}$'),                       # 数字格式: 000001
    'prefix': re.compile(r'^(sh|sz|bj)\d{6}$', re.I),        # 前缀格式: sz000001 (不区分大小写)
    'national': re.compile(r'^\d{6}\.(SH|SZ|BJ)$')           # 国标格式: 000001.SZ
}

# 国标格式到前缀格式的映射
NATIONAL_TO_PREFIX_MAP = {
    'SH': 'sh',
    'SZ': 'sz', 
    'BJ': 'bj'
}

# 股票代码处理缓存
_CODE_CACHE = {}


def update_stock_codes():
    """更新内置股票代码表"""
    response = requests.get("https://shidenggui.com/easy/stock_codes.json", headers ={'Accept-Encoding':'gzip'})
    with open(STOCK_CODE_PATH, "w") as f:
        f.write(response.text)
    return response.json()


def get_stock_codes(realtime=False):
    """获取内置股票代码表
    :param realtime: 是否获取实时数据, 默认为否"""
    if realtime:
        return update_stock_codes()
    with open(STOCK_CODE_PATH) as f:
        return json.load(f)["stock"]


def detect_stock_code_format(stock_code: str) -> str:
    """检测股票代码格式
    
    :param stock_code: 股票代码
    :return: 格式类型 ('digital', 'national', 'ts', 'unknown')
    """
    if not isinstance(stock_code, str):
        return 'unknown'
    
    # 转换为大写以统一处理
    code_upper = stock_code.upper()
    
    for format_type, pattern in STOCK_CODE_PATTERNS.items():
        if pattern.match(code_upper):
            return format_type
    
    return 'unknown'


def normalize_stock_code(stock_code: str) -> str:
    """将不同格式的股票代码标准化为6位数字格式
    
    :param stock_code: 输入的股票代码
    :return: 标准化后的6位数字代码
    :raises ValueError: 当代码格式无效时抛出异常
    """
    if not isinstance(stock_code, str):
        raise ValueError(f"股票代码必须是字符串类型，当前类型: {type(stock_code)}")
    
    # 使用缓存提高性能
    if stock_code in _CODE_CACHE:
        return _CODE_CACHE[stock_code]
    
    code_upper = stock_code.upper().strip()
    format_type = detect_stock_code_format(code_upper)
    
    if format_type == 'digital':
        # 数字格式: 000001 -> 000001
        normalized = code_upper
    elif format_type == 'prefix':
        # 前缀格式: SZ000001 -> 000001
        normalized = code_upper[2:]
    elif format_type == 'national':
        # 国标格式: 000001.SZ -> 000001
        normalized = code_upper.split('.')[0]
    else:
        raise ValueError(f"不支持的股票代码格式: {stock_code}。支持的格式: "
                        f"数字格式(000001), 前缀格式(sz000001), 国标格式(000001.SZ)")
    
    # 验证标准化后的代码
    if not re.match(r'^\d{6}$', normalized):
        raise ValueError(f"标准化后的股票代码格式无效: {normalized}")
    
    # 缓存结果
    _CODE_CACHE[stock_code] = normalized
    return normalized


def validate_stock_code(stock_code: str) -> bool:
    """验证股票代码是否有效
    
    :param stock_code: 股票代码
    :return: True表示有效，False表示无效
    """
    try:
        normalize_stock_code(stock_code)
        return True
    except (ValueError, AttributeError):
        return False


def get_market_from_national_code(stock_code: str) -> str:
    """从国标格式代码中提取市场标识
    
    :param stock_code: 国标格式股票代码 (如: 000001.SZ)
    :return: 市场标识 ('sh', 'sz', 'bj')
    """
    format_type = detect_stock_code_format(stock_code)
    if format_type == 'national':
        market_suffix = stock_code.upper().split('.')[1]
        return NATIONAL_TO_PREFIX_MAP.get(market_suffix, 'sz')
    return ''


def batch_normalize_stock_codes(stock_codes: List[str]) -> List[str]:
    """批量标准化股票代码
    
    :param stock_codes: 股票代码列表
    :return: 标准化后的股票代码列表
    """
    results = []
    for code in stock_codes:
        try:
            normalized = normalize_stock_code(code)
            results.append(normalized)
        except ValueError as e:
            # 记录无效代码但继续处理其他代码
            print(f"警告: 跳过无效股票代码 {code}: {e}")
            continue
    return results


def get_stock_type(stock_code):
    """判断股票ID对应的证券市场 (增强版)
    匹配规则
    ['4'， '8'] 为 bj
    ['5', '6', '7', '9', '110', '113', '118', '132', '204'] 为 sh
    其余为 sz
    :param stock_code:股票ID, 支持多种格式 (000001, sz000001, 000001.SZ)
    :return 'bj', 'sh' or 'sz'"""
    
    if not isinstance(stock_code, str):
        raise ValueError(f"股票代码必须是字符串类型，当前类型: {type(stock_code)}")
    
    code_upper = stock_code.upper().strip()
    
    # 处理国标格式
    format_type = detect_stock_code_format(code_upper)
    if format_type == 'national':
        return get_market_from_national_code(code_upper)
    
    # 处理前缀格式
    if format_type == 'prefix':
        if code_upper.startswith(("SH", "SZ", "ZZ", "BJ")):
            return code_upper[:2].lower()
    
    # 处理数字格式和其他情况
    # 先标准化为6位数字代码
    try:
        normalized_code = normalize_stock_code(code_upper)
    except ValueError:
        # 如果标准化失败，使用原始逻辑作为后备
        normalized_code = code_upper
    
    # 应用原始的市场判断规则
    bj_head = ("43", "83", "87", "92")
    sh_head = ("5", "6", "7", "9", "110", "113", "118", "132", "204")
    
    if normalized_code.startswith(bj_head):
        return "bj"
    elif normalized_code.startswith(sh_head):
        return "sh"
    return "sz"


def format_stock_code_examples() -> str:
    """返回支持的股票代码格式示例
    
    :return: 格式示例字符串
    """
    return """
支持的股票代码格式:
1. 数字格式: 000001, 600000, 430001
2. 前缀格式: sz000001, sh600000, bj430001  
3. 国标格式: 000001.SZ, 600000.SH, 430001.BJ
"""


# 前缀格式到国标格式的映射
PREFIX_TO_NATIONAL_MAP = {
    'sh': 'SH',
    'sz': 'SZ', 
    'bj': 'BJ'
}


def convert_to_national_format(stock_code: str) -> str:
    """将6位数字股票代码转换为国标格式
    
    :param stock_code: 6位数字股票代码 (如: 000001)
    :return: 国标格式代码 (如: 000001.SZ)
    """
    if not isinstance(stock_code, str):
        raise ValueError(f"股票代码必须是字符串类型，当前类型: {type(stock_code)}")
    
    # 验证输入是6位数字
    if not re.match(r'^\d{6}$', stock_code):
        raise ValueError(f"输入必须是6位数字股票代码，当前输入: {stock_code}")
    
    # 获取市场类型
    market_type = get_stock_type(stock_code)
    
    # 转换为国标格式
    national_suffix = PREFIX_TO_NATIONAL_MAP.get(market_type, 'SZ')  # 默认为SZ
    return f"{stock_code}.{national_suffix}"


def batch_convert_to_national_format(stock_codes: List[str]) -> dict:
    """批量将6位数字代码转换为国标格式
    
    :param stock_codes: 6位数字股票代码列表
    :return: 数字代码到国标格式的映射字典
    """
    conversion_map = {}
    
    for code in stock_codes:
        try:
            # 确保输入是6位数字代码
            if re.match(r'^\d{6}$', code):
                national_code = convert_to_national_format(code)
                conversion_map[code] = national_code
            else:
                print(f"警告: 跳过非6位数字代码 {code}")
        except Exception as e:
            print(f"警告: 转换 {code} 到国标格式失败: {e}")
    
    return conversion_map


def convert_data_keys_to_national_format(data: dict, original_codes: List[str] = None) -> dict:
    """将返回数据的键从各种格式转换为国标格式
    
    :param data: 原始数据字典，键可能是6位数字代码或前缀格式代码
    :param original_codes: 原始输入的股票代码列表，用于保留市场信息
    :return: 键转换为国标格式的数据字典
    """
    if not isinstance(data, dict):
        return data
    
    # 构建原始代码的市场信息映射
    market_info_map = {}
    if original_codes:
        for original_code in original_codes:
            try:
                # 标准化原始代码得到6位数字
                normalized = normalize_stock_code(original_code)
                # 如果原始代码是国标格式，提取其市场信息
                if detect_stock_code_format(original_code) == 'national':
                    market_suffix = original_code.upper().split('.')[1]
                    market_info_map[normalized] = market_suffix
            except:
                continue
    
    converted_data = {}
    
    for code, stock_info in data.items():
        try:
            # 处理6位数字格式的键
            if isinstance(code, str) and re.match(r'^\d{6}$', code):
                # 如果有原始市场信息，使用它；否则使用默认判断
                if code in market_info_map:
                    market_suffix = market_info_map[code]
                    national_code = f"{code}.{market_suffix}"
                else:
                    national_code = convert_to_national_format(code)
                converted_data[national_code] = stock_info
            
            # 处理前缀格式的键（如 sh000001, sz000001）
            elif isinstance(code, str) and re.match(r'^(sh|sz|bj)\d{6}$', code, re.I):
                # 提取市场前缀和数字代码
                market_prefix = code[:2].lower()
                digit_code = code[2:]
                
                # 转换为国标格式
                market_suffix = PREFIX_TO_NATIONAL_MAP.get(market_prefix, 'SZ')
                national_code = f"{digit_code}.{market_suffix}"
                converted_data[national_code] = stock_info
            
            # 已经是国标格式的键，直接保留
            elif isinstance(code, str) and re.match(r'^\d{6}\.(SH|SZ|BJ)$', code):
                converted_data[code] = stock_info
            
            else:
                # 其他格式保持原有键不变
                converted_data[code] = stock_info
                
        except Exception as e:
            print(f"警告: 转换数据键 {code} 失败: {e}")
            # 出错时保持原键
            converted_data[code] = stock_info
    
    return converted_data


def get_return_format_converter(return_format: str):
    """获取返回格式转换器
    
    :param return_format: 返回格式 ('digit', 'prefix', 'national')
    :return: 转换函数
    """
    if return_format == 'national':
        return convert_data_keys_to_national_format
    elif return_format == 'prefix':
        # 这个由现有的prefix参数处理
        return lambda data: data
    else:  # 'digit' 或其他
        return lambda data: data


def clear_code_cache():
    """清空股票代码处理缓存"""
    global _CODE_CACHE
    _CODE_CACHE.clear()

