"""大盘行情分析师，负责研判市场整体行情和情绪周期"""
# 导入分析模块日志装饰器（新增此行）
from tradingagents.utils.tool_logging import log_analyst_module
# 导入日志系统（确保已有此行，若无则添加）
from tradingagents.utils.logging_init import get_logger
logger = get_logger("default")

# 新增导入：从langchain.agents导入必要的函数
from langchain.agents import create_react_agent, AgentExecutor
from langchain import hub
from langchain_core.tools import BaseTool

def create_market_trend_analyst(llm, toolkit):
    """创建大盘行情分析师角色"""
    @log_analyst_module("market_trend")
    def market_trend_analyst_node(state):
        logger.debug(f"📊 [DEBUG] ===== 大盘行情分析师节点开始 =====")
        
        current_date = state["trade_date"]
        # 转换日期格式为YYYYMMDD用于评分接口
        score_date = current_date.replace("-", "")
        
        logger.debug(f"📊 [DEBUG] 分析日期: {current_date}")

        if toolkit.config["online_tools"]:            
            # 创建大盘分析工具集
            class MarketTrendTool(BaseTool):
                name: str = "get_market_trend_data"
                description: str = f"获取{current_date}大盘行情数据，包括成交额、涨跌分布、市场评分等"

                def _run(self, query: str = "") -> str:
                    try:

                        
                        # 通过toolkit调用工具函数获取数据
                        turnover = toolkit.get_market_turnover.invoke({"dummy": ""})  # 占位参数
                        distribution = toolkit.get_market_distribution.invoke({"dummy": ""})  # 占位参数
                        score = toolkit.get_market_score.invoke({"date": score_date})  # 必须传date
                        sectors = toolkit.get_favored_sectors.invoke({"dummy": ""})  # 补充占位参数调用
                        fund_flow = toolkit.get_sector_fund_flow.invoke({"dummy": ""})  # 补充占位参数调用
                        sse_data = toolkit.get_SSE_datas.invoke({"dummy": ""})  # 补充占位参数调用

                        return f"""【市场全景数据】
{turnover}

{distribution}

{score}

{sectors}

{fund_flow}

{sse_data}
"""
                    except Exception as e:
                        return f"获取大盘数据失败: {str(e)}"

            tools = [MarketTrendTool()]
            query = f"""请对{current_date}的A股大盘行情进行全面研判，步骤如下：

1. 使用get_market_trend_data工具获取完整市场数据
2. 基于数据判断当前市场处于以下哪个情绪周期阶段：
   - 冰点期/绝望期
   - 复苏期/酝酿期/启动期
   - 发酵期/上升期
   - 高潮期/疯狂期
   - 衰退期/出货期
   - 恐慌期/崩溃期
3. 分析当前属于哪种行情类型（震荡行情/上升趋势/下降趋势）
4. 结合板块轮动规律，判断当前主导板块和资金流向
5. 基于以上分析给出具体操作策略建议

报告格式要求：
## 一、市场概况
## 二、情绪周期判断
- 当前阶段：[具体阶段]
- 判断依据：[详细数据支撑]
## 三、行情类型分析
## 四、板块轮动观察
## 五、操作策略建议
- 仓位建议：[具体仓位比例]
- 核心手法：[对应操作手法]
- 风险提示：[主要风险点]

分析必须基于工具获取的真实数据，每个判断都要有明确的数据支撑，操作建议要具体可行。"""

            try:
                # 创建分析Agent - 使用与您正常代码相同的模式
                prompt = hub.pull("hwchase17/react")
                agent = create_react_agent(llm, tools, prompt)

                agent_executor = AgentExecutor(
                    agent=agent,
                    tools=tools,
                    verbose=True,
                    handle_parsing_errors=True,
                    max_iterations=15,
                    max_execution_time=300
                )

                logger.debug(f"📊 [DEBUG] 执行大盘行情分析...")
                result = agent_executor.invoke({'input': query})
                report = result['output']
                logger.info(f"📊 [大盘行情分析师] 分析完成，报告长度: {len(report)}")

            except Exception as e:
                logger.error(f"❌ 大盘行情分析失败: {str(e)}")
                report = f"大盘行情分析失败: {str(e)}"
        else:
            report = "离线模式，暂不支持大盘行情分析"

        logger.debug(f"📊 [DEBUG] ===== 大盘行情分析师节点结束 =====")
        return {
            "messages": [("assistant", report)],
            "trend_report": report,
        }

    return market_trend_analyst_node