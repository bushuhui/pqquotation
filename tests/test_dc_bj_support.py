# coding: utf8
"""
测试DC数据源对北交所股票的支持情况
"""

import sys
import os
import requests
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def test_bj_stocks_api_directly():
    """直接测试北交所股票的API支持"""
    
    bj_stocks = [
        '834014.BJ',  # 华创优选
        '870436.BJ',  # 华星股份
        '832491.BJ',  # 广脉科技
        '832000.BJ',  # 爱科生物
        '831906.BJ'   # 长虹三佳
    ]
    
    base_url = "https://push2.eastmoney.com/api/qt/stock/get"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/'
    }
    
    print("测试北交所股票的API支持")
    print("=" * 50)
    
    for stock in bj_stocks:
        print(f"\n测试股票: {stock}")
        
        # 提取数字代码
        import re
        num_code = re.search(r"(\d+)", stock).group(1)
        
        # 测试不同的市场前缀
        # 北交所在东方财富系统中可能使用特殊的市场标识
        for market_prefix in ['0', '1', '2', '3', '4', '5']:
            secid = f"{market_prefix}.{num_code}"
            
            params = {
                "invt": "2",
                "fltt": "1",
                "fields": "f58,f57,f43,f44,f45,f46,f47,f48,f60,f86",
                "secid": secid,
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "_": str(int(time.time() * 1000))
            }
            
            try:
                response = requests.get(base_url, headers=headers, params=params, timeout=5)
                data = response.json()
                
                if data and data.get("data") and data["data"].get("f58"):
                    name = data["data"]["f58"]
                    price = data["data"].get("f43", 0)
                    print(f"  ✓ secid={secid}: {name}, 价格={price/100 if price else 0}")
                    break  # 找到有效的市场前缀就停止
                else:
                    print(f"  × secid={secid}: 无数据", end="")
                    
            except Exception as e:
                print(f"  × secid={secid}: 请求失败", end="")
        
        print()  # 换行

def test_special_stock_codes():
    """测试其他特殊股票代码"""
    
    special_codes = [
        '000043.SH',  # 中航地产 - 这是个特殊情况，000开头但在上海
        '515220.SH',  # 上海ETF
        '588000.SH',  # 科创板
        '430139.BJ',  # 北交所另一种代码格式
        '920489.BJ'   # 北交所另一种代码格式
    ]
    
    print("\n测试特殊股票代码的API支持")
    print("=" * 50)
    
    base_url = "https://push2.eastmoney.com/api/qt/stock/get"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/'
    }
    
    for stock in special_codes:
        print(f"\n测试股票: {stock}")
        
        import re
        num_code = re.search(r"(\d+)", stock).group(1)
        
        # 根据后缀尝试不同的市场前缀
        if stock.endswith('.BJ'):
            prefixes = ['0', '1', '2', '3', '4', '5']
        elif stock.endswith('.SH'):
            prefixes = ['1', '0']  # 上海优先用1
        else:
            prefixes = ['0', '1']  # 深圳优先用0
        
        for market_prefix in prefixes:
            secid = f"{market_prefix}.{num_code}"
            
            params = {
                "invt": "2",
                "fltt": "1", 
                "fields": "f58,f57,f43,f44,f45,f46,f47,f48,f60,f86",
                "secid": secid,
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "_": str(int(time.time() * 1000))
            }
            
            try:
                response = requests.get(base_url, headers=headers, params=params, timeout=5)
                data = response.json()
                
                if data and data.get("data") and data["data"].get("f58"):
                    name = data["data"]["f58"]
                    price = data["data"].get("f43", 0)
                    print(f"  ✓ secid={secid}: {name}, 价格={price/100 if price else 0}")
                    break
                else:
                    print(f"  × secid={secid}: 无数据", end="")
                    
            except Exception as e:
                print(f"  × secid={secid}: 请求失败", end="")
        
        print()

def test_current_dc_implementation():
    """测试当前DC实现对这些股票的处理"""
    
    print("\n测试当前DC实现")
    print("=" * 50)
    
    test_codes = [
        '834014.BJ', '870436.BJ',    # 北交所
        '000043.SH', '515220.SH',    # 特殊上海股票
        '588000.SH'                  # 科创板
    ]
    
    dc = pqquotation.use('dc')
    
    for code in test_codes:
        print(f"\n测试 {code}:")
        try:
            data = dc.stocks([code])
            if data:
                print(f"  ✓ 成功获取: {list(data.keys())}")
                for k, v in data.items():
                    print(f"    {k}: {v.get('name', 'N/A')}")
            else:
                print(f"  × 失败: 返回空数据")
        except Exception as e:
            print(f"  × 失败: {e}")

if __name__ == '__main__':
    test_bj_stocks_api_directly()
    test_special_stock_codes()
    test_current_dc_implementation()