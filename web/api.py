"""股票分析HTTP API服务"""
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uuid
from datetime import date
from .utils.analysis_runner import run_stock_analysis
import asyncio
import time

app = FastAPI(title="TradingAgents 股票分析API")

# 存储分析任务状态
analysis_tasks = {}

# 请求模型定义
class AnalysisRequest(BaseModel):
    stock_symbol: str
    market_type: str = "A股"
    analysis_date: date = date.today()
    research_depth: int = 3
    analysts: list[str] = ["market", "fundamentals"]
    llm_provider: str = "dashscope"
    llm_model: str = "qwen-plus-latest"

# 进度回调函数
def progress_callback(task_id, message, step=None, total_steps=None):
    """更新任务进度"""
    if task_id in analysis_tasks:
        analysis_tasks[task_id]["status"] = "running"
        analysis_tasks[task_id]["progress"] = {
            "message": message,
            "step": step,
            "total_steps": total_steps
        }

# 启动分析任务
@app.post("/api/analyze")
async def start_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    task_id = str(uuid.uuid4())
    analysis_tasks[task_id] = {
        "status": "pending",
        "result": None,
        "progress": None,
        "request": request.dict()
    }
    
    # 定义后台任务
    def run_analysis_task():
        try:
            # 包装进度回调
            def callback(message, step=None, total_steps=None):
                progress_callback(task_id, message, step, total_steps)
            analysis_date_str = request.analysis_date.strftime("%Y-%m-%d") 
            # 调用分析函数
            result = run_stock_analysis(
                stock_symbol=request.stock_symbol,
                analysis_date=analysis_date_str,
                analysts=request.analysts,
                research_depth=request.research_depth,
                llm_provider=request.llm_provider,
                llm_model=request.llm_model,
                market_type=request.market_type,
                progress_callback=callback
            )
            
            analysis_tasks[task_id]["status"] = "completed"
            analysis_tasks[task_id]["result"] = result
        except Exception as e:
            analysis_tasks[task_id]["status"] = "failed"
            analysis_tasks[task_id]["error"] = str(e)
    
    background_tasks.add_task(run_analysis_task)
    return {"task_id": task_id, "status": "started"}

# 查询任务状态
@app.get("/api/analysis/{task_id}")
async def get_analysis_status(task_id: str):
    if task_id not in analysis_tasks:
        raise HTTPException(status_code=404, detail="任务不存在")
    return analysis_tasks[task_id]

# 运行API服务
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)