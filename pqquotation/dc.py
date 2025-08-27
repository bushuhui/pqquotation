# coding:utf8
import re
import time
import requests

from . import basequotation


class DC(basequotation.BaseQuotation):
    """东方财富免费行情获取"""

    max_num = 800

    @property
    def stock_api(self) -> str:
        return "https://push2.eastmoney.com/api/qt/stock/get"

    def _get_headers(self) -> dict:
        headers = super()._get_headers()
        return {
            **headers,
            'Referer': 'https://quote.eastmoney.com/'
        }

    def _get_current_timestamp(self):
        return str(int(time.time() * 1000))

    def verify_stock_or_index(self, symbol):
        """验证市场归属，确定API前缀
        返回市场前缀：0=深圳/北交所, 1=上海
        """
        symbol = str(symbol)
        
        # 提取数字代码
        code_match = re.search(r"(\d+)", symbol, re.S | re.M)
        if not code_match:
            return False  # 默认上海
        code = code_match.group(1)
        
        # 1. 优先根据后缀判断（最准确）
        if '.BJ' in symbol:
            # 北交所：统一使用 0. 前缀
            return True
        elif '.SH' in symbol:
            # 明确标识的上海股票：使用 1. 前缀
            return False
        elif '.SZ' in symbol:
            # 明确标识的深圳股票：使用 0. 前缀
            return True
        
        # 2. 特殊指数处理（这些虽然是000开头，但属于上海系统）
        special_sh_indices = {
            '000016',  # 上证50
            '000300',  # 沪深300
            '000852',  # 中证1000
            '000905',  # 中证500
        }
        
        if code in special_sh_indices:
            return False  # 上海市场 (1.)
        
        # 3. 根据代码段判断市场（无后缀的情况）
        
        # 深圳市场代码段 (0.)：
        if code.startswith(('000', '001', '002', '003',    # 深圳主板
                           '300', '301',                  # 创业板
                           '159',                         # 深圳ETF
                           '399')):                       # 深圳指数
            return True
        
        # 上海市场代码段 (1.)：
        if code.startswith(('600', '601', '603', '605',    # 上海主板
                           '688',                          # 科创板
                           '510', '511', '512', '513',     # 上海ETF
                           '515', '516', '517', '518',     
                           '588',                          # 科创板ETF
                           '430', '920')):                 # 特殊代码
            return False
        
        # 4. 默认判断（根据经验规则）
        # 8位数字代码通常是北交所
        if len(code) >= 6:
            # 83xxxx, 87xxxx 等北交所代码
            if code.startswith(('43', '83', '87', '92')):
                return True  # 北交所使用深圳前缀 (0.)
        
        # 默认返回上海
        return False

    def format_str_to_float(self, x):
        """字符串转浮点数"""
        try:
            return float(x) if x != "" and x != "-" else 0
        except:
            return 0

    def format_dc_price(self, x, is_etf=False):
        """格式化东方财富价格数据
        普通股票除以100，ETF基金除以1000
        """
        if x == "-" or x == 0:
            return 0
        
        if is_etf:
            # ETF基金需要除以1000
            return float(x / 1000)
        else:
            # 普通股票除以100
            return float(x / 100)

    def get_stocks_by_range(self, params):
        """重写基类方法，适配东方财富API"""
        if isinstance(params, str):
            stock_codes = params.split(',')
        else:
            stock_codes = [params]
        
        results = {}
        for stock_code in stock_codes:
            if not stock_code.strip():
                continue
                
            # 去掉前缀，只保留6位数字代码
            code = re.search(r"(\d+)", stock_code, re.S | re.M)
            if not code:
                continue
            code = code.group(1)
            
            # 构建请求参数
            params_dict = {
                "invt": "2",
                "fltt": "1",
                "fields": "f58,f734,f107,f57,f43,f59,f169,f301,f60,f170,f152,f177,f111,f46,f44,f45,f47,f260,f48,f261,f279,f277,f278,f288,f19,f17,f531,f15,f13,f11,f20,f18,f16,f14,f12,f39,f37,f35,f33,f31,f40,f38,f36,f34,f32,f211,f212,f213,f214,f215,f210,f209,f208,f207,f206,f161,f49,f171,f50,f86,f84,f85,f168,f108,f116,f167,f164,f162,f163,f92,f71,f117,f292,f51,f52,f191,f192,f262,f294,f295,f748,f747",
                "secid": f"0.{code}",
                "ut": "fa5fd1943c7b386f172d6893dbfba10b",
                "wbp2u": "|0|0|0|web",
                "_": self._get_current_timestamp()
            }
            
            # 判断市场
            if not self.verify_stock_or_index(stock_code):
                params_dict["secid"] = f"1.{code}"
            
            try:
                headers = self._get_headers()
                response = self._session.get(self.stock_api, headers=headers, params=params_dict)
                data_json = response.json()
                
                if data_json and data_json.get("data"):
                    data_info = data_json["data"]
                    
                    # 解析数据
                    stock_data = self._parse_stock_data(data_info, code, stock_code)
                    if stock_data:
                        # 使用6位数字代码作为键，保持与其他数据源一致
                        results[code] = stock_data
                        
            except Exception as e:
                print(f"获取股票 {code} 数据失败: {e}")
                continue
        
        return results
    
    def stocks(self, stock_codes, prefix=False):
        """获取股票实时行情数据"""
        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]
        
        return self.get_stocks_by_range(','.join(stock_codes))
    
    def real(self, stock_codes, prefix=False, return_format=None):
        """获取股票实时行情数据 - 兼容基类接口
        :param stock_codes: 股票代码或股票代码列表
        :param prefix: 是否在返回键中包含市场前缀
        :param return_format: 返回数据中股票代码的格式
        :return: 行情字典
        """
        from . import config, helpers
        
        # 如果没有指定return_format，使用全局配置
        if return_format is None:
            return_format = config.get_config().default_return_format
            
        # 标准化输入为列表
        if isinstance(stock_codes, str):
            stock_codes = [stock_codes]
        elif not isinstance(stock_codes, list):
            stock_codes = list(stock_codes)
            
        # 获取原始数据 - 使用逗号分隔的字符串
        raw_data = self.get_stocks_by_range(','.join(stock_codes))
        
        # 根据return_format调整返回键格式
        if return_format == 'national':
            # 转换为国标格式
            result = helpers.convert_data_keys_to_national_format(raw_data, stock_codes)
        elif return_format == 'digit':
            # 转换为数字格式（去掉前缀）
            converted_data = {}
            for key, value in raw_data.items():
                if isinstance(key, str) and key.startswith(('sh', 'sz', 'bj')):
                    # 去掉前缀，保留6位数字
                    digit_key = key[2:]
                    converted_data[digit_key] = value
                else:
                    converted_data[key] = value
            result = converted_data
        elif return_format == 'prefix' or prefix:
            # 转换为前缀格式（如 sz000001）
            converted_data = {}
            from . import helpers
            for key, value in raw_data.items():
                if isinstance(key, str) and key.isdigit() and len(key) == 6:
                    # 6位数字代码，需要添加市场前缀
                    market_type = helpers.get_stock_type(key)
                    prefix_key = market_type + key
                    converted_data[prefix_key] = value
                elif isinstance(key, str) and key.startswith(('sh', 'sz', 'bj')):
                    # 已经是前缀格式，保持不变
                    converted_data[key] = value
                else:
                    # 其他格式保持不变
                    converted_data[key] = value
            result = converted_data
        else:
            # 默认按照digit格式处理
            converted_data = {}
            for key, value in raw_data.items():
                if isinstance(key, str) and key.startswith(('sh', 'sz', 'bj')):
                    digit_key = key[2:]
                    converted_data[digit_key] = value
                else:
                    converted_data[key] = value
            result = converted_data
            
        return result
    
    def _is_etf(self, code, name=""):
        """判断是否为ETF基金"""
        # 根据代码判断
        if code.startswith(('159', '51')):  # 159xxx.SZ, 51xxxx.SH
            return True
        
        # 根据名称判断（包含ETF关键词）
        if name and 'ETF' in name:
            return True
            
        return False

    def _parse_stock_data(self, data_info, code, stock_code=""):
        """解析股票数据"""
        try:
            # 基本信息
            name = data_info.get("f58", "")
            if not name:
                return None
            
            # 判断是否为ETF基金
            is_etf = self._is_etf(stock_code or code, name)
                
            # 价格信息
            open_price = self.format_dc_price(data_info.get("f46", 0), is_etf)
            high = self.format_dc_price(data_info.get("f44", 0), is_etf)
            pre_close = self.format_dc_price(data_info.get("f60", 0), is_etf)
            low = self.format_dc_price(data_info.get("f45", 0), is_etf)
            now = self.format_dc_price(data_info.get("f43", 0), is_etf)
            
            # 买卖盘信息
            bid1 = self.format_dc_price(data_info.get("f19", 0), is_etf)
            ask1 = self.format_dc_price(data_info.get("f39", 0), is_etf)
            
            # 成交量和成交额
            turnover = self.format_str_to_float(data_info.get("f47", 0))
            volume = self.format_str_to_float(data_info.get("f48", 0))
            
            # 五档买卖盘
            bid_volumes = [
                self.format_str_to_float(data_info.get("f20", 0)),
                self.format_str_to_float(data_info.get("f18", 0)),
                self.format_str_to_float(data_info.get("f16", 0)),
                self.format_str_to_float(data_info.get("f14", 0)),
                self.format_str_to_float(data_info.get("f12", 0))
            ]
            
            bid_prices = [
                self.format_dc_price(data_info.get("f19", 0), is_etf),
                self.format_dc_price(data_info.get("f17", 0), is_etf),
                self.format_dc_price(data_info.get("f15", 0), is_etf),
                self.format_dc_price(data_info.get("f13", 0), is_etf),
                self.format_dc_price(data_info.get("f11", 0), is_etf)
            ]
            
            ask_volumes = [
                self.format_str_to_float(data_info.get("f40", 0)),
                self.format_str_to_float(data_info.get("f38", 0)),
                self.format_str_to_float(data_info.get("f36", 0)),
                self.format_str_to_float(data_info.get("f34", 0)),
                self.format_str_to_float(data_info.get("f32", 0))
            ]
            
            ask_prices = [
                self.format_dc_price(data_info.get("f39", 0), is_etf),
                self.format_dc_price(data_info.get("f37", 0), is_etf),
                self.format_dc_price(data_info.get("f35", 0), is_etf),
                self.format_dc_price(data_info.get("f33", 0), is_etf),
                self.format_dc_price(data_info.get("f31", 0), is_etf)
            ]
            
            # 时间信息
            timestamp = data_info.get("f86", 0)
            if timestamp and timestamp > 0:
                # 转换时间戳（东方财富时间戳是秒）
                dt = time.localtime(timestamp)
                date = time.strftime("%Y-%m-%d", dt)
                time_str = time.strftime("%H:%M:%S", dt)
            else:
                # 使用当前时间
                current_time = time.time()
                dt = time.localtime(current_time)
                date = time.strftime("%Y-%m-%d", dt)
                time_str = time.strftime("%H:%M:%S", dt)
            
            return {
                'name': name,
                'open': open_price,
                'close': pre_close,
                'now': now,
                'high': high,
                'low': low,
                'buy': bid1,
                'sell': ask1,
                'turnover': int(turnover),
                'volume': volume,
                'bid1_volume': int(bid_volumes[0]),
                'bid1': bid_prices[0],
                'bid2_volume': int(bid_volumes[1]),
                'bid2': bid_prices[1],
                'bid3_volume': int(bid_volumes[2]),
                'bid3': bid_prices[2],
                'bid4_volume': int(bid_volumes[3]),
                'bid4': bid_prices[3],
                'bid5_volume': int(bid_volumes[4]),
                'bid5': bid_prices[4],
                'ask1_volume': int(ask_volumes[0]),
                'ask1': ask_prices[0],
                'ask2_volume': int(ask_volumes[1]),
                'ask2': ask_prices[1],
                'ask3_volume': int(ask_volumes[2]),
                'ask3': ask_prices[2],
                'ask4_volume': int(ask_volumes[3]),
                'ask4': ask_prices[3],
                'ask5_volume': int(ask_volumes[4]),
                'ask5': ask_prices[4],
                'date': date,
                'time': time_str,
            }
            
        except Exception as e:
            print(f"解析股票 {code} 数据失败: {e}")
            return None

    def format_response_data(self, rep_data, prefix=False):
        """格式化响应数据"""
        if not rep_data:
            return {}
            
        stock_dict = {}
        for data in rep_data:
            if isinstance(data, dict):
                stock_dict.update(data)
        
        return stock_dict