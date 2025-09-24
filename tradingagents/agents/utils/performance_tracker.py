import pandas as pd
from datetime import datetime
from typing import Dict, List

class PerformanceTracker:
    def __init__(self):
        self.initial_capital = 100000  # 初始资金
        self.daily_returns = []
        self.total_profit = 0
        self.winning_rate = 0
        self.max_drawdown = 0
        
    def update_performance(self, portfolio: Dict, date: str, trade_history: List[Dict]):
        """更新绩效指标"""
        # 计算当前总资产
        current_assets = self.initial_capital
        
        # 计算持仓市值
        for code, pos in portfolio.items():
            from tradingagents.tools.trade_tools import fetch_stock_data
            current_price = fetch_stock_data(code, period="1d")["close"].iloc[-1]
            current_assets += (current_price * pos["shares"]) - pos["total_cost"]
        
        # 计算总利润
        self.total_profit = current_assets - self.initial_capital
        
        # 计算胜率
        winning_trades = [t for t in trade_history if t["action"] == "sell" and t.get("profit", 0) > 0]
        total_sells = len([t for t in trade_history if t["action"] == "sell"])
        self.winning_rate = len(winning_trades) / total_sells if total_sells > 0 else 0
        
        # 记录每日收益
        self.daily_returns.append({
            "date": date,
            "total_assets": current_assets,
            "profit": self.total_profit,
            "profit_ratio": (self.total_profit / self.initial_capital) * 100
        })
        
        # 计算最大回撤（简化版）
        if self.daily_returns:
            df = pd.DataFrame(self.daily_returns)
            cumulative_max = df['total_assets'].cummax()
            drawdown = (df['total_assets'] - cumulative_max) / cumulative_max
            self.max_drawdown = drawdown.min() * 100 if not drawdown.empty else 0
    
    def get_summary(self) -> Dict:
        """获取绩效摘要"""
        return {
            "initial_capital": self.initial_capital,
            "total_assets": self.daily_returns[-1]["total_assets"] if self.daily_returns else self.initial_capital,
            "total_profit": self.total_profit,
            "total_profit_ratio": (self.total_profit / self.initial_capital) * 100 if self.initial_capital > 0 else 0,
            "winning_rate": self.winning_rate * 100,
            "max_drawdown": self.max_drawdown,
            "trade_days": len(self.daily_returns)
        }