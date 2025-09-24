#!/usr/bin/env python3
"""
傩 Streamlit Web界面
基于Streamlit的股票分析Web应用程序，包含选股统计和自动选股功能
"""

import streamlit as st
import os
import sys
from pathlib import Path
import datetime  # 确保正确导入datetime模块
import time
import json
import pandas as pd
from dotenv import load_dotenv
import uuid
from datetime import timedelta, datetime  # 显式导入datetime类

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('web')

# 加载环境变量
load_dotenv(project_root / ".env", override=True)

# 导入自定义组件
from components.sidebar import render_sidebar
from components.header import render_header
from components.analysis_form import render_analysis_form
from components.results_display import render_results
from utils.api_checker import check_api_keys
from utils.analysis_runner import run_stock_analysis, validate_analysis_params, format_analysis_results
from utils.progress_tracker import SmartStreamlitProgressDisplay, create_smart_progress_callback
from utils.async_progress_tracker import AsyncProgressTracker
from components.async_progress_display import display_unified_progress
from utils.smart_session_manager import get_persistent_analysis_id, set_persistent_analysis_id

# 设置页面配置
st.set_page_config(
    page_title="傩 股票分析平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items=None
)

# 自定义CSS样式
st.markdown("""
<style>
    /* 隐藏Streamlit顶部工具栏和Deploy按钮 - 多种选择器确保兼容性 */
    .stAppToolbar {
        display: none !important;
    }
    
    header[data-testid="stHeader"] {
        display: none !important;
    }
    
    .stDeployButton {
        display: none !important;
    }
    
    /* 新版本Streamlit的Deploy按钮选择器 */
    [data-testid="stToolbar"] {
        display: none !important;
    }
    
    [data-testid="stDecoration"] {
        display: none !important;
    }
    
    [data-testid="stStatusWidget"] {
        display: none !important;
    }
    
    /* 隐藏整个顶部区域 */
    .stApp > header {
        display: none !important;
    }
    
    .stApp > div[data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* 隐藏主菜单按钮 */
    #MainMenu {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* 隐藏页脚 */
    footer {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* 隐藏"Made with Streamlit"标识 */
    .viewerBadge_container__1QSob {
        display: none !important;
    }
    
    /* 隐藏所有可能的工具栏元素 */
    div[data-testid="stToolbar"] {
        display: none !important;
    }
    
    /* 隐藏右上角的所有按钮 */
    .stApp > div > div > div > div > section > div {
        padding-top: 0 !important;
    }
    
    /* 应用样式 */
    .main-header {
        background: linear-gradient(90deg, #1f77b4, #ff7f0e);
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 2rem;
        color: white;
        text-align: center;
    }
    
    .metric-card {
        background: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
        margin: 0.5rem 0;
    }
    
    .analysis-section {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin: 1rem 0;
    }
    
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .warning-box {
        background: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    .error-box {
        background: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    
    /* 选股表格样式 */
    .stock-selection-table {
        margin-top: 1rem;
        margin-bottom: 1.5rem;
    }
    
    .strategy-tag {
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    
    .strategy-trend {
        background-color: #e3f2fd;
        color: #0d47a1;
    }
    
    .strategy-value {
        background-color: #e8f5e9;
        color: #1b5e20;
    }
    
    .strategy-momentum {
        background-color: #fff8e1;
        color: #ff8f00;
    }
    
    .strategy-volatility {
        background-color: #ffebee;
        color: #b71c1c;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """初始化会话状态，包括新增的选股相关状态"""
    if 'analysis_results' not in st.session_state:
        st.session_state.analysis_results = None
    if 'analysis_running' not in st.session_state:
        st.session_state.analysis_running = False
    if 'last_analysis_time' not in st.session_state:
        st.session_state.last_analysis_time = None
    if 'current_analysis_id' not in st.session_state:
        st.session_state.current_analysis_id = None
    if 'form_config' not in st.session_state:
        st.session_state.form_config = None
    
    # 选股统计相关状态初始化
    if 'stock_selections' not in st.session_state:
        # 初始化选股记录，包含示例数据
        st.session_state.stock_selections = [
            {
                'id': 'SEL_' + uuid.uuid4().hex[:6],
                'stock_code': '600519',
                'stock_name': '贵州茅台',
                'selection_time': (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d %H:%M'),
                'buy_time': (datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d %H:%M'),
                'sell_time': None,
                'holding_period': (datetime.now() - datetime.strptime((datetime.now() - timedelta(days=4)).strftime('%Y-%m-%d %H:%M'), '%Y-%m-%d %H:%M')).days,
                'return_rate': 3.2,
                'reason': '基本面良好，业绩稳定增长，行业龙头地位稳固，技术面呈现上升趋势',
                'strategy': '价值投资'
            },
            {
                'id': 'SEL_' + uuid.uuid4().hex[:6],
                'stock_code': '000858',
                'stock_name': '五粮液',
                'selection_time': (datetime.now() - timedelta(days=10)).strftime('%Y-%m-%d %H:%M'),
                'buy_time': (datetime.now() - timedelta(days=9)).strftime('%Y-%m-%d %H:%M'),
                'sell_time': (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d %H:%M'),
                'holding_period': 7,
                'return_rate': 5.8,
                'reason': '短期技术指标向好，市场情绪积极，成交量放大',
                'strategy': '趋势跟踪'
            }
        ]
    
    # 自动选股配置初始化
    if 'auto_selection_config' not in st.session_state:
        st.session_state.auto_selection_config = {
            'run_time': '09:30',  # 每天运行时间
            'enabled': False,      # 是否启用自动选股
            'strategies': {
                'trend_following': True,  # 趋势跟踪策略
                'value_investing': True,  # 价值投资策略
                'momentum': False,        # 动量策略
                'volatility_arbitrage': False  # 波动率套利策略
            },
            'max_stocks': 10,      # 每次最多选多少只股票
            'last_run_time': None  # 上次运行时间
        }
    
    # 自动选股结果初始化
    if 'auto_selection_results' not in st.session_state:
        st.session_state.auto_selection_results = []

    # 尝试从最新完成的分析中恢复结果
    if not st.session_state.analysis_results:
        try:
            from utils.async_progress_tracker import get_latest_analysis_id, get_progress_by_id
            from utils.analysis_runner import format_analysis_results

            latest_id = get_latest_analysis_id()
            if latest_id:
                progress_data = get_progress_by_id(latest_id)
                if (progress_data and
                    progress_data.get('status') == 'completed' and
                    'raw_results' in progress_data):

                    # 恢复分析结果
                    raw_results = progress_data['raw_results']
                    formatted_results = format_analysis_results(raw_results)

                    if formatted_results:
                        st.session_state.analysis_results = formatted_results
                        st.session_state.current_analysis_id = latest_id
                        # 检查分析状态
                        analysis_status = progress_data.get('status', 'completed')
                        st.session_state.analysis_running = (analysis_status == 'running')
                        # 恢复股票信息
                        if 'stock_symbol' in raw_results:
                            st.session_state.last_stock_symbol = raw_results.get('stock_symbol', '')
                        if 'market_type' in raw_results:
                            st.session_state.last_market_type = raw_results.get('market_type', '')
                        logger.info(f"📊 [结果恢复] 从分析 {latest_id} 恢复结果，状态: {analysis_status}")

        except Exception as e:
            logger.warning(f"⚠️ [结果恢复] 恢复失败: {e}")

    # 使用cookie管理器恢复分析ID（优先级：session state > cookie > Redis/文件）
    try:
        persistent_analysis_id = get_persistent_analysis_id()
        if persistent_analysis_id:
            # 使用线程检测来检查分析状态
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(persistent_analysis_id)

            # 只在状态变化时记录日志，避免重复
            current_session_status = st.session_state.get('last_logged_status')
            if current_session_status != actual_status:
                logger.info(f"📊 [状态检查] 分析 {persistent_analysis_id} 实际状态: {actual_status}")
                st.session_state.last_logged_status = actual_status

            if actual_status == 'running':
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = persistent_analysis_id
            elif actual_status in ['completed', 'failed']:
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = persistent_analysis_id
            else:  # not_found
                logger.warning(f"📊 [状态检查] 分析 {persistent_analysis_id} 未找到，清理状态")
                st.session_state.analysis_running = False
                st.session_state.current_analysis_id = None
    except Exception as e:
        # 如果恢复失败，保持默认值
        logger.warning(f"⚠️ [状态恢复] 恢复分析状态失败: {e}")
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None

    # 恢复表单配置
    try:
        from utils.smart_session_manager import smart_session_manager
        session_data = smart_session_manager.load_analysis_state()

        if session_data and 'form_config' in session_data:
            st.session_state.form_config = session_data['form_config']
            # 只在没有分析运行时记录日志，避免重复
            if not st.session_state.get('analysis_running', False):
                logger.info("📊 [配置恢复] 表单配置已恢复")
    except Exception as e:
        logger.warning(f"⚠️ [配置恢复] 表单配置恢复失败: {e}")

# 选股统计功能实现
def render_stock_selection_stats():
    """渲染选股统计页面"""
    st.header("📊 选股统计")
    st.markdown("---")
    
    # 添加新的选股记录
    with st.expander("➕ 添加新的选股记录", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            stock_code = st.text_input("股票代码", placeholder="例如: 600519")
            stock_name = st.text_input("股票名称", placeholder="例如: 贵州茅台")
            
            # 选出时间 - 使用日期+时间组合替代datetime_input
            st.subheader("选出时间")
            # 为date_input和time_input添加唯一key
            selection_date = st.date_input("日期", datetime.now(), key="selection_date")
            selection_hour = st.time_input("时间", datetime.now(), key="selection_time")
            selection_time = datetime.combine(selection_date, selection_hour)
            
            # 买入时间 - 使用日期+时间组合替代datetime_input
            st.subheader("买入时间")
            # 为date_input添加唯一key
            buy_date = st.date_input("日期", datetime.now(), key="buy_date")
            buy_hour = st.time_input("时间", datetime.now(), key="buy_time")
            buy_time = datetime.combine(buy_date, buy_hour)
            
        with col2:
            sell_status = st.radio("卖出状态", ["已卖出", "持有中"])
            sell_time = None
            if sell_status == "已卖出":
                # 卖出时间 - 使用日期+时间组合替代datetime_input
                st.subheader("卖出时间")
                sell_date = st.date_input("日期", datetime.now(), key="sell_date")
                sell_hour = st.time_input("时间", datetime.now(), key="sell_time")
                sell_time = datetime.combine(sell_date, sell_hour)
            
            strategy = st.selectbox("选股策略", ["趋势跟踪", "价值投资", "动量策略", "波动率套利", "其他"])
            reason = st.text_area("选中理由说明", placeholder="请输入选中这只股票的理由...", height=100)
        
        if st.button("保存选股记录", key="save_selection"):
            if not stock_code or not stock_name or not reason:
                st.error("请填写股票代码、名称和选中理由")
                return
            
            # 计算持仓时间和收益率（这里收益率为模拟输入，实际应用中应根据价格计算）
            if sell_time:
                holding_period = (sell_time - buy_time).days
                return_rate = st.number_input("收益率(%)", min_value=-100.0, max_value=100.0, value=0.0, step=0.1)
            else:
                holding_period = (datetime.now() - buy_time).days
                return_rate = st.number_input("当前收益率(%)", min_value=-100.0, max_value=100.0, value=0.0, step=0.1)
            
            # 创建新的选股记录
            new_selection = {
                'id': 'SEL_' + uuid.uuid4().hex[:6],
                'stock_code': stock_code,
                'stock_name': stock_name,
                'selection_time': selection_time.strftime('%Y-%m-%d %H:%M'),
                'buy_time': buy_time.strftime('%Y-%m-%d %H:%M'),
                'sell_time': sell_time.strftime('%Y-%m-%d %H:%M') if sell_time else None,
                'holding_period': holding_period,
                'return_rate': return_rate,
                'reason': reason,
                'strategy': strategy
            }
            
            # 添加到会话状态
            st.session_state.stock_selections.insert(0, new_selection)
            st.success("选股记录已保存！")
    
    # 显示选股统计数据
    st.subheader("📈 选股表现概览")
    col1, col2, col3, col4 = st.columns(4)
    
    total = len(st.session_state.stock_selections)
    holding = sum(1 for s in st.session_state.stock_selections if s['sell_time'] is None)
    closed = total - holding
    
    # 计算平均收益率（只计算已平仓的）
    returns = [s['return_rate'] for s in st.session_state.stock_selections if s['sell_time'] is not None]
    avg_return = sum(returns) / len(returns) if returns else 0
    
    # 计算胜率
    winning_trades = [r for r in returns if r > 0]
    win_rate = (len(winning_trades) / len(returns)) * 100 if returns else 0
    
    with col1:
        st.metric("总选股数", total)
    with col2:
        st.metric("持仓中", holding)
    with col3:
        st.metric("平均收益率", f"{avg_return:.2f}%")
    with col4:
        st.metric("胜率", f"{win_rate:.1f}%")
    
    # 显示选股记录表格
    st.subheader("📋 选股记录详情")
    
    # 转换为DataFrame以便显示
    df = pd.DataFrame(st.session_state.stock_selections)
    
    # 重命名列名
    df = df.rename(columns={
        'stock_code': '股票代码',
        'stock_name': '股票名称',
        'selection_time': '选出时间',
        'buy_time': '买入时间',
        'sell_time': '卖出时间',
        'holding_period': '持仓时间(天)',
        'return_rate': '收益率(%)',
        'strategy': '选股策略'
    })
    
    # 处理卖出时间显示
    df['卖出时间'] = df['卖出时间'].fillna('持有中')
    
    # 选择要显示的列
    display_df = df[['股票代码', '股票名称', '选出时间', '买入时间', '卖出时间', '持仓时间(天)', '收益率(%)', '选股策略']]
    
    # 显示表格
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # 详细查看选中的股票
    st.subheader("🔍 查看选股详情")
    selection_id = st.selectbox("选择记录ID", [s['id'] for s in st.session_state.stock_selections])
    
    # 找到选中的记录
    selected = next(s for s in st.session_state.stock_selections if s['id'] == selection_id)
    
    # 显示详情
    with st.expander(f"详细信息: {selected['stock_code']} {selected['stock_name']}", expanded=True):
        col1, col2 = st.columns(2)
        
        with col1:
            st.write(f"**选出时间:** {selected['selection_time']}")
            st.write(f"**买入时间:** {selected['buy_time']}")
            st.write(f"**卖出时间:** {selected['sell_time'] if selected['sell_time'] else '持有中'}")
            st.write(f"**持仓时间:** {selected['holding_period']} 天")
            st.write(f"**收益率:** {selected['return_rate']}%")
            st.write(f"**选股策略:** {selected['strategy']}")
        
        with col2:
            st.write("**选中理由说明:**")
            st.write(selected['reason'])
            
            # 添加操作按钮
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.button("📈 分析这只股票", key=f"analyze_{selected['id']}"):
                    # 跳转到股票分析页面并填充股票代码
                    st.session_state.last_stock_symbol = selected['stock_code']
                    st.session_state.last_market_type = 'A股'
                    st.session_state.page = "📊 股票分析"
                    st.rerun()
            
            with col_btn2:
                if st.button("🗑️ 删除记录", key=f"delete_{selected['id']}"):
                    st.session_state.stock_selections = [s for s in st.session_state.stock_selections if s['id'] != selection_id]
                    st.success("记录已删除")
                    st.rerun()
    

# 自动选股配置功能实现
def render_auto_selection_config():
    """渲染自动选股配置页面"""
    st.header("⚙️ 自动选股配置")
    st.markdown("---")
    
    # 基本配置
    st.subheader("基本设置")
    col1, col2 = st.columns(2)
    
    with col1:
        run_time = st.text_input("自动运行时间", st.session_state.auto_selection_config['run_time'], placeholder="例如: 09:30")
        max_stocks = st.slider("每次最多选股数量", 1, 30, st.session_state.auto_selection_config['max_stocks'])
        enabled = st.checkbox("启用自动选股", st.session_state.auto_selection_config['enabled'])
    
    with col2:
        st.info("""
        **自动选股说明:**
        
        系统将在每天指定时间，根据大盘行情自动判断适合的操作手法，从A股中筛选出符合条件的股票。
        
        选股结果将保存在系统中，您可以在选股统计页面查看。
        """)
        
        if st.session_state.auto_selection_config['last_run_time']:
            st.success(f"上次自动选股运行时间: {st.session_state.auto_selection_config['last_run_time']}")
    
    # 策略配置
    st.subheader("选股策略设置")
    st.write("选择系统可以使用的选股策略，系统会根据大盘行情自动选择合适的策略组合")
    
    col1, col2 = st.columns(2)
    with col1:
        trend_following = st.checkbox(
            "趋势跟踪策略", 
            st.session_state.auto_selection_config['strategies']['trend_following']
        )
        value_investing = st.checkbox(
            "价值投资策略", 
            st.session_state.auto_selection_config['strategies']['value_investing']
        )
    
    with col2:
        momentum = st.checkbox(
            "动量策略", 
            st.session_state.auto_selection_config['strategies']['momentum']
        )
        volatility_arbitrage = st.checkbox(
            "波动率套利策略", 
            st.session_state.auto_selection_config['strategies']['volatility_arbitrage']
        )
    
    # 保存配置
    if st.button("保存配置"):
        # 验证时间格式
        try:
            datetime.strptime(run_time, '%H:%M')
        except ValueError:
            st.error("时间格式不正确，请使用HH:MM格式，例如09:30")
            return
        
        # 更新配置
        st.session_state.auto_selection_config = {
            'run_time': run_time,
            'enabled': enabled,
            'strategies': {
                'trend_following': trend_following,
                'value_investing': value_investing,
                'momentum': momentum,
                'volatility_arbitrage': volatility_arbitrage
            },
            'max_stocks': max_stocks,
            'last_run_time': st.session_state.auto_selection_config['last_run_time']
        }
        
        st.success("自动选股配置已保存！")
    
    # 手动触发自动选股
    st.markdown("---")
    st.subheader("手动操作")
    
    if st.button("立即执行自动选股", type="primary"):
        with st.spinner("正在执行自动选股..."):
            # 模拟自动选股过程
            time.sleep(3)
            
            # 获取当前配置
            config = st.session_state.auto_selection_config
            
            # 模拟根据大盘行情选择策略
            # 这里简化处理，实际应用中应根据真实市场数据判断
            market_condition = "震荡上行"  # 模拟市场情况
            selected_strategies = []
            
            if market_condition in ["震荡上行", "单边上涨"] and config['strategies']['trend_following']:
                selected_strategies.append("趋势跟踪")
            
            if market_condition in ["震荡整理", "低位盘整"] and config['strategies']['value_investing']:
                selected_strategies.append("价值投资")
            
            if not selected_strategies:
                # 如果没有符合条件的策略，使用默认策略
                selected_strategies = ["趋势跟踪"]
            
            # 模拟选股结果（实际应用中应从A股市场筛选）
            # 这里使用随机生成的股票代码
            sectors = ["金融", "消费", "科技", "医药", "制造", "能源", "地产"]
            simulated_stocks = []
            
            for i in range(min(config['max_stocks'], 10)):
                # 随机生成6位股票代码
                code_prefix = "600" if i % 2 == 0 else "000"
                code_suffix = f"{i+100:03d}"
                stock_code = code_prefix + code_suffix
                
                # 随机生成股票名称
                names = [
                    f"XX银行{i+1}", f"XX科技{i+1}", f"XX医药{i+1}",
                    f"XX消费{i+1}", f"XX制造{i+1}", f"XX能源{i+1}"
                ]
                stock_name = names[i % len(names)]
                
                # 随机生成收益率
                return_rate = round((i + 1) * 0.8 + (i % 3) * 0.5, 2)
                
                # 随机选择行业
                sector = sectors[i % len(sectors)]
                
                simulated_stocks.append({
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'selection_time': datetime.now().strftime('%Y-%m-%d %H:%M'),
                    'reason': f"符合{selected_strategies[i % len(selected_strategies)]}策略，{sector}行业前景良好，技术指标积极",
                    'strategy': selected_strategies[i % len(selected_strategies)],
                    'sector': sector,
                    'return_potential': return_rate
                })
            
            # 保存选股结果
            st.session_state.auto_selection_results = simulated_stocks
            
            # 更新最后运行时间
            st.session_state.auto_selection_config['last_run_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 将选股结果添加到选股统计中
            for stock in simulated_stocks:
                new_selection = {
                    'id': 'AUTO_' + uuid.uuid4().hex[:6],
                    'stock_code': stock['stock_code'],
                    'stock_name': stock['stock_name'],
                    'selection_time': stock['selection_time'],
                    'buy_time': None,  # 自动选股仅记录选出时间，买入时间由用户决定
                    'sell_time': None,
                    'holding_period': 0,
                    'return_rate': 0,
                    'reason': stock['reason'],
                    'strategy': stock['strategy']
                }
                st.session_state.stock_selections.insert(0, new_selection)
            
            st.success(f"自动选股完成！共选出 {len(simulated_stocks)} 只股票")
    
    # 显示最近自动选股结果
    if st.session_state.auto_selection_results:
        st.subheader("最近自动选股结果")
        
        # 转换为DataFrame显示
        df = pd.DataFrame(st.session_state.auto_selection_results)
        df = df.rename(columns={
            'stock_code': '股票代码',
            'stock_name': '股票名称',
            'selection_time': '选出时间',
            'strategy': '选股策略',
            'sector': '行业',
            'return_potential': '预期收益率(%)'
        })
        
        st.dataframe(df[['股票代码', '股票名称', '行业', '选股策略', '预期收益率(%)', '选出时间']], 
                    use_container_width=True, hide_index=True)
        
        # 查看详细理由
        st.subheader("选股详细理由")
        stock_code = st.selectbox("选择股票查看详情", [s['stock_code'] for s in st.session_state.auto_selection_results])
        stock = next(s for s in st.session_state.auto_selection_results if s['stock_code'] == stock_code)
        
        st.write(f"**{stock['stock_code']} {stock['stock_name']}**")
        st.write(f"**选股策略:** {stock['strategy']}")
        st.write(f"**行业:** {stock['sector']}")
        st.write(f"**选出时间:** {stock['selection_time']}")
        st.write(f"**预期收益率:** {stock['return_potential']}%")
        st.write("**选股理由:**")
        st.write(stock['reason'])

def main():
    """主应用程序"""

    # 初始化会话状态
    initialize_session_state()

    # 自定义CSS - 调整侧边栏宽度
    st.markdown("""
    <style>
    /* 调整侧边栏宽度为260px，避免标题挤压 */
    section[data-testid="stSidebar"] {
        width: 260px !important;
        min-width: 260px !important;
        max-width: 260px !important;
    }

    /* 隐藏侧边栏的隐藏按钮 - 更全面的选择器 */
    button[kind="header"],
    button[data-testid="collapsedControl"],
    .css-1d391kg,
    .css-1rs6os,
    .css-17eq0hr,
    .css-1lcbmhc,
    .css-1y4p8pa,
    button[aria-label="Close sidebar"],
    button[aria-label="Open sidebar"],
    [data-testid="collapsedControl"],
    .stSidebar button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }

    /* 隐藏侧边栏顶部区域的特定按钮（更精确的选择器，避免影响表单按钮） */
    section[data-testid="stSidebar"] > div:first-child > button[kind="header"],
    section[data-testid="stSidebar"] > div:first-child > div > button[kind="header"],
    section[data-testid="stSidebar"] .css-1lcbmhc > button[kind="header"],
    section[data-testid="stSidebar"] .css-1y4p8pa > button[kind="header"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* 调整侧边栏内容的padding */
    section[data-testid="stSidebar"] > div {
        padding-top: 0.5rem !important;
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
    }

    /* 调整主内容区域，设置8px边距 - 使用更强的选择器 */
    .main .block-container,
    section.main .block-container,
    div.main .block-container,
    .stApp .main .block-container {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
        max-width: none !important;
        width: calc(100% - 16px) !important;
    }

    /* 确保内容不被滚动条遮挡 */
    .stApp > div {
        overflow-x: auto !important;
    }

    /* 调整详细分析报告的右边距 */
    .element-container {
        margin-right: 8px !important;
    }

    /* 优化侧边栏标题和元素间距 */
    .sidebar .sidebar-content {
        padding: 0.5rem 0.3rem !important;
    }

    /* 调整侧边栏内所有元素的间距 */
    section[data-testid="stSidebar"] .element-container {
        margin-bottom: 0.5rem !important;
    }

    /* 调整侧边栏分隔线的间距 */
    section[data-testid="stSidebar"] hr {
        margin: 0.8rem 0 !important;
    }

    /* 确保侧边栏标题不被挤压 */
    section[data-testid="stSidebar"] h1 {
        font-size: 1.2rem !important;
        line-height: 1.3 !important;
        margin-bottom: 1rem !important;
        word-wrap: break-word !important;
        overflow-wrap: break-word !important;
    }

    /* 简化功能选择区域样式 */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        font-size: 1.1rem !important;
        font-weight: 500 !important;
    }

    /* 调整选择框等组件的宽度 */
    section[data-testid="stSidebar"] .stSelectbox > div > div {
        min-width: 220px !important;
        width: 100% !important;
    }

    /* 修复右侧内容被遮挡的问题 */
    .main {
        padding-right: 8px !important;
    }

    /* 确保页面内容有足够的右边距 */
    .stApp {
        margin-right: 0 !important;
        padding-right: 8px !important;
    }

    /* 特别处理展开的分析报告 */
    .streamlit-expanderContent {
        padding-right: 8px !important;
        margin-right: 8px !important;
    }

    /* 防止水平滚动条出现 */
    .main .block-container {
        overflow-x: visible !important;
    }

    /* 强制设置8px边距给所有可能的容器 */
    .stApp,
    .stApp > div,
    .stApp > div > div,
    .main,
    .main > div,
    .main > div > div,
    div[data-testid="stAppViewContainer"],
    div[data-testid="stAppViewContainer"] > div,
    section[data-testid="stMain"],
    section[data-testid="stMain"] > div {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    /* 特别处理列容器 */
    div[data-testid="column"],
    .css-1d391kg,
    .css-1r6slb0,
    .css-12oz5g7,
    .css-1lcbmhc {
        padding-left: 8px !important;
        padding-right: 8px !important;
        margin-left: 0px !important;
        margin-right: 0px !important;
    }

    /* 强制设置容器宽度 */
    .main .block-container {
        width: calc(100vw - 276px) !important;
        max-width: calc(100vw - 276px) !important;
    }

    /* 优化使用指南区域的样式 */
    div[data-testid="column"]:last-child {
        background-color: #f8f9fa !important;
        border-radius: 8px !important;
        padding: 12px !important;
        margin-left: 8px !important;
        border: 1px solid #e9ecef !important;
    }

    /* 使用指南内的展开器样式 */
    div[data-testid="column"]:last-child .streamlit-expanderHeader {
        background-color: #ffffff !important;
        border-radius: 6px !important;
        border: 1px solid #dee2e6 !important;
        font-weight: 500 !important;
    }

    /* 使用指南内的文本样式 */
    div[data-testid="column"]:last-child .stMarkdown {
        font-size: 0.9rem !important;
        line-height: 1.5 !important;
    }

    /* 使用指南标题样式 */
    div[data-testid="column"]:last-child h1 {
        font-size: 1.3rem !important;
        color: #495057 !important;
        margin-bottom: 1rem !important;
    }
    </style>

    <script>
    // JavaScript来强制隐藏侧边栏按钮
    function hideSidebarButtons() {
        // 隐藏所有可能的侧边栏控制按钮
        const selectors = [
            'button[kind="header"]',
            'button[data-testid="collapsedControl"]',
            'button[aria-label="Close sidebar"]',
            'button[aria-label="Open sidebar"]',
            '[data-testid="collapsedControl"]',
            '.css-1d391kg',
            '.css-1rs6os',
            '.css-17eq0hr',
            '.css-1lcbmhc button',
            '.css-1y4p8pa button'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.display = 'none';
                el.style.visibility = 'hidden';
                el.style.opacity = '0';
                el.style.pointerEvents = 'none';
            });
        });
    }

    // 页面加载后执行
    document.addEventListener('DOMContentLoaded', hideSidebarButtons);

    // 定期检查并隐藏按钮（防止动态生成）
    setInterval(hideSidebarButtons, 1000);

    // 强制修改页面边距为8px
    function forceOptimalPadding() {
        const selectors = [
            '.main .block-container',
            '.stApp',
            '.stApp > div',
            '.main',
            '.main > div',
            'div[data-testid="stAppViewContainer"]',
            'section[data-testid="stMain"]',
            'div[data-testid="column"]'
        ];

        selectors.forEach(selector => {
            const elements = document.querySelectorAll(selector);
            elements.forEach(el => {
                el.style.paddingLeft = '8px';
                el.style.paddingRight = '8px';
                el.style.marginLeft = '0px';
                el.style.marginRight = '0px';
            });
        });

        // 特别处理主容器宽度
        const mainContainer = document.querySelector('.main .block-container');
        if (mainContainer) {
            mainContainer.style.width = 'calc(100vw - 276px)';
            mainContainer.style.maxWidth = 'calc(100vw - 276px)';
        }
    }

    // 页面加载后执行
    document.addEventListener('DOMContentLoaded', forceOptimalPadding);

    // 定期强制应用样式
    setInterval(forceOptimalPadding, 500);
    </script>
    """, unsafe_allow_html=True)

    # 添加调试按钮（仅在调试模式下显示）
    if os.getenv('DEBUG_MODE') == 'true':
        if st.button("🔄 清除会话状态"):
            st.session_state.clear()
            st.experimental_rerun()

    # 渲染页面头部
    render_header()

    # 页面导航 - 添加新的功能选项
    st.sidebar.title("🤖 傩")
    st.sidebar.markdown("---")

    # 添加功能切换标题
    st.sidebar.markdown("**🎯 功能导航**")

    # 在原有功能基础上添加两个新功能
    page = st.sidebar.selectbox(
        "切换功能模块",
        ["📊 股票分析", "🔍 选股统计", "🤖 自动选股配置", "⚙️ 配置管理", "💾 缓存管理", "💰 Token统计", "📈 历史记录", "🔧 系统状态"],
        label_visibility="collapsed"
    )

    # 在功能选择和AI模型配置之间添加分隔线
    st.sidebar.markdown("---")

    # 根据选择的页面渲染不同内容
    if page == "🔍 选股统计":
        render_stock_selection_stats()
        return
    elif page == "🤖 自动选股配置":
        render_auto_selection_config()
        return
    elif page == "⚙️ 配置管理":
        try:
            from modules.config_management import render_config_management
            render_config_management()
        except ImportError as e:
            st.error(f"配置管理模块加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "💾 缓存管理":
        try:
            from modules.cache_management import main as cache_main
            cache_main()
        except ImportError as e:
            st.error(f"缓存管理页面加载失败: {e}")
        return
    elif page == "💰 Token统计":
        try:
            from modules.token_statistics import render_token_statistics
            render_token_statistics()
        except ImportError as e:
            st.error(f"Token统计页面加载失败: {e}")
            st.info("请确保已安装所有依赖包")
        return
    elif page == "📈 历史记录":
        st.header("📈 历史记录")
        st.info("历史记录功能开发中...")
        return
    elif page == "🔧 系统状态":
        st.header("🔧 系统状态")
        st.info("系统状态功能开发中...")
        return

    # 默认显示股票分析页面
    # 检查API密钥
    api_status = check_api_keys()
    
    if not api_status['all_configured']:
        st.error("⚠️ API密钥配置不完整，请先配置必要的API密钥")
        
        with st.expander("📋 API密钥配置指南", expanded=True):
            st.markdown("""
            ### 🔑 必需的API密钥
            
            1. **阿里百炼API密钥** (DASHSCOPE_API_KEY)
               - 获取地址: https://dashscope.aliyun.com/
               - 用途: AI模型推理
            
            2. **金融数据API密钥** (FINNHUB_API_KEY)  
               - 获取地址: https://finnhub.io/
               - 用途: 获取股票数据
            
            ### ⚙️ 配置方法
            
            1. 复制项目根目录的 `.env.example` 为 `.env`
            2. 编辑 `.env` 文件，填入您的真实API密钥
            3. 重启Web应用
            
            ```bash
            # .env 文件示例
            DASHSCOPE_API_KEY=sk-your-dashscope-key
            FINNHUB_API_KEY=your-finnhub-key
            ```
            """)
        
        # 显示当前API密钥状态
        st.subheader("🔍 当前API密钥状态")
        for key, status in api_status['details'].items():
            if status['configured']:
                st.success(f"✅ {key}: {status['display']}")
            else:
                st.error(f"❌ {key}: 未配置")
        
        return
    
    # 渲染侧边栏
    config = render_sidebar()
    
    # 添加使用指南显示切换
    show_guide = st.sidebar.checkbox("📖 显示使用指南", value=True, help="显示/隐藏右侧使用指南")

    # 添加状态清理按钮
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 清理分析状态", help="清理僵尸分析状态，解决页面持续刷新问题"):
        # 清理session state
        st.session_state.analysis_running = False
        st.session_state.current_analysis_id = None
        st.session_state.analysis_results = None

        # 清理所有自动刷新状态
        keys_to_remove = []
        for key in st.session_state.keys():
            if 'auto_refresh' in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            del st.session_state[key]

        # 清理死亡线程
        from utils.thread_tracker import cleanup_dead_analysis_threads
        cleanup_dead_analysis_threads()

        st.sidebar.success("✅ 分析状态已清理")
        st.rerun()

    # 主内容区域 - 根据是否显示指南调整布局
    if show_guide:
        col1, col2 = st.columns([2, 1])  # 2:1比例，使用指南占三分之一
    else:
        col1 = st.container()
        col2 = None
    
    with col1:
        # 1. 分析配置区域

        st.header("⚙️ 分析配置")

        # 渲染分析表单
        try:
            form_data = render_analysis_form()

            # 验证表单数据格式
            if not isinstance(form_data, dict):
                st.error(f"⚠️ 表单数据格式异常: {type(form_data)}")
                form_data = {'submitted': False}

        except Exception as e:
            st.error(f"❌ 表单渲染失败: {e}")
            form_data = {'submitted': False}

        # 避免显示调试信息
        if form_data and form_data != {'submitted': False}:
            # 只在调试模式下显示表单数据
            if os.getenv('DEBUG_MODE') == 'true':
                st.write("Debug - Form data:", form_data)

        # 添加接收日志
        if form_data.get('submitted', False):
            logger.debug(f"🔍 [APP DEBUG] ===== 主应用接收表单数据 =====")
            logger.debug(f"🔍 [APP DEBUG] 接收到的form_data: {form_data}")
            logger.debug(f"🔍 [APP DEBUG] 股票代码: '{form_data['stock_symbol']}'")
            logger.debug(f"🔍 [APP DEBUG] 市场类型: '{form_data['market_type']}'")

        # 检查是否提交了表单
        if form_data.get('submitted', False) and not st.session_state.get('analysis_running', False):
            # 只有在没有分析运行时才处理新的提交
            # 验证分析参数
            is_valid, validation_errors = validate_analysis_params(
                stock_symbol=form_data['stock_symbol'],
                analysis_date=form_data['analysis_date'],
                analysts=form_data['analysts'],
                research_depth=form_data['research_depth'],
                market_type=form_data.get('market_type', '美股')
            )

            if not is_valid:
                # 显示验证错误
                for error in validation_errors:
                    st.error(error)
            else:
                # 执行分析
                st.session_state.analysis_running = True

                # 清空旧的分析结果
                st.session_state.analysis_results = None
                logger.info("🧹 [新分析] 清空旧的分析结果")

                # 生成分析ID
                analysis_id = f"analysis_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

                # 保存分析ID和表单配置到session state和cookie
                form_config = st.session_state.get('form_config', {})
                set_persistent_analysis_id(
                    analysis_id=analysis_id,
                    status="running",
                    stock_symbol=form_data['stock_symbol'],
                    market_type=form_data.get('market_type', '美股'),
                    form_config=form_config
                )

                # 创建异步进度跟踪器
                async_tracker = AsyncProgressTracker(
                    analysis_id=analysis_id,
                    analysts=form_data['analysts'],
                    research_depth=form_data['research_depth'],
                    llm_provider=config['llm_provider']
                )

                # 创建进度回调函数
                def progress_callback(message: str, step: int = None, total_steps: int = None):
                    async_tracker.update_progress(message, step)

                # 显示启动成功消息和加载动效
                st.success(f"🚀 分析已启动！分析ID: {analysis_id}")

                # 添加加载动效
                with st.spinner("🔄 正在初始化分析..."):
                    time.sleep(1.5)  # 让用户看到反馈

                st.info(f"📊 正在分析: {form_data.get('market_type', '美股')} {form_data['stock_symbol']}")
                st.info("""
                ⏱️ 页面将在6秒后自动刷新...

                📋 **查看分析进度：**
                刷新后请向下滚动到 "📊 股票分析" 部分查看实时进度
                """)

                # 确保AsyncProgressTracker已经保存初始状态
                time.sleep(0.1)  # 等待100毫秒确保数据已写入

                # 设置分析状态
                st.session_state.analysis_running = True
                st.session_state.current_analysis_id = analysis_id
                st.session_state.last_stock_symbol = form_data['stock_symbol']
                st.session_state.last_market_type = form_data.get('market_type', '美股')

                # 自动启用自动刷新选项（设置所有可能的key）
                auto_refresh_keys = [
                    f"auto_refresh_unified_{analysis_id}",
                    f"auto_refresh_unified_default_{analysis_id}",
                    f"auto_refresh_static_{analysis_id}",
                    f"auto_refresh_streamlit_{analysis_id}"
                ]
                for key in auto_refresh_keys:
                    st.session_state[key] = True

                # 在后台线程中运行分析（立即启动，不等待倒计时）
                import threading

                def run_analysis_in_background():
                    try:
                        results = run_stock_analysis(
                            stock_symbol=form_data['stock_symbol'],
                            analysis_date=form_data['analysis_date'],
                            analysts=form_data['analysts'],
                            research_depth=form_data['research_depth'],
                            llm_provider=config['llm_provider'],
                            market_type=form_data.get('market_type', '美股'),
                            llm_model=config['llm_model'],
                            progress_callback=progress_callback
                        )

                        # 标记分析完成并保存结果（不访问session state）
                        async_tracker.mark_completed("✅ 分析成功完成！", results=results)

                        logger.info(f"✅ [分析完成] 股票分析成功完成: {analysis_id}")

                    except Exception as e:
                        # 标记分析失败（不访问session state）
                        async_tracker.mark_failed(str(e))
                        logger.error(f"❌ [分析失败] {analysis_id}: {e}")

                    finally:
                        # 分析结束后注销线程
                        from utils.thread_tracker import unregister_analysis_thread
                        unregister_analysis_thread(analysis_id)
                        logger.info(f"🧵 [线程清理] 分析线程已注销: {analysis_id}")

                # 启动后台分析线程
                analysis_thread = threading.Thread(target=run_analysis_in_background)
                analysis_thread.daemon = True  # 设置为守护线程，这样主程序退出时线程也会退出
                analysis_thread.start()

                # 注册线程到跟踪器
                from utils.thread_tracker import register_analysis_thread
                register_analysis_thread(analysis_id, analysis_thread)

                logger.info(f"🧵 [后台分析] 分析线程已启动: {analysis_id}")

                # 分析已在后台线程中启动，显示启动信息并刷新页面
                st.success("🚀 分析已启动！正在后台运行...")

                # 显示启动信息
                st.info("⏱️ 页面将自动刷新显示分析进度...")

                # 等待2秒让用户看到启动信息，然后刷新页面
                time.sleep(2)
                st.rerun()

        # 2. 股票分析区域（只有在有分析ID时才显示）
        current_analysis_id = st.session_state.get('current_analysis_id')
        if current_analysis_id:
            st.markdown("---")

            st.header("📊 股票分析")

            # 使用线程检测来获取真实状态
            from utils.thread_tracker import check_analysis_status
            actual_status = check_analysis_status(current_analysis_id)
            is_running = (actual_status == 'running')

            # 同步session state状态
            if st.session_state.get('analysis_running', False) != is_running:
                st.session_state.analysis_running = is_running
                logger.info(f"🔄 [状态同步] 更新分析状态: {is_running} (基于线程检测: {actual_status})")

            # 获取进度数据用于显示
            from utils.async_progress_tracker import get_progress_by_id
            progress_data = get_progress_by_id(current_analysis_id)

            # 显示分析信息
            if is_running:
                st.info(f"🔄 正在分析: {current_analysis_id}")
            else:
                if actual_status == 'completed':
                    st.success(f"✅ 分析完成: {current_analysis_id}")

                elif actual_status == 'failed':
                    st.error(f"❌ 分析失败: {current_analysis_id}")
                else:
                    st.warning(f"⚠️ 分析状态未知: {current_analysis_id}")

            # 显示进度（根据状态决定是否显示刷新控件）
            progress_col1, progress_col2 = st.columns([4, 1])
            with progress_col1:
                st.markdown("### 📊 分析进度")

            is_completed = display_unified_progress(current_analysis_id, show_refresh_controls=is_running)

            # 如果分析正在进行，显示提示信息（不添加额外的自动刷新）
            if is_running:
                st.info("⏱️ 分析正在进行中，可以使用下方的自动刷新功能查看进度更新...")

            # 如果分析刚完成，尝试恢复结果
            if is_completed and not st.session_state.get('analysis_results') and progress_data:
                if 'raw_results' in progress_data:
                    try:
                        from utils.analysis_runner import format_analysis_results
                        raw_results = progress_data['raw_results']
                        formatted_results = format_analysis_results(raw_results)
                        if formatted_results:
                            st.session_state.analysis_results = formatted_results
                            st.session_state.analysis_running = False
                            logger.info(f"📊 [结果同步] 恢复分析结果: {current_analysis_id}")

                            # 检查是否已经刷新过，避免重复刷新
                            refresh_key = f"results_refreshed_{current_analysis_id}"
                            if not st.session_state.get(refresh_key, False):
                                st.session_state[refresh_key] = True
                                st.success("📊 分析结果已恢复，正在刷新页面...")
                                # 使用st.rerun()代替meta refresh，保持侧边栏状态
                                time.sleep(1)
                                st.rerun()
                            else:
                                # 已经刷新过，不再刷新
                                st.success("📊 分析结果已恢复！")
                    except Exception as e:
                        logger.warning(f"⚠️ [结果同步] 恢复失败: {e}")

            if is_completed and st.session_state.get('analysis_running', False):
                # 分析刚完成，更新状态
                st.session_state.analysis_running = False
                st.success("🎉 分析完成！正在刷新页面显示报告...")

                # 使用st.rerun()代替meta refresh，保持侧边栏状态
                time.sleep(1)
                st.rerun()



        # 3. 分析报告区域（只有在有结果且分析完成时才显示）

        current_analysis_id = st.session_state.get('current_analysis_id')
        analysis_results = st.session_state.get('analysis_results')
        analysis_running = st.session_state.get('analysis_running', False)

        # 检查是否应该显示分析报告
        # 1. 有分析结果且不在运行中
        # 2. 或者用户点击了"查看报告"按钮
        show_results_button_clicked = st.session_state.get('show_analysis_results', False)

        should_show_results = (
            (analysis_results and not analysis_running and current_analysis_id) or
            (show_results_button_clicked and analysis_results)
        )

        # 调试日志
        logger.info(f"🔍 [布局调试] 分析报告显示检查:")
        logger.info(f"  - analysis_results存在: {bool(analysis_results)}")
        logger.info(f"  - analysis_running: {analysis_running}")
        logger.info(f"  - current_analysis_id: {current_analysis_id}")
        logger.info(f"  - show_results_button_clicked: {show_results_button_clicked}")
        logger.info(f"  - should_show_results: {should_show_results}")

        if should_show_results:
            st.markdown("---")
            st.header("📋 分析报告")
            render_results(analysis_results)
            logger.info(f"✅ [布局] 分析报告已显示")

            # 清除查看报告按钮状态，避免重复触发
            if show_results_button_clicked:
                st.session_state.show_analysis_results = False
    
    # 只有在显示指南时才渲染右侧内容
    if show_guide and col2 is not None:
        with col2:
            st.markdown("### ℹ️ 使用指南")
        
            # 快速开始指南
            with st.expander("🎯 快速开始", expanded=True):
                st.markdown("""
                ### 📋 操作步骤

                1. **输入股票代码**
                   - A股示例: `000001` (平安银行), `600519` (贵州茅台), `000858` (五粮液)
                   - 美股示例: `AAPL` (苹果), `TSLA` (特斯拉), `MSFT` (微软)
                   - 港股示例: `00700` (腾讯), `09988` (阿里巴巴)

                   ⚠️ **重要提示**: 输入股票代码后，请按 **回车键** 确认输入！

                2. **选择分析日期**
                   - 默认为今天
                   - 可选择历史日期进行回测分析

                3. **选择分析师团队**
                   - 至少选择一个分析师
                   - 建议选择多个分析师获得全面分析

                4. **设置研究深度**
                   - 1-2级: 快速概览
                   - 3级: 标准分析 (推荐)
                   - 4-5级: 深度研究

                5. **点击开始分析**
                   - 等待AI分析完成
                   - 查看详细分析报告

                ### 💡 使用技巧

                - **A股默认**: 系统默认分析A股，无需特殊设置
                - **代码格式**: A股使用6位数字代码 (如 `000001`)
                - **实时数据**: 获取最新的市场数据和新闻
                - **多维分析**: 结合技术面、基本面、情绪面分析
                """)

            # 分析师说明
            with st.expander("👥 分析师团队说明"):
                st.markdown("""
                ### 🎯 专业分析师团队

                - **📈 市场分析师**:
                  - 技术指标分析 (K线、均线、MACD等)
                  - 价格趋势预测
                  - 支撑阻力位分析

                - **💭 社交媒体分析师**:
                  - 投资者情绪监测
                  - 社交媒体热度分析
                  - 市场情绪指标

                - **📰 新闻分析师**:
                  - 重大新闻事件影响
                  - 政策解读分析
                  - 行业动态跟踪

                - **💰 基本面分析师**:
                  - 财务报表分析
                  - 估值模型计算
                  - 行业对比分析
                  - 盈利能力评估

                💡 **建议**: 选择多个分析师可获得更全面的投资建议
                """)

            # 模型选择说明
            with st.expander("🧠 AI模型说明"):
                st.markdown("""
                ### 🤖 智能模型选择

                - **qwen-turbo**:
                  - 快速响应，适合快速查询
                  - 成本较低，适合频繁使用
                  - 响应时间: 2-5秒

                - **qwen-plus**:
                  - 平衡性能，推荐日常使用 ⭐
                  - 准确性与速度兼顾
                  - 响应时间: 5-10秒

                - **qwen-max**:
                  - 最强性能，适合深度分析
                  - 最高准确性和分析深度
                  - 响应时间: 10-20秒

                💡 **推荐**: 日常分析使用 `qwen-plus`，重要决策使用 `qwen-max`
                """)

            # 常见问题
            with st.expander("❓ 常见问题"):
                st.markdown("""
                ### 🔍 常见问题解答

                **Q: 为什么输入股票代码没有反应？**
                A: 请确保输入代码后按 **回车键** 确认，这是Streamlit的默认行为。

                **Q: A股代码格式是什么？**
                A: A股使用6位数字代码，如 `000001`、`600519`、`000858` 等。

                **Q: 分析需要多长时间？**
                A: 根据研究深度和模型选择，通常需要30秒到2分钟不等。

                **Q: 可以分析港股吗？**
                A: 可以，输入5位港股代码，如 `00700`、`09988` 等。

                **Q: 历史数据可以追溯多久？**
                A: 通常可以获取近5年的历史数据进行分析。
                """)

            # 风险提示
            st.warning("""
            ⚠️ **投资风险提示**

            - 本系统提供的分析结果仅供参考，不构成投资建议
            - 投资有风险，入市需谨慎，请理性投资
            - 请结合多方信息和专业建议进行投资决策
            - 重大投资决策建议咨询专业的投资顾问
            - AI分析存在局限性，市场变化难以完全预测
            """)
        
        # 显示系统状态
        if st.session_state.last_analysis_time:
            st.info(f"🕒 上次分析时间: {st.session_state.last_analysis_time.strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
