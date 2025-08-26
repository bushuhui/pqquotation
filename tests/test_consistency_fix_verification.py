# coding: utf8
"""
验证一致性修复效果
"""

import sys
import os

# 添加项目路径  
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from test_data_consistency_comparison import DataConsistencyChecker

def test_problem_stocks():
    """测试之前有问题的股票"""
    
    # 之前不一致的前10个股票
    problem_stocks = [
        '002903.SZ', '600650.SH', '002264.SZ', '002775.SZ', '301251.SZ',
        '300256.SZ', '002059.SZ', '300745.SZ', '002952.SZ', '300793.SZ'
    ]
    
    print("测试修复后的数据一致性")
    print("=" * 60)
    print(f"测试股票: {', '.join(problem_stocks[:5])}")  # 测试前5个
    
    checker = DataConsistencyChecker()
    
    # 测试这些股票
    results = checker.test_batch_consistency(problem_stocks[:5])
    
    print("\n修复验证结果:")
    print(f"测试股票数: {len(problem_stocks[:5])}")
    print(f"一致性通过: {checker.results['successful_comparisons']}")
    print(f"不一致股票: {len(checker.results['inconsistent_stocks'])}")
    
    success_rate = checker.results['successful_comparisons'] / checker.results['total_tested'] * 100 if checker.results['total_tested'] > 0 else 0
    print(f"一致性比例: {success_rate:.1f}%")
    
    if checker.results['inconsistent_stocks']:
        print("\n剩余不一致问题:")
        for issue in checker.results['inconsistent_stocks']:
            print(f"  {issue['code']}: {', '.join(issue['issues'])}")
    
    if success_rate >= 80:
        print("\n🎉 一致性显著改善！")
    else:
        print("\n⚠️ 仍有一致性问题需要进一步分析")

def test_volume_comparison_logic():
    """测试成交量比较逻辑"""
    print("\n" + "=" * 60)
    print("测试成交量比较逻辑")
    print("=" * 60)
    
    checker = DataConsistencyChecker()
    
    # 模拟QQ vs Sina/DC的成交量差异
    test_cases = [
        ("正常一致", 1000000, 1000000),
        ("小差异", 1000000, 1050000),  # 5%差异
        ("QQ已知问题", 15565200, 361803501),  # 实际观察到的差异
        ("另一个QQ问题", 22092100, 380956013),  # 另一个实际案例
    ]
    
    for name, val1, val2 in test_cases:
        consistent, detail = checker.compare_values('volume', val1, val2)
        status = "✓" if consistent else "×"
        print(f"{status} {name}: {val1} vs {val2} - {detail}")

if __name__ == '__main__':
    test_volume_comparison_logic()
    test_problem_stocks()