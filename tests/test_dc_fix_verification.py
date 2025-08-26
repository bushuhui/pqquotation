# coding: utf8
"""
验证DC修复后的大批量股票获取效果
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def test_dc_fix_comprehensive():
    """综合测试DC修复效果"""
    
    # 之前失败的各种类型股票代码
    test_codes = [
        # 北交所股票
        '834014.BJ', '870436.BJ', '832491.BJ', '832000.BJ', '831906.BJ', 
        '836270.BJ', '838262.BJ', '430139.BJ', '920489.BJ', '872374.BJ',
        
        # 特殊上海股票
        '000043.SH', '515220.SH', '588000.SH', '000300.SH', '000016.SH',
        
        # 普通股票样本
        '600827.SH', '600629.SH', '688516.SH', '601577.SH', '688617.SH',
        '000536.SZ', '300069.SZ', '000768.SZ', '002343.SZ', '301178.SZ'
    ]
    
    print(f"测试DC修复后的批量股票获取能力")
    print(f"测试股票总数: {len(test_codes)}")
    print("=" * 60)
    
    dc = pqquotation.use('dc')
    
    success_count = 0
    failed_count = 0
    
    # 分批测试（每批10个）
    batch_size = 10
    for i in range(0, len(test_codes), batch_size):
        batch = test_codes[i:i + batch_size]
        print(f"\n批次 {i//batch_size + 1}: 测试 {len(batch)} 个股票")
        
        try:
            data = dc.stocks(batch)
            
            for code in batch:
                if code in data and data[code] and data[code].get('name'):
                    success_count += 1
                    name = data[code]['name']
                    price = data[code].get('now', 'N/A')
                    print(f"  ✓ {code}: {name} - {price}")
                else:
                    failed_count += 1
                    print(f"  × {code}: 获取失败")
                    
        except Exception as e:
            print(f"  × 批次失败: {e}")
            failed_count += len(batch)
    
    print("\n" + "=" * 60)
    print("修复验证结果:")
    print(f"成功获取: {success_count} 个")
    print(f"获取失败: {failed_count} 个") 
    success_rate = success_count/(success_count+failed_count)*100
    print(f"成功率: {success_rate:.1f}%")
    
    # 按类型统计
    bj_codes = [c for c in test_codes if c.endswith('.BJ')]
    sh_codes = [c for c in test_codes if c.endswith('.SH')]
    sz_codes = [c for c in test_codes if c.endswith('.SZ')]
    
    print(f"\n按交易所统计:")
    print(f"北交所(.BJ): {len(bj_codes)} 个")
    print(f"上海(.SH): {len(sh_codes)} 个") 
    print(f"深圳(.SZ): {len(sz_codes)} 个")
    
    if success_rate >= 90:
        print("\n🎉 DC数据源修复成功！可以正常获取各类股票数据")
    elif success_rate >= 70:
        print("\n⚠️ DC数据源部分修复，还有少量问题需要解决")
    else:
        print("\n❌ DC数据源修复效果不佳，需要进一步调试")

if __name__ == '__main__':
    test_dc_fix_comprehensive()