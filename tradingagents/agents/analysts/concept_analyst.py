# tradingagents/agents/analysts/concept_analyst.py
import logging
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

# 导入概念分析器
from ...utils.concept_analyzer import CorrectedConceptAnalyzer

# 配置日志
logger = logging.getLogger("ConceptAnalyst")

def create_concept_analyst():
    """创建概念分析师节点"""
    def concept_analyst_node(state):
        logger.info(f"📈 [概念分析师] 开始分析股票相关概念")
        
        # 从状态中获取必要信息
        ticker = state["company_of_interest"]
        current_date = state.get("trade_date", datetime.now().strftime("%Y-%m-%d"))
        
        try:
            # 初始化概念分析器
            concept_analyzer = CorrectedConceptAnalyzer(
                top_n=5,            # 推荐前5个概念
                rise_weight=0.3,    # 涨跌幅权重
                flow_weight=0.3,    # 资金流向权重
                fundamental_weight=0.2,  # 基本面权重
                sentiment_weight=0.2     # 情绪权重
            )
            
            # 运行概念分析
            logger.info(f"📈 [概念分析师] 正在分析与 {ticker} 相关的概念板块...")
            concept_results = concept_analyzer.run(initial_top_n=30, days_type=5)
            
            # 提取与当前股票最相关的概念
            related_concepts = identify_related_concepts(ticker, concept_analyzer)
            
            # 生成概念分析报告
            concept_report = generate_concept_report(related_concepts, concept_results)
            
            # 将概念分析结果添加到状态中
            state["concept_report"] = concept_report
            state["related_concepts"] = related_concepts
            
            logger.info(f"📈 [概念分析师] 概念分析完成")
            return state
            
        except Exception as e:
            logger.error(f"❌ [概念分析师] 分析失败: {str(e)}")
            state["concept_report"] = f"概念分析失败: {str(e)}"
            return state
    
    return concept_analyst_node

def identify_related_concepts(ticker: str, analyzer: CorrectedConceptAnalyzer) -> List[Dict]:
    """识别与指定股票相关的概念"""
    related = []
    
    # 遍历所有概念及其成分股，寻找包含当前股票的概念
    for concept_code, stocks_df in analyzer.concept_stocks.items():
        if not stocks_df.empty and '代码' in stocks_df.columns:
            # 检查股票是否在该概念的成分股中
            if any(str(stock_code).strip().upper() == ticker.strip().upper() 
                   for stock_code in stocks_df['代码'].astype(str)):
                
                # 查找概念名称
                concept_name = None
                if analyzer.scored_concepts is not None:
                    mask = analyzer.scored_concepts['板块代码'] == concept_code
                    if mask.any():
                        concept_name = analyzer.scored_concepts.loc[mask, '板块名称'].iloc[0]
                
                # 获取该概念的得分
                concept_score = None
                if analyzer.scored_concepts is not None:
                    mask = analyzer.scored_concepts['板块代码'] == concept_code
                    if mask.any():
                        concept_score = analyzer.scored_concepts.loc[mask, '综合得分'].iloc[0]
                
                related.append({
                    'concept_code': concept_code,
                    'concept_name': concept_name or f"未知概念({concept_code})",
                    'score': concept_score,
                    'stocks_count': len(stocks_df)
                })
    
    # 按得分排序
    return sorted(related, key=lambda x: x['score'] if x['score'] is not None else 0, reverse=True)

def generate_concept_report(related_concepts: List[Dict], all_concepts: pd.DataFrame) -> str:
    """生成概念分析报告"""
    if not related_concepts:
        return "未找到与该股票相关的概念板块信息。"
    
    report = "## 📊 股票概念分析报告\n\n"
    
    # 相关概念分析
    report += "### 相关概念板块\n"
    report += "该股票所属的主要概念板块及市场表现：\n\n"
    report += "| 概念名称 | 综合得分 | 成分股数量 |\n"
    report += "|----------|----------|------------|\n"
    
    for concept in related_concepts[:5]:  # 只显示前5个
        report += f"| {concept['concept_name']} | {concept['score']:.4f} | {concept['stocks_count']} |\n"
    
    # 市场热门概念
    report += "\n### 市场热门概念板块\n"
    report += "当前市场表现最佳的概念板块：\n\n"
    report += "| 排名 | 概念名称 | 涨跌幅(%) | 资金净流入(元) | 综合得分 |\n"
    report += "|------|----------|-----------|----------------|----------|\n"
    
    if all_concepts is not None and not all_concepts.empty:
        for i, (_, row) in enumerate(all_concepts.head(5).iterrows(), 1):
            report += f"| {i} | {row['板块名称']} | {row['涨跌幅']:.2f} | {int(row['主力资金净流入(元)']):,} | {row['综合得分']:.4f} |\n"
    
    # 投资建议
    report += "\n### 概念投资建议\n"
    top_concept = related_concepts[0] if related_concepts else None
    if top_concept and top_concept['score'] > 0.7:
        report += f"该股票所属的 {top_concept['concept_name']} 概念表现强劲，综合得分 {top_concept['score']:.4f}，具有较高投资价值。\n"
    elif top_concept:
        report += f"该股票所属的 {top_concept['concept_name']} 概念表现一般，综合得分 {top_concept['score']:.4f}，需谨慎投资。\n"
    
    report += "\n概念分析可帮助投资者了解股票所处行业环境及市场热点，但不应作为唯一投资依据。\n"
    
    return report