import akshare as ak
import adata
import pandas as pd
import numpy as np
import logging
import json  # 新增：用于JSON导出
from datetime import datetime, timedelta
# 移除：matplotlib相关导入（图表功能）
from typing import List, Dict, Optional, Tuple
from scipy import stats

# 配置日志（保留原逻辑）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("corrected_concept_analyzer.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CorrectedConceptAnalyzer")

#D:\stock_code\TradingAgents-CN-main\TradingAgents-CN-main\tradingagents\utils\concept_analyzer.py
class CorrectedConceptAnalyzer:
    def __init__(self, top_n: int = 10, 
                 rise_weight: float = 0.3, 
                 flow_weight: float = 0.3,
                 fundamental_weight: float = 0.2,
                 sentiment_weight: float = 0.2):
        """保留原初始化逻辑"""
        self.top_n = top_n
        self.rise_weight = rise_weight
        self.flow_weight = flow_weight
        self.fundamental_weight = fundamental_weight
        self.sentiment_weight = sentiment_weight
        
        # 数据存储（完全保留原定义）
        self.all_concepts = None  # 所有概念板块
        self.top_concepts = None  # 筛选出的热门概念
        self.concept_details = {}  # 概念详细数据（保留K线/分时数据获取，不影响其他逻辑）
        self.capital_flows = None  # 概念资金流向
        self.concept_stocks = {}  # 概念成分股（核心：用于后续JSON导出成分股名称）
        self.scored_concepts = None  # 评分后的概念
        self.time_series_indicators = {}  # 时间序列指标
    
    # ---------------------- 以下方法完全保留原逻辑 ----------------------
    def fetch_all_concepts(self) -> pd.DataFrame:
        """获取东方财富所有概念板块数据（原逻辑不变）"""
        try:
            logger.info("获取东方财富所有概念板块数据")
            self.all_concepts = ak.stock_board_concept_name_em()
            logger.info(f"成功获取{len(self.all_concepts)}个概念板块")
            return self.all_concepts
        except Exception as e:
            logger.error(f"获取概念板块数据失败: {str(e)}")
            raise
    
    def select_top_concepts(self, top_n: Optional[int] = None) -> pd.DataFrame:
        """选择前N个热门概念（原逻辑不变）"""
        if self.all_concepts is None:
            self.fetch_all_concepts()
            
        if top_n is None:
            top_n = self.top_n * 2  # 多获取一倍以便后续筛选
            
        # 按涨跌幅排序，选取前N个概念
        self.top_concepts = self.all_concepts.sort_values(by='涨跌幅', ascending=False).head(top_n)
        logger.info(f"已选择前{top_n}个热门概念")
        return self.top_concepts
    
    def fetch_concept_stocks(self, concept_code: str, concept_name: str) -> pd.DataFrame:
        """获取概念成分股列表（原逻辑不变，核心数据用于JSON导出）"""
        try:
            # 使用akshare获取概念成分股
            stocks = ak.stock_board_concept_cons_em(symbol=concept_name)
            logger.debug(f"获取概念{concept_name}({concept_code})的成分股数量: {len(stocks)}")
            return stocks
        except Exception as e:
            logger.warning(f"获取概念{concept_name}({concept_code})的成分股失败: {str(e)}")
            return pd.DataFrame(columns=['代码', '名称', '涨跌幅', '现价', '涨跌额', '成交量'])
    
    def fetch_concept_details(self, concept_codes: List[str], concept_names: List[str]) -> Dict:
        """获取概念的详细行情数据（保留原逻辑，不删除K线/分时数据获取）"""
        try:
            logger.info(f"开始获取{len(concept_codes)}个概念的详细数据")
            
            for idx, (concept_code, concept_name) in enumerate(zip(concept_codes, concept_names)):
                # 进度提示
                if (idx + 1) % 5 == 0:
                    logger.info(f"已获取{idx + 1}/{len(concept_codes)}个概念数据")
                
                # 获取概念成分股（核心：存入self.concept_stocks，用于后续JSON导出）
                stocks = self.fetch_concept_stocks(concept_code, concept_name)
                self.concept_stocks[concept_code] = stocks
                
                # 保留原K线/分时/实时数据获取（不影响功能，仅不使用可视化）
                try:
                    kline_data = adata.stock.market.get_market_concept_east(
                        index_code=concept_code, 
                        k_type=1  # 1.日K
                    )
                except Exception as e:
                    logger.warning(f"获取概念{concept_code}的K线数据失败: {str(e)}")
                    kline_data = None
                
                try:
                    minute_data = adata.stock.market.get_market_concept_min_east(
                        index_code=concept_code
                    )
                except Exception as e:
                    logger.warning(f"获取概念{concept_code}的分时数据失败: {str(e)}")
                    minute_data = None
                
                try:
                    realtime_data = adata.stock.market.get_market_concept_current_east(
                        index_code=concept_code
                    )
                except Exception as e:
                    logger.warning(f"获取概念{concept_code}的实时数据失败: {str(e)}")
                    realtime_data = None
                
                # 存储数据（保留原结构）
                self.concept_details[concept_code] = {
                    "kline": kline_data,
                    "minute": minute_data,
                    "realtime": realtime_data
                }
            
            logger.info(f"完成{len(concept_codes)}个概念的详细数据获取")
            return self.concept_details
        except Exception as e:
            logger.error(f"获取概念详细数据时发生错误: {str(e)}")
            raise
    
    def fetch_capital_flows(self, days_type: int = 5) -> pd.DataFrame:
        """获取概念资金流向数据（原逻辑不变）"""
        try:
            logger.info(f"获取所有概念近{days_type}天的资金流向数据")
            self.capital_flows = adata.stock.market.all_capital_flow_east(days_type=days_type)
            
            # 重命名列以便于理解
            self.capital_flows.rename(columns={
                "index_code": "概念代码",
                "index_name": "概念名称",
                "change_pct": "近N日涨跌幅(%)",
                "main_net_inflow": "主力资金净流入(元)",
                "main_net_inflow_rate": "主力资金净流入占比(%)",
                "max_net_inflow": "特大单净流入(元)",
                "lg_net_inflow": "大单净流入(元)",
                "mid_net_inflow": "中单净流入(元)",
                "sm_net_inflow": "小单净流入(元)"
            }, inplace=True)
            
            logger.info(f"成功获取{len(self.capital_flows)}个概念的资金流向数据")
            return self.capital_flows
        except Exception as e:
            logger.error(f"获取资金流向数据失败: {str(e)}")
            raise
    
    def calculate_fundamental_indicators(self, concept_code: str) -> Dict:
        """计算概念的基本面指标（原逻辑不变）"""
        try:
            stocks = self.concept_stocks.get(concept_code, pd.DataFrame())
            if stocks.empty or '代码' not in stocks.columns:
                return {"平均市盈率": None, "行业集中度": None, "行业分布": None}
            
            pe_ratios = []
            industry_counts = {}
            sample_stocks = stocks.head(10)  # 取前10只股票作为样本
            
            for _, stock in sample_stocks.iterrows():
                stock_code = stock['代码']
                try:
                    stock_data = ak.stock_individual_info_em(symbol=stock_code)
                    if '市盈率' in stock_data.index:
                        pe = stock_data.loc['市盈率']
                        if isinstance(pe, str):
                            pe = pe.replace('%', '').replace(',', '')
                            if pe.replace('.', '', 1).isdigit():
                                pe_value = float(pe)
                                if pe_value > 0:
                                    pe_ratios.append(pe_value)
                    
                    if '所属行业' in stock_data.index:
                        industry = stock_data.loc['所属行业']
                        if isinstance(industry, str) and industry.strip():
                            industry_counts[industry] = industry_counts.get(industry, 0) + 1
                except Exception as e:
                    logger.debug(f"获取股票{stock_code}数据失败: {str(e)}")
                    continue
            
            # 计算平均市盈率（去除极端值）
            avg_pe = None
            if pe_ratios:
                pe_ratios_sorted = sorted(pe_ratios)
                trim_ratio = 0.1
                trim_count = int(len(pe_ratios_sorted) * trim_ratio)
                trimmed_pe = pe_ratios_sorted[trim_count:-trim_count] if len(pe_ratios_sorted) > 2 else pe_ratios_sorted
                avg_pe = sum(trimmed_pe) / len(trimmed_pe) if trimmed_pe else None
            
            # 计算行业集中度
            industry_concentration = None
            industry_distribution = None
            if industry_counts:
                total = sum(industry_counts.values())
                industry_distribution = {k: v/total for k, v in industry_counts.items()}
                hhi = sum((v/total)**2 for v in industry_counts.values())
                industry_concentration = hhi
            
            return {
                "平均市盈率": avg_pe,
                "行业集中度": industry_concentration,
                "行业分布": industry_distribution
            }
        except Exception as e:
            logger.error(f"计算概念{concept_code}基本面指标失败: {str(e)}")
            return {"平均市盈率": None, "行业集中度": None, "行业分布": None}
    
    def calculate_sentiment_indicators(self, concept_code: str, concept_name: str) -> Dict:
        """计算市场情绪指标（原逻辑不变）"""
        try:
            ths_hot_concepts = adata.sentiment.hot.hot_concept_20_ths()
            hot_rank = None
            if not ths_hot_concepts.empty and 'concept_name' in ths_hot_concepts.columns:
                mask = ths_hot_concepts['concept_name'].str.contains(concept_name, na=False)
                if mask.any():
                    hot_entry = ths_hot_concepts[mask].iloc[0]
                    hot_rank = hot_entry['rank']
            
            # 提取大单/小单资金比例
            large_small_ratio = None
            if self.capital_flows is not None:
                flow_mask = (self.capital_flows['概念代码'] == concept_code) | \
                           (self.capital_flows['概念名称'].str.contains(concept_name, na=False))
                if flow_mask.any():
                    flow_data = self.capital_flows[flow_mask].iloc[0]
                    if 'lg_net_inflow' in flow_data and 'sm_net_inflow' in flow_data:
                        large = abs(flow_data['lg_net_inflow'])
                        small = abs(flow_data['sm_net_inflow'])
                        if large + small > 0:
                            large_small_ratio = large / (large + small)
            
            # 计算热度标签得分
            hot_tag_score = 0
            if not ths_hot_concepts.empty and 'hot_tag' in ths_hot_concepts.columns:
                mask = ths_hot_concepts['concept_name'].str.contains(concept_name, na=False)
                if mask.any():
                    hot_entry = ths_hot_concepts[mask].iloc[0]
                    hot_tag = str(hot_entry.get('hot_tag', ''))
                    if '连续' in hot_tag and '上榜' in hot_tag:
                        for s in hot_tag.split():
                            if s.endswith('天'):
                                try:
                                    days = int(s.replace('天', ''))
                                    hot_tag_score = min(days / 30, 1)
                                except:
                                    pass
            
            # 综合情绪得分
            sentiment_score = 0
            if hot_rank:
                sentiment_score += (20 - hot_rank) / 20
            if large_small_ratio:
                sentiment_score += large_small_ratio
            sentiment_score += hot_tag_score
            sentiment_score = sentiment_score / 3  # 归一化到0-1
            
            return {
                "热门榜排名": hot_rank,
                "大单资金占比": large_small_ratio,
                "连续上榜得分": hot_tag_score,
                "情绪得分": sentiment_score
            }
        except Exception as e:
            logger.warning(f"计算概念{concept_name}情绪指标失败: {str(e)}")
            return {
                "热门榜排名": None,
                "大单资金占比": None,
                "连续上榜得分": 0,
                "情绪得分": 0.5
            }
    
    def analyze_time_series(self, concept_code: str) -> Dict:
        """时间序列分析（原逻辑不变，依赖concept_details中的K线数据）"""
        try:
            concept_data = self.concept_details.get(concept_code, {})
            kline_data = concept_data.get('kline')
            
            if kline_data is None or kline_data.empty:
                return {
                    "连续上涨天数": 0,
                    "涨跌幅斜率": 0,
                    "热度加速率": 0,
                    "近期趋势": "未知",
                    "波动率": 0,
                    "MA5_vs_MA20": 0
                }
            
            # 处理交易日期
            if 'trade_date' in kline_data.columns:
                kline_data['trade_date'] = pd.to_datetime(kline_data['trade_date'])
                kline_data = kline_data.sort_values('trade_date')
            else:
                logger.warning(f"概念{concept_code}的K线数据没有trade_date列")
                return {
                    "连续上涨天数": 0,
                    "涨跌幅斜率": 0,
                    "热度加速率": 0,
                    "近期趋势": "数据格式错误",
                    "波动率": 0,
                    "MA5_vs_MA20": 0
                }
            
            # 计算连续上涨天数
            up_days = 0
            if 'close' in kline_data.columns and len(kline_data) > 1:
                for i in range(len(kline_data)-1, 0, -1):
                    if kline_data.iloc[i]['close'] > kline_data.iloc[i-1]['close']:
                        up_days += 1
                    else:
                        break
            
            # 趋势分析
            recent_data = kline_data.tail(10)
            if len(recent_data) < 5:
                return {
                    "连续上涨天数": up_days,
                    "涨跌幅斜率": 0,
                    "热度加速率": 0,
                    "近期趋势": "数据不足",
                    "波动率": 0,
                    "MA5_vs_MA20": 0
                }
            
            # 涨跌幅斜率
            slope = 0
            if 'change_pct' in recent_data.columns:
                x = np.arange(len(recent_data))
                y = recent_data['change_pct'].values
                slope, _, _, _, _ = stats.linregress(x, y)
            
            # 热度加速率
            acceleration = 0
            if 'change_pct' in recent_data.columns and len(recent_data) >= 3:
                y = recent_data['change_pct'].values
                acceleration = (y[-1] - 2*y[-2] + y[-3]) / 1
            
            # 近期趋势
            trend = "上涨" if slope > 0 else "下跌" if slope < 0 else "横盘"
            
            # 波动率
            volatility = 0
            if 'change_pct' in recent_data.columns:
                volatility = np.std(recent_data['change_pct'])
            
            # 均线差
            ma_diff_pct = 0
            if 'close' in kline_data.columns and len(kline_data) >= 20:
                ma5 = kline_data['close'].tail(5).mean()
                ma20 = kline_data['close'].tail(20).mean()
                ma_diff_pct = (ma5 - ma20) / ma20 * 100 if ma20 != 0 else 0
            
            result = {
                "连续上涨天数": up_days,
                "涨跌幅斜率": slope,
                "热度加速率": acceleration,
                "近期趋势": trend,
                "波动率": volatility,
                "MA5_vs_MA20": ma_diff_pct
            }
            
            self.time_series_indicators[concept_code] = result
            return result
        except Exception as e:
            logger.error(f"概念{concept_code}时间序列分析失败: {str(e)}")
            return {
                "连续上涨天数": 0,
                "涨跌幅斜率": 0,
                "热度加速率": 0,
                "近期趋势": "分析失败",
                "波动率": 0,
                "MA5_vs_MA20": 0
            }
    
    def calculate_scores(self) -> pd.DataFrame:
        """计算概念的综合得分（原逻辑不变）"""
        if self.top_concepts is None:
            self.select_top_concepts()
            
        if self.capital_flows is None:
            self.fetch_capital_flows()
            
        # 合并数据
        merged_data = pd.merge(
            self.top_concepts, 
            self.capital_flows,
            left_on="板块代码",
            right_on="概念代码",
            how="left"
        )
        
        # 添加分析列
        merged_data["平均市盈率"] = None
        merged_data["行业集中度"] = None
        merged_data["情绪得分"] = None
        merged_data["连续上涨天数"] = None
        merged_data["涨跌幅斜率"] = None
        merged_data["MA5_vs_MA20"] = None
        merged_data["综合得分"] = 0
        
        # 计算多维度指标
        for idx, row in merged_data.iterrows():
            concept_code = row["板块代码"]
            concept_name = row["板块名称"]
            
            if pd.isna(concept_code) or pd.isna(concept_name):
                continue
            
            # 基本面指标
            fundamental = self.calculate_fundamental_indicators(concept_code)
            merged_data.at[idx, "平均市盈率"] = fundamental["平均市盈率"]
            merged_data.at[idx, "行业集中度"] = fundamental["行业集中度"]
            
            # 情绪指标
            sentiment = self.calculate_sentiment_indicators(concept_code, concept_name)
            merged_data.at[idx, "情绪得分"] = sentiment["情绪得分"]
            
            # 时间序列指标
            time_series = self.analyze_time_series(concept_code)
            merged_data.at[idx, "连续上涨天数"] = time_series["连续上涨天数"]
            merged_data.at[idx, "涨跌幅斜率"] = time_series["涨跌幅斜率"]
            merged_data.at[idx, "MA5_vs_MA20"] = time_series["MA5_vs_MA20"]
        
        # 过滤有效数据
        valid_mask = (
            ~merged_data["涨跌幅"].isna() & 
            ~merged_data["主力资金净流入(元)"].isna() &
            ~merged_data["情绪得分"].isna()
        )
        merged_data = merged_data[valid_mask]
        logger.info(f"有效概念数量: {len(merged_data)}")
        
        if merged_data.empty:
            logger.warning("没有足够的有效概念数据进行分析")
            return pd.DataFrame()
        
        # 标准化指标
        max_rise = merged_data["涨跌幅"].abs().max()
        merged_data["标准化涨跌幅"] = merged_data["涨跌幅"] / max_rise if max_rise != 0 else 0
        
        max_flow = merged_data["主力资金净流入(元)"].abs().max()
        merged_data["标准化资金流向"] = merged_data["主力资金净流入(元)"] / max_flow if max_flow != 0 else 0
        
        # 市盈率标准化
        merged_data["标准化市盈率"] = 0
        valid_pe_mask = ~merged_data["平均市盈率"].isna() & (merged_data["平均市盈率"] > 0)
        if valid_pe_mask.any():
            max_pe = merged_data.loc[valid_pe_mask, "平均市盈率"].max()
            merged_data.loc[valid_pe_mask, "标准化市盈率"] = 1 / (merged_data.loc[valid_pe_mask, "平均市盈率"] / max_pe)
        
        # 时间序列斜率标准化
        max_slope = merged_data["涨跌幅斜率"].abs().max()
        merged_data["标准化斜率"] = merged_data["涨跌幅斜率"] / max_slope if max_slope != 0 else 0
        
        # 计算综合得分
        merged_data["综合得分"] = (
            merged_data["标准化涨跌幅"] * self.rise_weight + 
            merged_data["标准化资金流向"] * self.flow_weight +
            merged_data["标准化市盈率"] * self.fundamental_weight +
            merged_data["情绪得分"] * self.sentiment_weight +
            merged_data["标准化斜率"] * 0.1  # 额外斜率权重
        )
        
        # 排序
        self.scored_concepts = merged_data.sort_values(by="综合得分", ascending=False)
        return self.scored_concepts
    
    def get_buy_candidates(self) -> pd.DataFrame:
        """获取适合买入的概念候选列表（原逻辑不变）"""
        if self.scored_concepts is None:
            self.calculate_scores()
            
        if self.scored_concepts.empty:
            return pd.DataFrame()
            
        # 选取前N个概念
        candidates = self.scored_concepts.head(self.top_n).copy()
        
        # 添加最新价格信息
        latest_prices = []
        for _, row in candidates.iterrows():
            code = row["板块代码"]
            if code in self.concept_details and self.concept_details[code]["realtime"] is not None:
                realtime_df = self.concept_details[code]["realtime"]
                if not realtime_df.empty and 'price' in realtime_df.columns:
                    latest_prices.append(realtime_df["price"].iloc[0])
                    continue
            latest_prices.append(None)
            
        candidates["最新价格"] = latest_prices
        candidates["更新时间"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        return candidates
    
    # ---------------------- 以下是核心修改：1. 移除可视化方法 2. 新增JSON导出 ----------------------
    # 移除：visualize_time_series 方法（图表功能）
    # 移除：visualize_top_concepts 方法（图表功能）
    
    def export_results(self, filename: Optional[str] = None) -> None:
        """保留原CSV导出功能（不删除，兼容原需求）"""
        if self.scored_concepts is None or self.scored_concepts.empty:
            logger.warning("没有评分后的概念数据，无法导出")
            return
            
        if filename is None:
            filename = f'corrected_concept_analysis_results_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            
        export_columns = [
            "板块名称", "板块代码", "涨跌幅", "近N日涨跌幅(%)",
            "主力资金净流入(元)", "主力资金净流入占比(%)",
            "平均市盈率", "行业集中度", "情绪得分",
            "连续上涨天数", "涨跌幅斜率", "MA5_vs_MA20",
            "标准化涨跌幅", "标准化资金流向", "标准化市盈率",
            "综合得分", "更新时间"
        ]
        export_columns = [col for col in export_columns if col in self.scored_concepts.columns]
        
        self.scored_concepts[export_columns].to_csv(filename, index=False, encoding='utf-8-sig')
        logger.info(f"分析结果已导出到CSV文件: {filename}")
    
    # 新增：将「推荐概念+对应成分股名称」导出为JSON
    def export_concept_stocks_to_json(self, buy_candidates: pd.DataFrame, filename: Optional[str] = None) -> None:
        """
        导出格式说明：
        {
            "分析时间": "2025-xx-xx xx:xx:xx",
            "推荐概念总数": 10,
            "推荐列表": [
                {
                    "排名": 1,
                    "概念名称": "XXX",
                    "概念代码": "XXXXXX",
                    "涨跌幅(%)": 5.23,
                    "主力资金净流入(元)": 1234567890,
                    "平均市盈率": 25.6,
                    "情绪得分": 0.85,
                    "最新价格": 100.5,
                    "成分股名称": ["股票A", "股票B", "股票C", ...]
                },
                ...
            ]
        }
        """
        if buy_candidates.empty:
            logger.warning("没有推荐概念数据，无法导出JSON")
            return
        
        # 生成带时间戳的默认文件名
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"concept_stocks_recommendation_{timestamp}.json"
        
        # 构建JSON数据
        json_data = {
            "分析时间": buy_candidates["更新时间"].iloc[0],
            "推荐概念总数": len(buy_candidates),
            "推荐列表": []
        }
        
        # 遍历每个推荐概念，关联成分股名称
        for rank, (_, row) in enumerate(buy_candidates.iterrows(), 1):
            concept_code = row["板块代码"]
            concept_name = row["板块名称"]
            
            # 从self.concept_stocks中获取当前概念的成分股名称列表
            stocks_df = self.concept_stocks.get(concept_code, pd.DataFrame())
            stock_names = stocks_df["名称"].tolist() if "名称" in stocks_df.columns else []
            
            # 整理当前概念的核心信息（处理空值）
            concept_info = {
                "排名": rank,
                "概念名称": concept_name,
                "概念代码": concept_code,
                "涨跌幅(%)": round(row["涨跌幅"], 2) if not pd.isna(row["涨跌幅"]) else None,
                "主力资金净流入(元)": int(row["主力资金净流入(元)"]) if not pd.isna(row["主力资金净流入(元)"]) else None,
                "平均市盈率": round(row["平均市盈率"], 2) if not pd.isna(row["平均市盈率"]) else None,
                "情绪得分": round(row["情绪得分"], 4) if not pd.isna(row["情绪得分"]) else None,
                "最新价格": round(row["最新价格"], 2) if not pd.isna(row["最新价格"]) else None,
                "成分股名称": stock_names  # 核心：导出成分股名称列表
            }
            
            json_data["推荐列表"].append(concept_info)
        
        # 写入JSON文件（支持中文，格式化输出）
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            logger.info(f"推荐概念及成分股已导出到JSON文件: {filename}")
        except Exception as e:
            logger.error(f"导出JSON文件失败: {str(e)}")
            raise
    
    def run(self, initial_top_n: int = 30, days_type: int = 5) -> pd.DataFrame:
        """运行完整流程（修改：移除可视化调用，新增JSON导出）"""
        try:
            logger.info("====== 开始修正版概念板块量化分析 ======")
            
            # 1. 获取所有概念并筛选热门
            self.fetch_all_concepts()
            self.select_top_concepts(initial_top_n)
            
            # 2. 获取概念详细数据（含成分股）
            if '板块代码' in self.top_concepts.columns and '板块名称' in self.top_concepts.columns:
                concept_codes = self.top_concepts["板块代码"].tolist()
                concept_names = self.top_concepts["板块名称"].tolist()
                self.fetch_concept_details(concept_codes, concept_names)
            else:
                logger.error("概念数据缺少必要的列(板块代码或板块名称)")
                return pd.DataFrame()
            
            # 3. 获取资金流向
            self.fetch_capital_flows(days_type)
            
            # 4. 计算综合得分
            self.calculate_scores()
            
            # 5. 获取买入候选
            candidates = self.get_buy_candidates()
            
            # 修改点1：移除可视化调用（原self.visualize_top_concepts(...)）
            # 修改点2：新增JSON导出（调用新增的方法）
            if not candidates.empty:
                self.export_concept_stocks_to_json(candidates)
            
            # 保留原CSV导出
            self.export_results()
            
            logger.info("====== 修正版概念板块量化分析完成 ======")
            return candidates
        except Exception as e:
            logger.error(f"分析过程中发生错误: {str(e)}")
            raise


if __name__ == "__main__":
    # 完全保留原初始化和运行逻辑
    analyzer = CorrectedConceptAnalyzer(
        top_n=10,            # 最终选取10个概念
        rise_weight=0.3,     # 涨跌幅权重
        flow_weight=0.3,     # 资金流向权重
        fundamental_weight=0.2,  # 基本面指标权重
        sentiment_weight=0.2    # 市场情绪权重
    )
    
    # 运行分析流程（参数不变）
    buy_candidates = analyzer.run(initial_top_n=30, days_type=5)
    
    # 保留原控制台打印结果
    if buy_candidates is not None and not buy_candidates.empty:
        print("\n====== 适合买入的概念板块推荐 ======")
        print(f"分析时间: {buy_candidates['更新时间'].iloc[0]}")
        print("-" * 150)
        print(f"{'排名':<5} {'概念名称':<20} {'代码':<10} {'涨跌幅(%)':<12} {'资金净流入(元)':<18} {'平均市盈率':<12} {'情绪得分':<10} {'连续上涨天数':<12} {'综合得分':<10}")
        print("-" * 150)
        
        for i, (_, row) in enumerate(buy_candidates.iterrows(), 1):
            print(f"{i:<5} {row['板块名称']:<20} {row['板块代码']:<10} {row['涨跌幅']:>10.2f}% {row['主力资金净流入(元)']:>16,.0f} {row['平均市盈率'] if pd.notna(row['平均市盈率']) else 'N/A':>10} {row['情绪得分']:>10.4f} {row['连续上涨天数']:>12} {row['综合得分']:>10.4f}")