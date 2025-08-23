# coding:utf8
import abc
import json
import multiprocessing.pool
import warnings

import requests

from . import helpers
from . import config


class BaseQuotation(metaclass=abc.ABCMeta):
    """行情获取基类"""

    max_num = 800  # 每次请求的最大股票数

    @property
    @abc.abstractmethod
    def stock_api(self) -> str:
        """
        行情 api 地址
        """
        pass

    def __init__(self):
        self._session = requests.session()
        stock_codes = self.load_stock_codes()
        self.stock_list = self.gen_stock_list(stock_codes)

    def gen_stock_list(self, stock_codes):
        stock_with_exchange_list = self._gen_stock_prefix(stock_codes)

        if self.max_num > len(stock_with_exchange_list):
            request_list = ",".join(stock_with_exchange_list)
            return [request_list]

        stock_list = []
        for i in range(0, len(stock_codes), self.max_num):
            request_list = ",".join(
                stock_with_exchange_list[i : i + self.max_num]
            )
            stock_list.append(request_list)
        return stock_list

    def _gen_stock_prefix(self, stock_codes):
        """生成带市场前缀的股票代码列表 (增强版)
        
        支持多种输入格式:
        - 数字格式: 000001 -> sz000001
        - 前缀格式: sz000001 -> sz000001  
        - 国标格式: 000001.SZ -> sz000001
        """
        result = []
        for code in stock_codes:
            try:
                # 标准化为6位数字代码
                normalized_code = helpers.normalize_stock_code(code)
                # 获取市场类型
                market_type = helpers.get_stock_type(code)
                # 生成带前缀的代码
                prefixed_code = market_type + normalized_code
                result.append(prefixed_code)
            except ValueError as e:
                # 记录错误但继续处理其他代码
                print(f"警告: 跳过无效股票代码 {code}: {e}")
                continue
        return result

    @staticmethod
    def load_stock_codes():
        with open(helpers.STOCK_CODE_PATH) as f:
            return json.load(f)["stock"]

    @property
    def all(self):
        warnings.warn("use market_snapshot instead", DeprecationWarning)
        return self.get_stock_data(self.stock_list)

    @property
    def all_market(self):
        """return quotation with stock_code prefix key"""
        return self.get_stock_data(self.stock_list, prefix=True)

    def stocks(self, stock_codes, prefix=False):
        """deprecated, use real instead"""
        warnings.warn("use real instead", DeprecationWarning)
        return self.real(stock_codes, prefix)

    def real(self, stock_codes, prefix=False, return_format=None):
        """返回指定股票的实时行情 (增强版)
        :param stock_codes: 股票代码或股票代码列表，
                支持多种格式：数字格式(000001), 前缀格式(sz000001), 国标格式(000001.SZ) 
        :param prefix: 如果prefix为True，返回的行情字典键以sh/sz/bj市场标识开头
                    如果prefix为False，返回的行情将无法区分指数和股票代码，例如 sh000001 上证指数和 sz000001 平安银行
        :param return_format: 返回数据中股票代码的格式 ('digit': 000001, 'prefix': sz000001, 'national': 000001.SZ)
                    如果为None，使用全局配置的默认格式
                    注意：当return_format='national'时，prefix参数将被忽略
        :return: 行情字典，键为股票代码，值为实时行情。
        """
        # 如果没有指定return_format，使用全局配置
        if return_format is None:
            return_format = config.get_config().default_return_format
        
        if not isinstance(stock_codes, list):
            stock_codes = [stock_codes]

        # 预处理：验证和标准化股票代码
        valid_codes = []
        for code in stock_codes:
            if helpers.validate_stock_code(code):
                valid_codes.append(code)
            else:
                print(f"警告: 跳过无效股票代码 {code}。{helpers.format_stock_code_examples()}")
        
        if not valid_codes:
            print("错误: 没有有效的股票代码")
            return {}

        stock_list = self.gen_stock_list(valid_codes)
        
        # 根据return_format决定prefix参数
        if return_format == 'national':
            # 国标格式时，先获取无prefix的数据，然后转换
            data = self.get_stock_data(stock_list, prefix=False)
            # 转换键格式为国标格式，传入原始代码以保留市场信息
            data = helpers.convert_data_keys_to_national_format(data, valid_codes)
        elif return_format == 'prefix':
            # 前缀格式使用prefix=True
            data = self.get_stock_data(stock_list, prefix=True)
        else:
            # 数字格式或其他，使用原始的prefix参数
            data = self.get_stock_data(stock_list, prefix=prefix)
        
        return data

    def market_snapshot(self, prefix=False):
        """return all market quotation snapshot
        :param prefix: if prefix is True, return quotation dict's  stock_code
             key start with sh/sz market flag
        """
        return self.get_stock_data(self.stock_list, prefix=prefix)

    def get_stocks_by_range(self, params):
        headers = self._get_headers()
        r = self._session.get(self.stock_api + params, headers=headers)
        return r.text

    def _get_headers(self) -> dict:
        return {
            "Accept-Encoding": "gzip, deflate, sdch",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/54.0.2840.100 "
                "Safari/537.36"
            ),
        }

    def get_stock_data(self, stock_list, **kwargs):
        """获取并格式化股票信息"""
        res = self._fetch_stock_data(stock_list)
        return self.format_response_data(res, **kwargs)

    def _fetch_stock_data(self, stock_list):
        """获取股票信息"""
        pool = multiprocessing.pool.ThreadPool(len(stock_list))
        try:
            res = pool.map(self.get_stocks_by_range, stock_list)
        finally:
            pool.close()
        return [d for d in res if d is not None]

    def format_response_data(self, rep_data, **kwargs):
        pass
