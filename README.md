# pqquotation


快速获取新浪/腾讯/东方财富的全市场行情，网络正常的情况下只需要 `200+ms`。本软件基于 [easyquotation](https://github.com/shidenggui/easyquotation)改进而来。

## 功能
* 获取新浪的免费实时行情
* 获取腾讯财经的免费实时行情
* 获取东方财富的免费实时行情
* 获取集思路的数据
* 智能轮询机制: sina → tencent → dc 循环轮询访问数据，避免被屏蔽
* 支持的股票代码格式多:
   - 数字格式: 000001, 600000, 430047
   - 前缀格式: sz000001, sh600000, bj430047
   - 国标格式: 000001.SZ, 600000.SH, 430047.BJ
* 结果返回的股票代码默认格式是国标格式，例如 000001.SZ。也可以通过如下的函数设置输出数据的股票代码格式
   - `pqquotation.enable_national_format_globally()`   # 国标格式, 000001.SZ, 600000.SH, 430047.BJ
   - `pqquotation.enable_prefix_format_globally()`  #前缀格式， sz000001, sh600000, bj430047
   - `pqquotation.enable_digit_format_globally()`    # 数字格式， 000001, 600000, 430047

## 安装

```python
pip install pqquotation
```

## 用法

### 引入:

```python
import pqquotation
```

### 选择行情

```python
quotation = pqquotation.use('sina') # 新浪 ['sina'], 腾讯 ['tencent', 'qq'], 东方财富 ['dc', 'eastmoney']
```

### 获取所有股票行情

```python
# prefix 指定返回行情的股票代码是否带 sz/sh/bj 市场前缀
quotation.market_snapshot(prefix=True) 
```

**return**

```python
 {'sh000159': {'name': '国际实业', # 股票名
  'buy': 8.87, # 竞买价
  'sell': 8.88, # 竞卖价
  'now': 8.88, # 现价
  'open': 8.99, # 开盘价
  'close': 8.96, # 昨日收盘价
  'high': 9.15, # 今日最高价
  'low': 8.83, # 今日最低价
  'turnover': 22545048, # 交易股数
  'volume': 202704887.74， # 交易金额
  'ask1': 8.88, # 卖一价
  'ask1_volume': 111900, # 卖一量
  'ask2': 8.89,
  'ask2_volume': 54700,
  'bid1': 8.87, # 买一价
  'bid1_volume': 21800, # 买一量
  ...
  'bid2': 8.86, 
  'bid2_volume': 78400,
  'date': '2016-02-19',
  'time': '14:30:00',
  ...},
  ......
}
```

#### 单只股票

```python
quotation.real('162411') # 支持直接指定前缀，如 'sh000001'
```

#### 多只股票

```python
quotation.real(['000001', '162411']) 
```

#### 多个服务器轮询调用

1. 智能轮询机制: sina → tencent → dc 循环轮询
2. 故障自动切换: 某个数据源失败时自动切换到下一个
3. 数据格式统一: 将tencent和dc的数据格式标准化为sina格式
4. 异常处理: 完整的重试机制和错误处理
5. 性能监控: 统计各数据源的成功率和响应时间
6. 多种别名支持: 'rr'、'roundrobin'、'round-robin'

```Python
import pqquotation

# 创建Round-robin实例
rr = pqquotation.use('roundrobin')  # 或 'rr', 'round-robin'

# 获取实时行情
data = rr.real(['000001', '000002', '600000'])

# 查看数据源统计
stats = rr.get_source_stats()

# 重置失败状态
rr.reset_failed_sources()
```



#### 同时获取指数和行情

```python
# 获取相同代码的指数和股票时 prefix 必须为 True
quotation.real(['sh000001', 'sz000001'], prefix=True)
```

### 更新内置全市场股票代码

```python
easyquotation.update_stock_codes()
```


### 港股日k线图
*[腾讯日k线图](http://web.ifzq.gtimg.cn/appstock/app/hkfqkline/get?_var=kline_dayqfq&param=hk00700,day,,,350,qfq&r=0.7773272375526847)*

```python

import easyquotation
quotation  = easyquotation.use("daykline")
data = quotation.real(['00001','00700'])
print(data)
```

```python
{
    '00001': [
                ['2017-10-09', '352.00', '349.00', '353.00', '348.60', '13455864.00'], # [日期, 今开, 今收, 最高, 最低, 成交量 ]
                ['2017-10-10', '350.80', '351.20', '352.60', '349.80', '10088970.00'],
               ]
    '00700':[
        
    ]           
     }
}
```

### 腾讯港股实时行情 
*[腾讯控股实时行情](http://sqt.gtimg.cn/utf8/q=r_hk00700)*
```python

import easyquotation
quotation = easyquotation.use("hkquote")
data = quotation.real(['00001','00700'])
print(data)
```

```python
{
    '00001': 
        {
            'stock_code': '00001', # 股票代码
            'lotSize': '"100', # 每手数量
            'name': '长和', # 股票名称
            'price': '97.20', # 股票当前价格
            'lastPrice': '97.75', # 股票昨天收盘价格
            'openPrice': '97.75', # 股票今天开盘价格
            'amount': '1641463.0', # 股票成交量 
            'time': '2017/11/29 15:38:58', # 当前时间
            'high': '98.05', # 当天最高价格
            'low': '97.15' # 当天最低价格
        }, 
    '00700': 
        {
            'stock_code': '00700', 
            'lotSize': '"100',
            'name': '腾讯控股', 
            'price': '413.20', 
            'lastPrice': '419.20', 
            'openPrice': '422.20', 
            'amount': '21351010.0', 
            'time': '2017/11/29 15:39:01', 
            'high': '422.80',
            'low': '412.40'
        }
}
```

### 选择 [jsl](https://www.jisilu.cn)（集思录） 行情

```python
quotation = easyquotation.use('jsl') 
```

#### 设置 cookie (可选)

不设置的话获取相关数据有限制

```python
quotation.set_cookie('从浏览器获取的集思录 Cookie')
```


#### 指数ETF查询接口

**TIP :** 尚未包含黄金ETF和货币ETF

*[集思录ETF源网页](https://www.jisilu.cn/data/etf/#tlink_2)*

```python
quotation.etfindex(index_id="", min_volume=0, max_discount=None, min_discount=None)
```

**return**

```python
{
    "510050": {
        "fund_id": "510050",                # 代码
        "fund_nm": "50ETF",                 # 名称
        "price": "2.066",                   # 现价
        "increase_rt": "0.34%",             # 涨幅
        "volume": "71290.96",               # 成交额(万元)
        "index_nm": "上证50",                # 指数
        "pe": "9.038",                      # 指数PE
        "pb": "1.151",                      # 指数PB
        "index_increase_rt": "0.45%",       # 指数涨幅
        "estimate_value": "2.0733",         # 估值
        "fund_nav": "2.0730",               # 净值
        "nav_dt": "2016-03-11",             # 净值日期
        "discount_rt": "-0.34%",            # 溢价率
        "creation_unit": "90",              # 最小申赎单位(万份)
        "amount": "1315800",                # 份额
        "unit_total": "271.84",             # 规模(亿元)
        "index_id": "000016",               # 指数代码
        "last_time": "15:00:00",            # 价格最后时间(未确定)
        "last_est_time": "23:50:02",        # 估值最后时间(未确定)
    }
}
```

## TODO
* [x] 检查数据源 sina，qq，dc，访问数据是否完毕，数据是否一致。sina和dc的数据比较一致，qq的volume字段有些问题
* [x] 增加自动切换服务器的功能，避免长时间连接一个服务器导致屏蔽连接
* [x] 支持多种股票代码格式，支持结果中股票代码格式设置

