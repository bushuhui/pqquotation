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
        """验证是否为股票或指数
        返回 True 表示是深圳市场 (0.)，False 表示是上海市场 (1.)
        """
        code = re.search(r"(\d+)", str(symbol), re.S | re.M).group(1)
        
        # 特殊指数处理 - 这些指数在东方财富系统中属于上海市场
        index_codes = {
            '000300',  # 沪深300
            '000905',  # 中证500
            '000852',  # 中证1000
            '000016',  # 上证50
        }
        
        if code in index_codes:
            return False  # 这些指数属于上海市场 (1.)
        
        # 深圳市场：000xxx(除特殊指数), 002xxx, 003xxx, 300xxx等  
        # 上海市场：600xxx, 601xxx, 603xxx, 688xxx等
        if code.startswith(('000', '002', '003', '300')):
            return True
        return False

    def format_str_to_float(self, x):
        """字符串转浮点数"""
        try:
            return float(x) if x != "" and x != "-" else 0
        except:
            return 0

    def format_dc_price(self, x):
        """格式化东方财富价格数据（除以100）"""
        return float(x / 100) if x != "-" and x != 0 else 0

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
                    stock_data = self._parse_stock_data(data_info, code)
                    if stock_data:
                        results[code] = stock_data
                        
            except Exception as e:
                print(f"获取股票 {code} 数据失败: {e}")
                continue
        
        return results

    def _parse_stock_data(self, data_info, code):
        """解析股票数据"""
        try:
            # 基本信息
            name = data_info.get("f58", "")
            if not name:
                return None
                
            # 价格信息
            open_price = self.format_dc_price(data_info.get("f46", 0))
            high = self.format_dc_price(data_info.get("f44", 0))
            pre_close = self.format_dc_price(data_info.get("f60", 0))
            low = self.format_dc_price(data_info.get("f45", 0))
            now = self.format_dc_price(data_info.get("f43", 0))
            
            # 买卖盘信息
            bid1 = self.format_dc_price(data_info.get("f19", 0))
            ask1 = self.format_dc_price(data_info.get("f39", 0))
            
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
                self.format_dc_price(data_info.get("f19", 0)),
                self.format_dc_price(data_info.get("f17", 0)),
                self.format_dc_price(data_info.get("f15", 0)),
                self.format_dc_price(data_info.get("f13", 0)),
                self.format_dc_price(data_info.get("f11", 0))
            ]
            
            ask_volumes = [
                self.format_str_to_float(data_info.get("f40", 0)),
                self.format_str_to_float(data_info.get("f38", 0)),
                self.format_str_to_float(data_info.get("f36", 0)),
                self.format_str_to_float(data_info.get("f34", 0)),
                self.format_str_to_float(data_info.get("f32", 0))
            ]
            
            ask_prices = [
                self.format_dc_price(data_info.get("f39", 0)),
                self.format_dc_price(data_info.get("f37", 0)),
                self.format_dc_price(data_info.get("f35", 0)),
                self.format_dc_price(data_info.get("f33", 0)),
                self.format_dc_price(data_info.get("f31", 0))
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