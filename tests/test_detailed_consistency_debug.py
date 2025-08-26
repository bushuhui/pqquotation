# coding: utf8
"""
详细分析数据一致性问题
"""

import sys
import os
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def get_data_from_all_sources(stock_codes):
    """并发获取所有数据源的数据"""
    sources = ['sina', 'qq', 'dc']
    results = {}
    
    def fetch_source_data(source):
        try:
            api = pqquotation.use(source)
            data = api.stocks(stock_codes)
            return source, data
        except Exception as e:
            print(f"获取{source}数据失败: {e}")
            return source, {}
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_source = {
            executor.submit(fetch_source_data, source): source 
            for source in sources
        }
        
        for future in as_completed(future_to_source):
            source, data = future.result()
            results[source] = data
            
    return results

def analyze_single_stock(code, all_data):
    """分析单个股票在各数据源的详细差异"""
    print(f"\n分析股票: {code}")
    print("=" * 50)
    
    # 检查数据可用性
    available_sources = []
    for source in ['sina', 'qq', 'dc']:
        if code in all_data[source] and all_data[source][code]:
            available_sources.append(source)
    
    if len(available_sources) < 2:
        print(f"可用数据源不足: {available_sources}")
        return None
    
    # 提取关键字段
    fields_to_compare = ['name', 'now', 'open', 'high', 'low', 'close', 'volume']
    comparison = {}
    
    for source in available_sources:
        stock_data = all_data[source][code]
        comparison[source] = {}
        
        for field in fields_to_compare:
            value = stock_data.get(field)
            if value is not None:
                if field in ['now', 'open', 'high', 'low', 'close']:
                    try:
                        comparison[source][field] = float(value)
                    except (ValueError, TypeError):
                        comparison[source][field] = None
                elif field == 'volume':
                    try:
                        comparison[source][field] = int(float(value)) if value != 0 else 0
                    except (ValueError, TypeError):
                        comparison[source][field] = None
                else:
                    comparison[source][field] = str(value).strip()
            else:
                comparison[source][field] = None
    
    # 打印详细对比
    for field in fields_to_compare:
        values = {}
        for source in available_sources:
            values[source] = comparison[source].get(field)
        
        print(f"\n{field}:")
        consistent = True
        reference_val = None
        
        for source, value in values.items():
            print(f"  {source:>5}: {value}")
            
            if reference_val is None and value is not None:
                reference_val = value
            elif reference_val is not None and value is not None:
                if field == 'name':
                    # 名称对比：去除空格后比较
                    val1 = str(reference_val).replace(' ', '').replace('*', '')
                    val2 = str(value).replace(' ', '').replace('*', '')
                    if val1 != val2:
                        consistent = False
                elif field in ['now', 'open', 'high', 'low', 'close']:
                    # 价格对比：0.1%容差
                    if reference_val != 0 and value != 0:
                        diff_pct = abs(reference_val - value) / max(abs(reference_val), abs(value)) * 100
                        if diff_pct > 0.1:
                            consistent = False
                            print(f"    差异: {diff_pct:.3f}%")
                elif field == 'volume':
                    # 成交量对比：5%容差
                    if reference_val != 0 and value != 0:
                        diff_pct = abs(reference_val - value) / max(abs(reference_val), abs(value)) * 100
                        if diff_pct > 5.0:
                            consistent = False
                            print(f"    差异: {diff_pct:.1f}%")
        
        if not consistent:
            print(f"  ❌ {field} 不一致")
        else:
            print(f"  ✓ {field} 一致")
    
    return comparison

def analyze_dc_data_format():
    """分析DC数据格式问题"""
    print("\n" + "=" * 60)
    print("分析DC数据源的数据格式")
    print("=" * 60)
    
    # 测试一个股票的原始返回数据
    test_code = '002903.SZ'
    
    dc = pqquotation.use('dc')
    sina = pqquotation.use('sina')
    qq = pqquotation.use('qq')
    
    print(f"\n测试股票: {test_code}")
    
    for name, api in [('DC', dc), ('Sina', sina), ('QQ', qq)]:
        try:
            data = api.stocks([test_code])
            if test_code in data:
                stock_info = data[test_code]
                print(f"\n{name} 数据源:")
                print(f"  name: '{stock_info.get('name')}' (type: {type(stock_info.get('name'))})")
                print(f"  now: {stock_info.get('now')} (type: {type(stock_info.get('now'))})")
                print(f"  open: {stock_info.get('open')} (type: {type(stock_info.get('open'))})")
                print(f"  volume: {stock_info.get('volume')} (type: {type(stock_info.get('volume'))})")
                print(f"  所有字段: {list(stock_info.keys())}")
            else:
                print(f"\n{name}: 未获取到数据")
        except Exception as e:
            print(f"\n{name}: 获取失败 - {e}")

def main():
    """主函数"""
    # 测试前10个不一致的股票
    problem_stocks = [
        '002903.SZ', '600650.SH', '002264.SZ', '002775.SZ', '301251.SZ',
        '300256.SZ', '002059.SZ', '300745.SZ', '002952.SZ', '300793.SZ'
    ]
    
    print("详细数据一致性诊断")
    print("=" * 60)
    print(f"分析股票: {', '.join(problem_stocks)}")
    
    # 1. 分析数据格式
    analyze_dc_data_format()
    
    # 2. 获取所有数据源的数据
    print(f"\n并发获取三个数据源的数据...")
    all_data = get_data_from_all_sources(problem_stocks[:3])  # 先测试前3个
    
    # 3. 逐个分析
    for code in problem_stocks[:3]:
        analysis = analyze_single_stock(code, all_data)

if __name__ == '__main__':
    main()