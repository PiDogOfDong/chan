import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional
from tradingagents.tools.trade_tools import fetch_stock_data, get_eligible_stocks
from tradingagents.utils.performance_tracker import PerformanceTracker

logger = logging.getLogger(__name__)

class TradeExecutor:
    def __init__(self):
        self.portfolio = {}  # 持仓: {股票代码: {数量: ..., 买入价: ..., 买入时间: ...}}
        self.performance_tracker = PerformanceTracker()
        self.trade_history = []  # 交易历史
    
    def execute_strategy(self, state: Dict) -> Dict:
        """根据情绪周期阶段执行相应的交易策略"""
        logger.debug("💹 [交易执行器] 开始执行交易策略")
        
        # 获取必要参数
        current_phase = state.get("current_sentiment_phase", "未知阶段")
        stock_pool = state.get("stock_pool", [])
        capital = state.get("capital", 100000)  # 初始资金
        current_date = state.get("trade_date", datetime.now().strftime("%Y-%m-%d"))
        
        # 根据情绪周期获取符合条件的股票
        eligible_stocks = self._filter_stocks_by_phase(
            current_phase, 
            stock_pool if stock_pool else get_eligible_stocks(state.get("industry", ""))
        )
        
        # 执行交易
        if eligible_stocks:
            # 卖出操作
            self._execute_sell_orders(current_phase, current_date)
            
            # 买入操作
            self._execute_buy_orders(current_phase, eligible_stocks, capital, current_date)
        
        # 更新绩效
        self.performance_tracker.update_performance(
            self.portfolio, 
            current_date,
            self.trade_history
        )
        
        return {
            **state,
            "portfolio": self.portfolio,
            "trade_history": self.trade_history,
            "performance_summary": self.performance_tracker.get_summary()
        }
    
    def _filter_stocks_by_phase(self, phase: str, stock_pool: List[str]) -> List[Dict]:
        """根据情绪周期阶段筛选股票"""
        filtered = []
        for stock in stock_pool:
            try:
                data = fetch_stock_data(stock, period="14d")  # 获取14天数据
                if self._is_stock_eligible(phase, data):
                    filtered.append({
                        "code": stock,
                        "data": data,
                        "score": self._score_stock(phase, data)
                    })
            except Exception as e:
                logger.error(f"筛选股票 {stock} 时出错: {str(e)}")
        
        # 按分数排序，取前5名
        return sorted(filtered, key=lambda x: x["score"], reverse=True)[:5]
    
    def _is_stock_eligible(self, phase: str, stock_data: pd.DataFrame) -> bool:
        """判断股票是否符合当前阶段的选股标准"""
        # 这里实现具体的选股逻辑，根据不同情绪周期阶段
        if phase in ["冰点期/绝望期", "恐慌期/崩溃期"]:
            # 超跌质优股：低市盈率、低市净率、近期跌幅大
            if len(stock_data) < 10:
                return False
            recent_return = (stock_data['close'].iloc[-1] / stock_data['close'].iloc[-10] - 1) * 100
            return recent_return < -10  # 近10日跌幅超过10%
            
        elif phase in ["复苏期/酝酿期/启动期"]:
            # 首板或低位启动股
            if 'is_first_board' in stock_data.columns:
                return stock_data['is_first_board'].iloc[-1]
            return False
            
        elif phase == "发酵期/上升期":
            # 趋势良好的龙头股
            if len(stock_data) < 5:
                return False
            # 连续上涨且均线多头排列
            return all(stock_data['close'].iloc[-i] < stock_data['close'].iloc[-i+1] for i in range(1, 5))
            
        # 其他阶段的选股逻辑...
        return True
    
    def _score_stock(self, phase: str, stock_data: pd.DataFrame) -> float:
        """给股票打分，用于排序"""
        # 实现具体的打分逻辑
        return 0.0  # 示例返回值
    
    def _execute_buy_orders(self, phase: str, eligible_stocks: List[Dict], capital: float, date: str):
        """执行买入操作"""
        if not eligible_stocks:
            return
            
        # 根据不同阶段确定仓位
        position_sizes = {
            "冰点期/绝望期": 0.1,  # 10%仓位
            "复苏期/酝酿期/启动期": 0.3,  # 30%仓位
            "发酵期/上升期": 0.6,  # 60%仓位
            "高潮期/疯狂期": 0.4,  # 40%仓位
            "衰退期/出货期": 0.2,  # 20%仓位
            "恐慌期/崩溃期": 0.1   # 10%仓位
        }
        
        position_size = position_sizes.get(phase, 0.2)
        invest_amount = capital * position_size
        stock_count = len(eligible_stocks)
        
        if stock_count == 0 or invest_amount <= 0:
            return
            
        # 平均分配资金
        per_stock_amount = invest_amount / stock_count
        
        for stock in eligible_stocks:
            code = stock["code"]
            latest_price = stock["data"]["close"].iloc[-1]
            
            # 计算可购买数量
            shares = int(per_stock_amount / latest_price / 100) * 100  # 按100股整数倍
            
            if shares > 0 and code not in self.portfolio:
                # 执行买入
                total_cost = shares * latest_price
                self.portfolio[code] = {
                    "shares": shares,
                    "buy_price": latest_price,
                    "buy_date": date,
                    "total_cost": total_cost
                }
                
                self.trade_history.append({
                    "date": date,
                    "code": code,
                    "action": "buy",
                    "shares": shares,
                    "price": latest_price,
                    "amount": total_cost
                })
                
                logger.info(f"买入 {code}: {shares}股, 价格: {latest_price}, 总成本: {total_cost}")
    
    def _execute_sell_orders(self, phase: str, date: str):
        """执行卖出操作"""
        if not self.portfolio:
            return
            
        # 卖出逻辑：根据阶段和止盈止损条件
        sell_candidates = []
        
        for code, pos in self.portfolio.items():
            stock_data = fetch_stock_data(code, period="1d")
            current_price = stock_data["close"].iloc[-1]
            profit_ratio = (current_price - pos["buy_price"]) / pos["buy_price"] * 100
            
            # 止盈条件：盈利超过20%
            if profit_ratio >= 20:
                sell_candidates.append(code)
            
            # 止损条件：亏损超过10%
            if profit_ratio <= -10:
                sell_candidates.append(code)
                
            # 阶段特定卖出条件
            if phase in ["高潮期/疯狂期", "衰退期/出货期"]:
                # 这些阶段倾向于卖出更多持仓
                sell_candidates.append(code)
        
        # 执行卖出
        for code in sell_candidates:
            if code in self.portfolio:
                pos = self.portfolio[code]
                current_price = fetch_stock_data(code, period="1d")["close"].iloc[-1]
                total_revenue = pos["shares"] * current_price
                profit = total_revenue - pos["total_cost"]
                
                self.trade_history.append({
                    "date": date,
                    "code": code,
                    "action": "sell",
                    "shares": pos["shares"],
                    "price": current_price,
                    "amount": total_revenue,
                    "profit": profit
                })
                
                logger.info(f"卖出 {code}: {pos['shares']}股, 价格: {current_price}, 总收入: {total_revenue}, 利润: {profit}")
                del self.portfolio[code]