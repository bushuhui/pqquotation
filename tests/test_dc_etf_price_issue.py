# coding: utf8
"""
测试DC数据源ETF价格问题
"""

import sys
import os
import requests
import time

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def test_dc_raw_api_response():
    """测试DC API的原始响应"""
    
    # 有问题的ETF
    problem_etfs = [
        '512100.SH',  # 中证1000ETF
        '159919.SZ',  # 沪深300ETF  
        '510500.SH'   # 中证500ETF
    ]
    
    # 正常的股票对比
    normal_stocks = [
        '600187.SH',  # 国中水务
        '300347.SZ'   # 泰格医药
    ]
    
    base_url = "https://push2.eastmoney.com/api/qt/stock/get"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://quote.eastmoney.com/'
    }
    
    print("测试DC API的原始价格响应")
    print("=" * 60)
    
    for category, codes in [("ETF基金", problem_etfs), ("普通股票", normal_stocks)]:
        print(f"\n{category}:")
        for code in codes:
            print(f"\n  {code}:")
            
            # 提取数字代码和判断市场
            import re
            num_code = re.search(r"(\d+)", code).group(1)
            
            # 使用DC的市场判断逻辑
            dc = pqquotation.use('dc')
            use_sz_prefix = dc.verify_stock_or_index(code)
            secid = f"{'0' if use_sz_prefix else '1'}.{num_code}"
            
            params = {
                "invt": "2",
                "fltt": "1",
                "fields": "f58,f43,f60,f46,f44,f45",  # 名称、现价、昨收、开盘、最高、最低
                "secid": secid,
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "_": str(int(time.time() * 1000))
            }
            
            try:
                response = requests.get(base_url, headers=headers, params=params, timeout=5)
                data = response.json()
                
                if data and data.get("data") and data["data"].get("f58"):
                    raw_data = data["data"]
                    name = raw_data.get("f58")
                    raw_price = raw_data.get("f43", 0)
                    
                    # 应用DC的格式化
                    formatted_price = raw_price / 100 if raw_price else 0
                    
                    print(f"    名称: {name}")
                    print(f"    原始价格: {raw_price}")
                    print(f"    格式化后: {formatted_price}")
                    
                    # 对比其他数据源
                    try:
                        sina = pqquotation.use('sina')
                        sina_data = sina.stocks([code])
                        if code in sina_data:
                            sina_price = sina_data[code].get('now')
                            print(f"    Sina价格: {sina_price}")
                            
                            if sina_price:
                                # 检查是否应该不除以100
                                if abs(raw_price - sina_price) < abs(formatted_price - sina_price):
                                    print(f"    ⚠️  原始价格更接近Sina！差异: {abs(raw_price - sina_price):.3f}")
                                else:
                                    print(f"    ✓  格式化价格正确，差异: {abs(formatted_price - sina_price):.3f}")
                    except:
                        pass
                        
                else:
                    print(f"    × 无数据返回")
                    
            except Exception as e:
                print(f"    × 请求失败: {e}")

def test_etf_identification():
    """测试ETF识别逻辑"""
    print("\n" + "=" * 60)
    print("ETF识别逻辑测试")
    print("=" * 60)
    
    test_codes = [
        '512100.SH',  # 中证1000ETF
        '159919.SZ',  # 沪深300ETF
        '510500.SH',  # 中证500ETF
        '600187.SH',  # 国中水务（普通股票）
        '300347.SZ',  # 泰格医药（普通股票）
    ]
    
    for code in test_codes:
        print(f"\n{code}:")
        
        # 判断是否是ETF
        is_etf = code.startswith('51') or code.startswith('159')
        print(f"  是否为ETF: {is_etf}")
        
        # DC实际处理的数据对比
        try:
            dc = pqquotation.use('dc')
            dc_data = dc.stocks([code])
            
            sina = pqquotation.use('sina')
            sina_data = sina.stocks([code])
            
            if code in dc_data and code in sina_data:
                dc_price = dc_data[code].get('now')
                sina_price = sina_data[code].get('now')
                
                print(f"  DC价格: {dc_price}")
                print(f"  Sina价格: {sina_price}")
                
                if dc_price and sina_price:
                    ratio = dc_price / sina_price
                    print(f"  价格比例: {ratio:.3f}")
                    
                    if abs(ratio - 10) < 0.1:
                        print(f"  ⚠️  DC价格是Sina的10倍 - ETF价格格式问题！")
                    elif abs(ratio - 1) < 0.01:
                        print(f"  ✓  价格一致")
                    else:
                        print(f"  ?  价格比例异常")
        except Exception as e:
            print(f"  × 比较失败: {e}")

if __name__ == '__main__':
    test_dc_raw_api_response()
    test_etf_identification()