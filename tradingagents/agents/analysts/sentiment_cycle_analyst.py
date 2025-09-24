import logging
from datetime import datetime
from typing import Dict, List
from langchain.prompts import ChatPromptTemplate
from tradingagents.tools.market_tools import get_index_data, get_industry_data, get_market_breadth

logger = logging.getLogger(__name__)

class SentimentCycleAnalyst:
    def __init__(self, llm):
        self.llm = llm
        self.cycle_phases = [
            "冰点期/绝望期",
            "复苏期/酝酿期/启动期",
            "发酵期/上升期",
            "高潮期/疯狂期",
            "衰退期/出货期",
            "恐慌期/崩溃期"
        ]
        
    def analyze_market_sentiment(self, state: Dict) -> Dict:
        """分析大盘和行业情绪，判断当前情绪周期阶段"""
        logger.debug("📊 [情绪周期分析师] 开始分析市场情绪周期")
        
        # 获取必要数据
        index_code = state.get("index_code", "000001")  # 默认上证指数
        industry = state.get("industry", "")
        current_date = state.get("trade_date", datetime.now().strftime("%Y-%m-%d"))
        
        # 调用工具获取市场数据
        index_data = get_index_data(index_code, period="1m")  # 获取1个月数据
        industry_data = get_industry_data(industry) if industry else None
        breadth_data = get_market_breadth()  # 获取市场广度数据（涨停数、成交量等）
        
        # 构建提示词
        prompt = ChatPromptTemplate.from_messages([
            ("system", """
            你是一位专业的市场情绪分析师，擅长判断A股市场的情绪周期阶段。
            请根据提供的大盘数据、行业数据和市场广度数据，分析当前市场处于哪个情绪周期阶段。
            
            情绪周期阶段划分标准：
            1. 冰点期/绝望期：市场极度悲观，投资者信心低迷，涨停板数量稀少，几乎无热点和赚钱效应，个股普遍阴跌或横盘，成交量极低。
            2. 复苏期/酝酿期/启动期：市场逐步企稳，个别股票开始试探性涨停，部分资金尝试布局新题材，炸板股减少，市场人气缓慢恢复。
            3. 发酵期/上升期：出现新的领涨题材或龙头股，市场情绪升温，涨停板数量增多，赚钱效应明显，连板股数量增加。
            4. 高潮期/疯狂期：市场热度到达顶峰，龙头股连续涨停，跟风股群起响应，出现大面积涨停，但也可能伴随分化。
            5. 衰退期/出货期：领涨题材或龙头股开始见顶回调，市场情绪冷却，涨停封板率下降，高位股大幅下跌，资金流出明显。
            6. 恐慌期/崩溃期：市场情绪反转，抛压加大，高位股急速下跌，可能引发连锁反应，导致整个市场短期急挫。
            
            请结合以下数据进行分析：
            1. 大盘数据：{index_data}
            2. 行业数据：{industry_data}
            3. 市场广度数据：{breadth_data}
            
            分析结果需包含：
            - 当前情绪周期阶段判断及理由
            - 对应的操作策略建议
            - 适合的交易手法
            - 板块轮动可能性分析
            """),
            ("human", "请分析当前市场（{current_date}）的情绪周期阶段并给出操作建议")
        ])
        
        # 执行分析
        formatted_prompt = prompt.format_prompt(
            index_data=index_data,
            industry_data=industry_data,
            breadth_data=breadth_data,
            current_date=current_date
        )
        
        response = self.llm.invoke(formatted_prompt.to_messages())
        sentiment_analysis = response.content
        
        # 提取情绪周期阶段（用于后续交易决策）
        current_phase = self._extract_phase(sentiment_analysis)
        
        return {
            **state,
            "sentiment_analysis": sentiment_analysis,
            "current_sentiment_phase": current_phase,
            "messages": state.get("messages", []) + [{"role": "system", "content": sentiment_analysis}]
        }
    
    def _extract_phase(self, analysis: str) -> str:
        """从分析结果中提取当前情绪周期阶段"""
        for phase in self.cycle_phases:
            if phase in analysis:
                return phase
        return "未知阶段"