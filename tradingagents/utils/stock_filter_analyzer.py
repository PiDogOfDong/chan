import json
import pandas as pd
import akshare as ak
import os
from datetime import datetime, timedelta
import time
import warnings
warnings.filterwarnings('ignore')

class stock_filter_tool:
    def __init__(self, cache_dir="./stock_cache"):
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
    def get_cached_data(self, key, data_func, cache_minutes=30):
        """缓存数据获取函数"""
        cache_file = os.path.join(self.cache_dir, f"{key}.pkl")
        
        # 检查缓存是否存在且未过期
        if os.path.exists(cache_file):
            file_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            if datetime.now() - file_time < timedelta(minutes=cache_minutes):
                return pd.read_pickle(cache_file)
        
        # 获取新数据并缓存
        data = data_func()
        data.to_pickle(cache_file)
        return data
    
    def get_stock_basic_info(self):
        """获取股票基本信息"""
        def fetch_data():
            # 获取A股基本信息
            stock_info = ak.stock_info_a_code_name()
            # 获取实时行情数据
            stock_spot = ak.stock_zh_a_spot_em()
            # 合并数据
            merged_data = pd.merge(stock_info, stock_spot, left_on='code', right_on='代码')
            return merged_data
        return self.get_cached_data("stock_basic_info", fetch_data)
    
    def get_financial_indicators(self, stock_codes):
        """获取财务指标数据"""
        def fetch_data():
            financial_data = {}
            for code in stock_codes[:50]:  # 限制数量避免请求过多
                try:
                    # 获取个股财务指标
                    indicator = ak.stock_financial_analysis_indicator(symbol=code)
                    if not indicator.empty:
                        financial_data[code] = indicator.iloc[0]  # 取最新数据
                    time.sleep(0.1)  # 防止反爬
                except:
                    continue
            return pd.DataFrame.from_dict(financial_data, orient='index')
        return self.get_cached_data("financial_indicators", fetch_data)
    
    def get_technical_indicators(self, stock_codes):
        """获取技术指标数据"""
        def fetch_data():
            technical_data = {}
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
                except:
                    continue
            return pd.DataFrame.from_dict(technical_data, orient='index')
        return self.get_cached_data("technical_indicators", fetch_data)
    
    def filter_stocks_by_technical(self, stock_names, concept_data):
        """基于技术指标筛选股票"""
        print("开始技术指标筛选...")
        
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
            return []
        
        # 获取技术指标
        technical_data = self.get_technical_indicators(valid_stocks)
        
        # 筛选条件
        filtered_stocks = []
        for stock_name, stock_code in name_to_code.items():
            if stock_code in technical_data.index:
                tech_data = technical_data.loc[stock_code]
                
                # 技术筛选条件（可根据需要调整）
                conditions = [
                    tech_data.get('price_change', 0) < 5,  # 当日涨幅小于5%
                    tech_data.get('volume_ratio', 0) > 0.8,  # 量比大于0.8
                    tech_data.get('current_price', 0) > tech_data.get('ma5', 0),  # 股价在5日均线上
                    tech_data.get('current_price', 0) > 5,  # 股价高于5元（避免低价股）
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
        
        return filtered_stocks
    
    def filter_stocks_by_financial(self, stock_names):
        """基于财务指标筛选股票"""
        print("开始财务指标筛选...")
        
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
            return []
        
        # 获取财务指标
        financial_data = self.get_financial_indicators(valid_stocks)
        
        filtered_stocks = []
        for stock_name, stock_code in name_to_code.items():
            if stock_code in financial_data.index:
                fin_data = financial_data.loc[stock_code]
                
                # 财务筛选条件（可根据需要调整）
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
                except:
                    continue
        
        return filtered_stocks
    
    def comprehensive_filter(self, concept_data):
        """综合筛选股票"""
        stock_names = concept_data['成分股名称']
        print(f"开始筛选概念 '{concept_data['概念名称']}' 下的 {len(stock_names)} 只股票...")
        
        # 第一轮：技术指标筛选
        technically_filtered = self.filter_stocks_by_technical(stock_names, concept_data)
        
        # 第二轮：财务指标筛选（可选）
        financially_filtered = self.filter_stocks_by_financial(stock_names)
        
        # 综合筛选结果
        final_stocks = []
        for stock in technically_filtered:
            if stock['股票名称'] in financially_filtered or not financially_filtered:
                final_stocks.append(stock)
        
        # 按涨跌幅排序，取前5只
        final_stocks.sort(key=lambda x: abs(x['涨跌幅']), reverse=True)
        return final_stocks[:5]

class ConceptStockFilter:
    def __init__(self, concept_file):
        self.concept_file = concept_file
        self.stock_analyzer = stock_filter_tool()
        
    def load_concept_data(self):
        """加载概念数据"""
        with open(self.concept_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def filter_all_concepts(self):
        """筛选所有概念的股票"""
        concept_data = self.load_concept_data()
        all_recommendations = []
        
        print(f"开始处理 {concept_data['推荐概念总数']} 个推荐概念...")
        
        for concept in concept_data['推荐列表']:
            print(f"\n处理概念: {concept['概念名称']} (排名: {concept['排名']})")
            
            try:
                filtered_stocks = self.stock_analyzer.comprehensive_filter(concept)
                
                if filtered_stocks:
                    concept_recommendation = {
                        '概念名称': concept['概念名称'],
                        '概念排名': concept['排名'],
                        '涨跌幅': concept['涨跌幅(%)'],
                        '推荐股票': filtered_stocks
                    }
                    all_recommendations.append(concept_recommendation)
                    
                    print(f"  推荐 {len(filtered_stocks)} 只股票:")
                    for stock in filtered_stocks:
                        print(f"    {stock['股票名称']}: 价格{stock['当前价格']:.2f}, 涨幅{stock['涨跌幅']:.2f}%")
                else:
                    print(f"  该概念下无符合筛选条件的股票")
                    
            except Exception as e:
                print(f"  处理概念 {concept['概念名称']} 时出错: {e}")
                continue
        
        return all_recommendations
    
    def save_recommendations(self, recommendations, output_file=None):
        """保存推荐结果"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"stock_recommendations_{timestamp}.json"
        
        result = {
            "生成时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "推荐概念数量": len(recommendations),
            "推荐详情": recommendations
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"\n推荐结果已保存到: {output_file}")
        return output_file

# 使用示例
if __name__ == "__main__":
    # 初始化筛选器
    concept_file = "concept_stocks_recommendation_20251013_004800.json"  # 替换为您的实际文件路径
    filter_agent = ConceptStockFilter(concept_file)
    
    # 执行筛选
    recommendations = filter_agent.filter_all_concepts()
    
    # 保存结果
    if recommendations:
        output_file = filter_agent.save_recommendations(recommendations)
        print(f"\n共推荐 {len(recommendations)} 个概念下的股票")
    else:
        print("没有找到符合条件的推荐股票")