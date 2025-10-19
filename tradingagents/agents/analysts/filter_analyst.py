"""股票概念筛选Agent - 用于筛选符合条件的概念股票并加入到graph中"""
import json
import pandas as pd
import akshare as ak
import os
from datetime import datetime, timedelta
import time
import warnings
from typing import Dict, Any, List
from tradingagents.utils.logging_manager import get_logger

# 忽略警告信息
warnings.filterwarnings('ignore')

# 初始化日志
logger = get_logger('agents')

class StockFilterAgent:
    def __init__(self, cache_dir="./stock_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        logger.info(f"📊 股票筛选Agent初始化，缓存目录: {cache_dir}")
        
    def get_cached_data(self, key: str, data_func, cache_minutes: int = 30) -> pd.DataFrame:
        """缓存数据获取函数"""
        cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
        
        # 检查缓存是否存在且未过期
        if os.path.exists(cache_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - file_time < timedelta(minutes=cache_minutes):
                logger.debug(f"🔍 从缓存加载数据: {key}")
                return pd.read_pickle(cache_file)
        
        # 获取新数据并缓存
        logger.debug(f"📥 获取新数据: {key}")
        data = data_func()
        data.to_pickle(cache_file)
        return data
    
    def get_stock_basic_info(self) -> pd.DataFrame:
        """获取股票基本信息"""
        def fetch_data():
            # 获取A股基本信息
            logger.info("📥 获取A股基本信息")
            stock_info = ak.stock_info_a_code_name()
            # 获取实时行情数据
            logger.info("📥 获取A股实时行情数据")
            stock_spot = ak.stock_zh_a_spot_em()
            # 合并数据
            merged_data = pd.merge(stock_info, stock_spot, left_on='code', right_on='代码')
            return merged_data
        return self.get_cached_data("stock_basic_info", fetch_data)
    
    def get_financial_indicators(self, stock_codes: List[str]) -> pd.DataFrame:
        """获取财务指标数据"""
        def fetch_data():
            financial_data = {}
            logger.info(f"📥 获取{len(stock_codes[:50])}只股票的财务指标")
            for code in stock_codes[:50]:  # 限制数量避免请求过多
                try:
                    # 获取个股财务指标
                    indicator = ak.stock_financial_analysis_indicator(symbol=code)
                    if not indicator.empty:
                        financial_data[code] = indicator.iloc[0]  # 取最新数据
                    time.sleep(0.1)  # 防止反爬
                except Exception as e:
                    logger.warning(f"⚠️ 获取{code}财务指标失败: {str(e)}")
                    continue
            return pd.DataFrame.from_dict(financial_data, orient='index')
        return self.get_cached_data("financial_indicators", fetch_data)
    
    def get_technical_indicators(self, stock_codes: List[str]) -> pd.DataFrame:
        """获取技术指标数据"""
        def fetch_data():
            technical_data = {}
            logger.info(f"📥 获取{len(stock_codes[:50])}只股票的技术指标")
            for code in stock_codes[:50]:
                try:
                    # 获取历史数据计算技术指标
                    hist_data = ak.stock_zh_a_hist(symbol=code, period="daily", start_date="20240101")
                    if not hist_data.empty:
                        # 计算简单技术指标
                        latest = hist_data.iloc[-1]
                        technical_data[code] = {
                            'current_price': latest['收盘'],
                            'volume_ratio': latest['成交量'] / hist_data['成交量'].mean() if hist_data['成交量'].mean() > 0 else 1,
                            'price_change': (latest['收盘'] - hist_data.iloc[-2]['收盘']) / hist_data.iloc[-2]['收盘'] * 100,
                            'ma5': hist_data['收盘'].tail(5).mean(),
                            'ma20': hist_data['收盘'].tail(20).mean()
                        }
                    time.sleep(0.1)
                except Exception as e:
                    logger.warning(f"⚠️ 获取{code}技术指标失败: {str(e)}")
                    continue
            return pd.DataFrame.from_dict(technical_data, orient='index')
        return self.get_cached_data("technical_indicators", fetch_data)
    
    def filter_stocks_by_technical(self, stock_names: List[str], concept_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """基于技术指标筛选股票"""
        logger.info("🔍 开始技术指标筛选...")
        
        # 获取所有股票基本信息
        all_stocks = self.get_stock_basic_info()
        
        # 将股票名称映射到代码
        name_to_code = {}
        valid_stocks = []
        
        for stock_name in stock_names:
            matches = all_stocks[all_stocks['name'] == stock_name]
            if not matches.empty:
                code = matches.iloc[0]['code']
                name_to_code[stock_name] = code
                valid_stocks.append(code)
        
        if not valid_stocks:
            logger.warning("⚠️ 没有找到有效的股票代码")
            return []
        
        # 获取技术指标
        technical_data = self.get_technical_indicators(valid_stocks)
        
        # 筛选条件
        filtered_stocks = []
        for stock_name, stock_code in name_to_code.items():
            if stock_code in technical_data.index:
                tech_data = technical_data.loc[stock_code]
                
                # 技术筛选条件
                conditions = [
                    tech_data.get('price_change', 0) < 5,  # 当日涨幅小于5%
                    tech_data.get('volume_ratio', 0) > 0.8,  # 量比大于0.8
                    tech_data.get('current_price', 0) > tech_data.get('ma5', 0),  # 股价在5日均线上
                    tech_data.get('current_price', 0) > 5,  # 股价高于5元
                ]
                
                if sum(conditions) >= 3:  # 满足至少3个条件
                    filtered_stocks.append({
                        '股票名称': stock_name,
                        '股票代码': stock_code,
                        '当前价格': tech_data.get('current_price', 0),
                        '涨跌幅': tech_data.get('price_change', 0),
                        '量比': tech_data.get('volume_ratio', 0),
                        '概念名称': concept_data['概念名称'],
                        '概念排名': concept_data['排名']
                    })
        
        logger.info(f"✅ 技术指标筛选完成，找到{len(filtered_stocks)}只符合条件的股票")
        return filtered_stocks
    
    def filter_stocks_by_financial(self, stock_names: List[str]) -> List[str]:
        """基于财务指标筛选股票"""
        logger.info("🔍 开始财务指标筛选...")
        
        all_stocks = self.get_stock_basic_info()
        name_to_code = {}
        valid_stocks = []
        
        for stock_name in stock_names:
            matches = all_stocks[all_stocks['name'] == stock_name]
            if not matches.empty:
                code = matches.iloc[0]['code']
                name_to_code[stock_name] = code
                valid_stocks.append(code)
        
        if not valid_stocks:
            logger.warning("⚠️ 没有找到有效的股票代码")
            return []
        
        # 获取财务指标
        financial_data = self.get_financial_indicators(valid_stocks)
        
        filtered_stocks = []
        for stock_name, stock_code in name_to_code.items():
            if stock_code in financial_data.index:
                fin_data = financial_data.loc[stock_code]
                
                # 财务筛选条件
                try:
                    pe_ratio = fin_data.get('市盈率', 1000)
                    pb_ratio = fin_data.get('市净率', 1000)
                    roe = fin_data.get('净资产收益率', 0)
                    
                    conditions = [
                        pe_ratio > 0 and pe_ratio < 50,  # 市盈率在0-50之间
                        pb_ratio > 0 and pb_ratio < 5,   # 市净率在0-5之间
                        roe > 5  # 净资产收益率大于5%
                    ]
                    
                    if sum(conditions) >= 2:  # 满足至少2个条件
                        filtered_stocks.append(stock_name)
                except Exception as e:
                    logger.warning(f"⚠️ 处理{stock_name}财务数据时出错: {str(e)}")
                    continue
        
        logger.info(f"✅ 财务指标筛选完成，找到{len(filtered_stocks)}只符合条件的股票")
        return filtered_stocks
    
    def comprehensive_filter(self, concept_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """综合筛选股票"""
        stock_names = concept_data['成分股名称']
        logger.info(f"🔍 开始筛选概念 '{concept_data['概念名称']}' 下的 {len(stock_names)} 只股票...")
        
        # 第一轮：技术指标筛选
        technically_filtered = self.filter_stocks_by_technical(stock_names, concept_data)
        
        if not technically_filtered:
            logger.warning(f"⚠️ 概念 '{concept_data['概念名称']}' 下没有通过技术指标筛选的股票")
            return []
        
        # 第二轮：财务指标筛选
        financially_filtered = self.filter_stocks_by_financial(stock_names)
        
        # 综合筛选结果
        final_stocks = []
        for stock in technically_filtered:
            if stock['股票名称'] in financially_filtered or not financially_filtered:
                final_stocks.append(stock)
        
        # 按涨跌幅排序，取前5只
        final_stocks.sort(key=lambda x: abs(x['涨跌幅']), reverse=True)
        result = final_stocks[:5]
        
        logger.info(f"✅ 概念 '{concept_data['概念名称']}' 筛选完成，推荐{len(result)}只股票")
        return result


def concept_stock_filter_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    概念股票筛选Agent节点，用于Graph流程
    
    Args:
        state: 包含以下键的字典:
            - concept_file: 概念数据文件路径
            - cache_dir: 缓存目录路径（可选）
            - trade_date: 交易日期（可选）
    
    Returns:
        更新后的state，包含筛选结果
    """
    logger.info("📊 ===== 概念股票筛选Agent开始执行 =====")
    
    # 从state中获取参数
    concept_file = state.get('concept_file', "concept_stocks_recommendation.json")
    cache_dir = state.get('cache_dir', "./stock_cache")
    
    # 验证概念文件是否存在
    if not os.path.exists(concept_file):
        logger.error(f"❌ 概念文件不存在: {concept_file}")
        state['stock_filter_result'] = None
        state['filter_status'] = 'failed'
        state['filter_error'] = f"概念文件不存在: {concept_file}"
        return state
    
    try:
        # 初始化筛选器
        filter_agent = StockFilterAgent(cache_dir=cache_dir)
        
        # 加载概念数据
        logger.info(f"📥 加载概念数据: {concept_file}")
        with open(concept_file, 'r', encoding='utf-8') as f:
            concept_data = json.load(f)
        
        # 执行筛选
        all_recommendations = []
        logger.info(f"📋 开始处理 {concept_data['推荐概念总数']} 个推荐概念...")
        
        for concept in concept_data['推荐列表']:
            logger.info(f"\n📌 处理概念: {concept['概念名称']} (排名: {concept['排名']})")
            
            try:
                filtered_stocks = filter_agent.comprehensive_filter(concept)
                
                if filtered_stocks:
                    concept_recommendation = {
                        '概念名称': concept['概念名称'],
                        '概念排名': concept['排名'],
                        '涨跌幅': concept.get('涨跌幅(%)', 0),
                        '推荐股票': filtered_stocks
                    }
                    all_recommendations.append(concept_recommendation)
                    
                    logger.info(f"📈 推荐 {len(filtered_stocks)} 只股票")
                else:
                    logger.info(f"📉 该概念下无符合筛选条件的股票")
                    
            except Exception as e:
                logger.error(f"❌ 处理概念 {concept['概念名称']} 时出错: {str(e)}")
                continue
        
        # 保存结果到state
        state['stock_filter_result'] = {
            "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "推荐概念数量": len(all_recommendations),
            "推荐详情": all_recommendations
        }
        state['filter_status'] = 'success'
        
        # 如果需要，保存到文件
        if state.get('save_filter_result', True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"stock_recommendations_{timestamp}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(state['stock_filter_result'], f, ensure_ascii=False, indent=2)
            logger.info(f"💾 推荐结果已保存到: {output_file}")
            state['filter_output_file'] = output_file
        
        logger.info("📊 ===== 概念股票筛选Agent执行完成 =====")
        return state
        
    except Exception as e:
        logger.error(f"❌ 概念股票筛选Agent执行失败: {str(e)}", exc_info=True)
        state['stock_filter_result'] = None
        state['filter_status'] = 'failed'
        state['filter_error'] = str(e)
        return state


"""
# 将Agent添加到Graph的示例代码
if __name__ == "__main__":
    # 示例：创建一个简单的Graph并添加此Agent
    from langgraph.graph import Graph, END
    
    # 初始化图
    workflow = Graph()
    
    # 添加筛选Agent节点
    workflow.add_node("filter_stocks", concept_stock_filter_agent)
    
    # 设置入口点
    workflow.set_entry_point("filter_stocks")
    
    # 设置出口点
    workflow.add_edge("filter_stocks", END)
    
    # 编译图
    app = workflow.compile()
    
    # 测试运行
    test_state = {
        "concept_file": "concept_stocks_recommendation_20251013_004800.json",  # 替换为实际文件路径
        "cache_dir": "./stock_cache",
        "save_filter_result": True
    }
    
    result = app.invoke(test_state)
    
    if result['filter_status'] == 'success':
        logger.info(f"🎉 筛选成功，共推荐 {result['stock_filter_result']['推荐概念数量']} 个概念")
    else:
        logger.error(f"❌ 筛选失败: {result['filter_error']}")
"""