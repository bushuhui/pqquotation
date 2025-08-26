# coding: utf8
"""
批量验证DC修复效果
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pqquotation

def test_dc_failed_codes():
    """测试之前失败的所有股票代码"""
    
    failed_codes = [
        '001203.SZ', '001206.SZ', '001255.SZ', '001259.SZ', '001306.SZ', '001335.SZ',
        '159869.SZ', '159929.SZ',
        '301017.SZ', '301025.SZ', '301051.SZ', '301065.SZ', '301102.SZ', '301113.SZ',
        '301119.SZ', '301170.SZ', '301176.SZ', '301195.SZ', '301205.SZ', '301215.SZ',
        '301246.SZ', '301248.SZ', '301251.SZ', '301256.SZ', '301283.SZ', '301295.SZ',
        '301296.SZ', '301349.SZ', '301367.SZ', '301387.SZ', '301390.SZ', '301486.SZ',
        '301517.SZ', '301522.SZ', '301557.SZ', '301617.SZ', '301632.SZ',
        '399005.SZ'
    ]
    
    print(f"测试之前失败的 {len(failed_codes)} 个股票代码")
    print("=" * 60)
    
    dc = pqquotation.use('dc')
    
    success_count = 0
    failed_count = 0
    
    # 分批测试（每批10个）
    batch_size = 10
    for i in range(0, len(failed_codes), batch_size):
        batch = failed_codes[i:i + batch_size]
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
    print("修复效果统计:")
    print(f"成功: {success_count} 个")
    print(f"失败: {failed_count} 个") 
    print(f"成功率: {success_count/(success_count+failed_count)*100:.1f}%")
    
    if success_count > 0:
        print("\n✅ DC数据源修复成功！")
    else:
        print("\n❌ 修复未成功，需要进一步调试")

if __name__ == '__main__':
    test_dc_failed_codes()