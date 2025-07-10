#!/usr/bin/env python3
"""
OpenSMILE感情分析集計・アップロードAPI サーバー

FastAPIを使用してOpenSMILE感情分析機能をREST APIとして提供する。
ダッシュボードやWebアプリケーションから呼び出し可能。
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import json
import os
from datetime import datetime
import logging

from opensmile_aggregator import OpenSMILEAggregator

# FastAPIアプリ設定
app = FastAPI(
    title="OpenSMILE感情分析API",
    description="OpenSMILE特徴量データの収集・感情スコア集計・Supabase保存API",
    version="2.0.0"
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 本番環境では適切なオリジンを指定してください
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# タスク状況管理
task_status: Dict[str, Dict[str, Any]] = {}


class AnalysisRequest(BaseModel):
    """分析リクエストモデル"""
    device_id: str
    date: str  # YYYY-MM-DD形式


class TaskStatus(BaseModel):
    """タスク状況モデル"""
    task_id: str
    status: str  # started, running, completed, failed
    message: str
    progress: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/", tags=["Health"])
async def root():
    """ヘルスチェック"""
    return {
        "service": "OpenSMILE感情分析API", 
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """ヘルスチェックエンドポイント"""
    return {"status": "healthy"}


@app.post("/analyze/opensmile-aggregator", response_model=Dict[str, str], tags=["Analysis"])
async def start_emotion_analysis(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    OpenSMILE感情分析を開始（非同期バックグラウンド実行）
    """
    # 日付形式検証
    try:
        datetime.strptime(request.date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日付はYYYY-MM-DD形式で指定してください")
    
    # タスクID生成
    task_id = str(uuid.uuid4())
    
    # タスク状況初期化
    task_status[task_id] = {
        "task_id": task_id,
        "status": "started",
        "message": "感情分析タスクを開始しました",
        "progress": 0,
        "device_id": request.device_id,
        "date": request.date,
        "created_at": datetime.now().isoformat()
    }
    
    # バックグラウンドタスク追加
    background_tasks.add_task(execute_emotion_analysis, task_id, request.device_id, request.date)
    
    logger.info(f"OpenSMILE感情分析開始: task_id={task_id}, device_id={request.device_id}, date={request.date}")
    
    return {
        "task_id": task_id,
        "status": "started",
        "message": f"{request.device_id}/{request.date} の感情分析を開始しました"
    }


@app.get("/analyze/opensmile-aggregator/{task_id}", response_model=TaskStatus, tags=["Analysis"])
async def get_analysis_status(task_id: str):
    """
    分析タスクの状況を取得
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    
    return task_status[task_id]


@app.get("/analyze/opensmile-aggregator", tags=["Analysis"])
async def list_analysis_tasks():
    """
    全分析タスクの一覧を取得
    """
    return {
        "tasks": list(task_status.values()),
        "total": len(task_status)
    }


@app.delete("/analyze/opensmile-aggregator/{task_id}", tags=["Analysis"])
async def delete_analysis_task(task_id: str):
    """
    完了・失敗したタスクを削除
    """
    if task_id not in task_status:
        raise HTTPException(status_code=404, detail="タスクが見つかりません")
    
    task = task_status[task_id]
    if task["status"] in ["running", "started"]:
        raise HTTPException(status_code=400, detail="実行中のタスクは削除できません")
    
    del task_status[task_id]
    return {"message": f"タスク {task_id} を削除しました"}


async def execute_emotion_analysis(task_id: str, device_id: str, date: str):
    """
    OpenSMILE感情分析の実行（バックグラウンドタスク）
    """
    try:
        logger.info(f"🚀 バックグラウンドタスク開始: task_id={task_id}, device_id={device_id}, date={date}")
        
        # OpenSMILEデータ収集・感情スコア計算・Supabase保存
        task_status[task_id].update({
            "status": "running",
            "message": "OpenSMILEデータ収集・感情分析中...",
            "progress": 50
        })
        
        logger.info(f"📊 OpenSMILEAggregator インスタンス作成中...")
        aggregator = OpenSMILEAggregator()
        logger.info(f"🎭 感情分析開始（Supabaseからデータ取得）...")
        result = await aggregator.run(device_id, date)
        logger.info(f"📄 感情分析結果: {result}")
        
        if not result["success"]:
            logger.error(f"❌ 感情分析失敗")
            task_status[task_id].update({
                "status": "failed",
                "message": "感情分析処理に失敗しました",
                "error": "データ処理またはSupabase保存に失敗しました",
                "progress": 100
            })
            return
        
        logger.info(f"✅ 感情分析成功（Supabaseに保存済み）")
        
        # 成功メッセージをデータの有無に応じて調整
        message = result["message"]
        if not result["has_data"]:
            logger.info(f"📭 データなし: {message}")
        else:
            logger.info(f"🎉 感情分析完了: {result['processed_slots']}スロット処理")
        
        # 成功
        task_status[task_id].update({
            "status": "completed",
            "message": message,
            "progress": 100,
            "result": {
                "storage": {
                    "location": "Supabase emotion_opensmile_summary table",
                    "success": True
                },
                "has_data": result["has_data"],
                "processed_slots": result["processed_slots"],
                "total_emotion_points": result["total_emotion_points"],
                "emotion_graph_length": 48  # 48スロット固定
            }
        })
        
        logger.info(f"✅ OpenSMILE感情分析完了: task_id={task_id}")
        
    except Exception as e:
        logger.error(f"💥 OpenSMILE感情分析エラー: task_id={task_id}, error={e}")
        logger.error(f"💥 エラー詳細: {type(e).__name__}: {str(e)}")
        import traceback
        logger.error(f"💥 スタックトレース: {traceback.format_exc()}")
        task_status[task_id].update({
            "status": "failed",
            "message": "感情分析中にエラーが発生しました",
            "error": str(e),
            "progress": 100
        })
        logger.error(f"❌ OpenSMILE感情分析エラー: task_id={task_id}, error={e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)