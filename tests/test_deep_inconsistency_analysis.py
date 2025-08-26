# coding: utf8
"""
深度分析数据不一致问题的具体原因
"""

import sys
import os
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def analyze_inconsistency_patterns(stock_codes):
    """分析不一致股票的模式"""
    print("分析不一致股票的类型分布")
    print("=" * 50)
    
    patterns = {
        'SZ股票': [code for code in stock_codes if code.endswith('.SZ')],
        'SH股票': [code for code in stock_codes if code.endswith('.SH')], 
        'BJ股票': [code for code in stock_codes if code.endswith('.BJ')],
        '科创板': [code for code in stock_codes if code.startswith('688') and code.endswith('.SH')],
        '创业板': [code for code in stock_codes if code.startswith('30') and code.endswith('.SZ')],
        'ETF基金': [code for code in stock_codes if code.startswith('51') or code.startswith('159')],
        '主板股票': [code for code in stock_codes if (code.startswith('600') or code.startswith('000')) and not code.startswith('688')]
    }
    
    for pattern_name, codes in patterns.items():
        if codes:
            print(f"{pattern_name}: {len(codes)}个 - {codes[:5]}{'...' if len(codes) > 5 else ''}")
    
    return patterns

def get_detailed_comparison(stock_codes):
    """获取详细的三方数据对比"""
    sources = ['sina', 'qq', 'dc']
    apis = {}
    
    print(f"\n获取 {len(stock_codes)} 个股票的详细数据...")
    
    # 初始化APIs
    for source in sources:
        try:
            apis[source] = pqquotation.use(source)
            print(f"✓ {source} 初始化成功")
        except Exception as e:
            print(f"× {source} 初始化失败: {e}")
            return None
    
    # 并发获取数据
    def fetch_source_data(source):
        try:
            api = apis[source]
            data = api.stocks(stock_codes)
            return source, data
        except Exception as e:
            print(f"× {source} 数据获取失败: {e}")
            return source, {}
    
    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_source = {
            executor.submit(fetch_source_data, source): source 
            for source in sources
        }
        
        for future in as_completed(future_to_source):
            source, data = future.result()
            results[source] = data
            print(f"  {source}: 获取到 {len(data)} 个股票数据")
    
    return results

def analyze_field_differences(code, all_data):
    """分析单个股票各字段的差异"""
    print(f"\n详细分析: {code}")
    print("-" * 40)
    
    # 检查数据可用性
    available_sources = []
    for source in ['sina', 'qq', 'dc']:
        if code in all_data[source] and all_data[source][code]:
            available_sources.append(source)
        else:
            print(f"× {source}: 无数据")
    
    if len(available_sources) < 2:
        print(f"可用数据源不足: {available_sources}")
        return {'availability_issue': True}
    
    print(f"可用数据源: {', '.join(available_sources)}")
    
    # 对比关键字段
    fields = ['name', 'now', 'open', 'high', 'low', 'close', 'volume']
    field_analysis = {}
    inconsistent_fields = []
    
    for field in fields:
        values = {}
        types = {}
        
        for source in available_sources:
            stock_data = all_data[source][code]
            value = stock_data.get(field)
            values[source] = value
            types[source] = type(value).__name__
        
        # 分析字段一致性
        field_consistent = True
        notes = []
        
        if field == 'name':
            # 名称对比
            unique_names = set()
            for source, name in values.items():
                if name:
                    cleaned = str(name).replace(' ', '').replace('*', '').strip()
                    unique_names.add(cleaned)
            
            if len(unique_names) > 1:
                field_consistent = False
                notes.append(f"名称差异: {unique_names}")
        
        elif field in ['now', 'open', 'high', 'low', 'close']:
            # 价格字段对比
            numeric_values = []
            for source, value in values.items():
                if value is not None:
                    try:
                        numeric_values.append(float(value))
                    except (ValueError, TypeError):
                        notes.append(f"{source}价格非数值: {value}")
                        field_consistent = False
            
            if len(numeric_values) >= 2:
                min_val, max_val = min(numeric_values), max(numeric_values)
                if min_val != max_val and max_val > 0:
                    diff_pct = (max_val - min_val) / max_val * 100
                    if diff_pct > 0.1:  # 0.1%容差
                        field_consistent = False
                        notes.append(f"价格差异: {min_val:.3f}-{max_val:.3f} ({diff_pct:.2f}%)")
        
        elif field == 'volume':
            # 成交量对比（已知QQ问题）
            numeric_values = []
            volume_sources = []
            for source, value in values.items():
                if value is not None:
                    try:
                        vol = float(value)
                        numeric_values.append(vol)
                        volume_sources.append((source, vol))
                    except (ValueError, TypeError):
                        notes.append(f"{source}成交量非数值: {value}")
            
            if len(numeric_values) >= 2:
                max_vol = max(numeric_values)
                min_vol = min(numeric_values)
                if max_vol > 0 and min_vol > 0:
                    ratio = max_vol / min_vol
                    if ratio > 1.5:  # 超过50%差异
                        if 3 < ratio < 50:  # QQ已知问题范围
                            notes.append(f"成交量差异(QQ已知): {ratio:.1f}倍")
                        else:
                            field_consistent = False
                            notes.append(f"成交量异常差异: {ratio:.1f}倍")
        
        # 记录分析结果
        field_analysis[field] = {
            'consistent': field_consistent,
            'values': values,
            'types': types,
            'notes': notes
        }
        
        if not field_consistent:
            inconsistent_fields.append(field)
        
        # 输出详细信息
        status = "✓" if field_consistent else "×"
        print(f"  {status} {field}:")
        for source in available_sources:
            value = values[source]
            type_str = types[source]
            print(f"    {source}: {value} ({type_str})")
        if notes:
            for note in notes:
                print(f"    -> {note}")
    
    analysis_result = {
        'available_sources': available_sources,
        'inconsistent_fields': inconsistent_fields,
        'field_analysis': field_analysis,
        'overall_consistent': len(inconsistent_fields) == 0
    }
    
    return analysis_result

