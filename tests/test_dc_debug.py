# coding: utf8
"""
调试DC数据源的股票代码转换问题
"""

import sys
import os
import requests
import json
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def test_dc_api_directly():
    """直接测试DC API"""
    
    failed_codes = [
        '001203.SZ',  # 深圳主板新股票
        '301017.SZ',  # 创业板注册制
        '159869.SZ',  # ETF
        '399005.SZ'   # 深圳指数
    ]
    
    base_url = "https://push2.eastmoney.com/api/qt/stock/get"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://quote.eastmoney.com/'
    }
    
    for code in failed_codes:
        print(f"\n测试股票代码: {code}")
        
        # 提取数字代码
        import re
        num_code = re.search(r"(\d+)", code).group(1)
        
        # 测试不同的市场前缀
        for market_prefix in ['0', '1']:
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
                response = requests.get(base_url, headers=headers, params=params)
                data = response.json()
                
                if data and data.get("data") and data["data"].get("f58"):
                    name = data["data"]["f58"]
                    price = data["data"].get("f43", 0)
                    print(f"  ✓ secid={secid}: {name}, 价格={price/100 if price else 0}")
                else:
                    print(f"  × secid={secid}: 无数据或错误")
                    
            except Exception as e:
                print(f"  × secid={secid}: 请求失败 - {e}")

def test_current_dc_implementation():
    """测试当前DC实现"""
    print("\n" + "="*50)
    print("测试当前DC实现")
    print("="*50)
    
    dc = pqquotation.use('dc')
    
    failed_codes = [
        '001203.SZ',
        '301017.SZ', 
        '159869.SZ',
        '399005.SZ'
    ]
    
    for code in failed_codes:
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
    print("DC数据源调试测试")
    print("="*50)
    
    # 1. 直接测试API
    test_dc_api_directly()
    
    # 2. 测试当前实现
    test_current_dc_implementation()