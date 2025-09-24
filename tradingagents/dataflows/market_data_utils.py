import requests
import pandas as pd
from datetime import datetime
import numpy as np
import json
from dataclasses import dataclass
from typing import List, Dict, Optional
import akshare as ak
# 补充数据类定义（原代码中缺失，用于get_market_distribution函数）
@dataclass
class DistributionItem:
    key: str
    value: str

@dataclass
class MarketDistributionData:
    suspend: int
    last_update_time: str
    limit_down: int
    limit_up: int
    flat: int
    up: int
    down: int
    table: List[DistributionItem]

@dataclass
class MarketDistributionResponse:
    status_code: int
    status_msg: str
    data: Optional[MarketDistributionData]


def get_market_turnover():
    """同花顺API获取市场成交额分时数据"""
    url = "https://dq.10jqka.com.cn/fuyao/market_analysis_api/chart/v1/get_chart_data"
    params = {"chart_key": "turnover_minute"}
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "User-Agent": "PostmanRuntime-ApipostRuntime/1.1.0"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("status_code") != 0:
            raise ValueError(f"接口返回错误: {data.get('status_msg', '未知错误')}")
            
        charts = data.get("data", {}).get("charts", {})
        points = charts.get("point_list", [])
        time_labels = charts.get("x_label_list", [])
        
        if len(points) != len(time_labels):
            raise ValueError("数据长度与时间标签不匹配")
        
        processed_data = []
        for point, time_label in zip(points, time_labels):
            timestamp = point[0] / 1000
            dt = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
            
            processed_data.append({
                "时间": dt,
                "时间标签": time_label,
                "当日成交额(元)": point[1],
                "昨日成交额(元)": point[2],
                "较昨日变动(元)": point[3]
            })
            
        return pd.DataFrame(processed_data)
        
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        return pd.DataFrame()
    except (ValueError, KeyError) as e:
        print(f"数据解析失败: {str(e)}")
        return pd.DataFrame()


def get_market_distribution():
    """
    同花顺API获取市场涨跌分布数据
    Returns:
        MarketDistributionResponse: 结构化的市场涨跌分布数据
    """
    url = "https://dq.10jqka.com.cn/fuyao/up_down_distribution/distribution/v2/realtime"
    
    headers = {
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "User-Agent": "PostmanRuntime-ApipostRuntime/1.1.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        json_data = response.json()
        
        if json_data.get("status_code") != 0:
            raise ValueError(f"接口返回错误: {json_data.get('status_msg', '未知错误')}")
        
        # 解析table数据
        table_items = [
            DistributionItem(item.get("key"), item.get("value")) 
            for item in json_data.get("data", {}).get("table", [])
        ]
        
        # 构建完整的数据结构
        market_data = MarketDistributionData(
            suspend=json_data.get("data", {}).get("suspend", 0),
            last_update_time=json_data.get("data", {}).get("last_update_time", ""),
            limit_down=json_data.get("data", {}).get("limit_down", 0),
            limit_up=json_data.get("data", {}).get("limit_up", 0),
            flat=json_data.get("data", {}).get("flat", 0),
            up=json_data.get("data", {}).get("up", 0),
            down=json_data.get("data", {}).get("down", 0),
            table=table_items
        )
        
        return MarketDistributionResponse(
            status_code=json_data.get("status_code", 0),
            status_msg=json_data.get("status_msg", ""),
            data=market_data
        )
        
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        return None
    except (ValueError, KeyError) as e:
        print(f"数据解析失败: {str(e)}")
        return None


def get_market_score(date: str) -> Optional[dict]:
    """
    同花顺API获取市场综合评分
    :param date: 日期 (格式示例：20250403)
    :return: 包含评分的字典 (包含score_title和score_content)
    """
    url = "https://dq.10jqka.com.cn/fuyao/market_analysis_api/score/v1/get_market_score"
    
    try:
        headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'User-Agent': 'PostmanRuntime-ApipostRuntime/1.1.0'
        }
        response = requests.get(
            url,
            headers=headers,
            params={'date': date},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        if data.get('status_code') != 0:
            print(f"请求失败：{data.get('status_msg', '未知错误')}")
            return None
            
        score_data = data.get('data', {})
        result = {
            'score_title': score_data.get('score_title', ''),
            'score_content': score_data.get('score_content', ''),
            'finance_score': score_data.get('finance_score', 0.0),
            'tech_score': score_data.get('tech_score', 0.0),
            'sum_socre': score_data.get('sum_socre', 0.0)
        }
        
        return result
    except requests.exceptions.RequestException as e:
        print(f"网络请求异常：{str(e)}")
        return None
    except (ValueError, KeyError) as e:
        print(f"数据解析失败：{str(e)}")
        return None


def get_favored_sectors():
    """同花顺API获取热门板块"""
    headers = {
        'cookie': '__utma=156575163.1417338894.1732157798.1732157798.1732157798.1; __utmz=156575163.1732157798.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none); Hm_lvt_722143063e4892925903024537075d0d=1735994556; Hm_lvt_929f8b362150b1f77b477230541dbbc2=1735994556; Hm_lvt_78c58f01938e4d85eaf619eae71b4ed1=1735994503,1736412644; v=A7B1Mop4ozqf1n89X1qzpngHgXUH-ZR0tt3oR6oBfIveZV6rUglk0wbtuN35',
        'referer': 'https://eq.10jqka.com.cn/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
    }
    url = 'https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/plate?type=concept'

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            raise ValueError(f"请求失败，状态码: {response.status_code}")

        data = json.loads(response.text)
        data_strings = [
            sectors_info.get("name") 
            for sectors_info in data.get("data", {}).get("plate_list", [])
            if sectors_info.get("name")
        ]

        md_output = "## 同花顺热门板块\n\n"
        return md_output + str(data_strings)
    
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        return "## 同花顺热门板块\n\n"
    except (ValueError, KeyError) as e:
        print(f"数据解析失败: {str(e)}")
        return "## 同花顺热门板块\n\n"


def get_sector_fund_flow(sector_type: str) -> str:
    """AkShare获取今天板块资金流排名"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type=sector_type)
        sorted_df = df.sort_values(by="今日涨跌幅", ascending=False)
        top_10 = sorted_df.head(10)
        bottom_10 = sorted_df.tail(10)
        combined_df = pd.concat([top_10, bottom_10])
        
        md_output = f"## {sector_type}（今日涨跌幅排名前10与后10）\n\n"
        md_output += combined_df.to_markdown(index=False) + "\n\n"
        return md_output
    
    except Exception as e:
        print(f"数据获取失败: {str(e)}")
        return f"## {sector_type}（今日涨跌幅排名前10与后10）\n\n"


def get_SSE_datas():
    """ 新浪财经API获取大盘数据 """
    headers = {
        'referer': 'https://finance.sina.com.cn/stock/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
    }
    url = 'https://hq.sinajs.cn/rn=1737181300898&list=s_sh000001,s_sz399001,s_sh000300,s_bj899050,s_sz399006'

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            raise ValueError(f"请求失败，状态码: {response.status_code}")

        html = response.text
        data = html.split(",")
        data_strings = []

        data_strings.append("上证指数")
        for i in range(1, 4):
            try:
                data_strings.append(float(data[i]))
            except (IndexError, ValueError):
                data_strings.append(0.0)

        return data_strings
    
    except requests.exceptions.RequestException as e:
        print(f"网络请求失败: {str(e)}")
        return ["上证指数", 0.0, 0.0, 0.0]
    except (ValueError, KeyError) as e:
        print(f"数据解析失败: {str(e)}")
        return ["上证指数", 0.0, 0.0, 0.0]