def main():
    """主函数"""
    # 选择一些有代表性的不一致股票进行分析
    sample_stocks = [
        '002775.SZ',  # 深圳股票
        '600187.SH',  # 上海股票  
        '688543.SH',  # 科创板
        '920037.BJ',  # 北交所
        '512100.SH',  # ETF
        '300347.SZ',  # 创业板
        '159919.SZ',  # 深圳ETF
        '510500.SH',  # 上海ETF
    ]
    
    print("深度分析数据不一致问题")
    print("=" * 60)
    
    # 1. 分析股票类型分布
    all_inconsistent = [
        '002775.SZ', '600187.SH', '600606.SH', '688543.SH', '688314.SH', 
        '920037.BJ', '300347.SZ', '688499.SH', '600740.SH', '002133.SZ'
    ]
    analyze_inconsistency_patterns(all_inconsistent[:20])  # 分析前20个
    
    # 2. 详细分析样本股票
    print(f"\n详细分析 {len(sample_stocks)} 个代表性股票:")
    all_data = get_detailed_comparison(sample_stocks)
    
    if not all_data:
        print("无法获取数据，分析终止")
        return
    
    # 3. 逐个分析
    inconsistency_summary = defaultdict(int)
    availability_issues = 0
    
    for code in sample_stocks:
        analysis = analyze_field_differences(code, all_data)
        
        if analysis.get('availability_issue'):
            availability_issues += 1
        else:
            for field in analysis.get('inconsistent_fields', []):
                inconsistency_summary[field] += 1
    
    # 4. 汇总分析
    print("\n" + "=" * 60)
    print("问题汇总分析")
    print("=" * 60)
    
    print(f"数据可用性问题: {availability_issues} 个股票")
    print("字段不一致统计:")
    for field, count in inconsistency_summary.items():
        print(f"  {field}: {count} 个股票存在问题")
    
    if inconsistency_summary:
        most_problematic = max(inconsistency_summary, key=inconsistency_summary.get)
        print(f"\n最大问题字段: {most_problematic} ({inconsistency_summary[most_problematic]}个股票)")
    
    # 建议
    print("\n修复建议:")
    if availability_issues > 0:
        print(f"1. 解决数据获取问题 ({availability_issues}个股票)")
    if 'volume' in inconsistency_summary:
        print("2. 进一步优化成交量差异处理")
    if any(field in inconsistency_summary for field in ['now', 'open', 'high', 'low', 'close']):
        print("3. 检查价格字段的精度和格式问题")
    if 'name' in inconsistency_summary:
        print("4. 统一股票名称格式处理")

if __name__ == '__main__':
    main()