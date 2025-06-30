#!/usr/bin/env python3
"""
OpenSMILE感情分析集計・アップロードAPI サーバー

FastAPIを使用してOpenSMILE感情分析機能をREST APIとして提供する。
ダッシュボードやWebアプリケーションから呼び出し可能。
"""

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import uuid
import json
import os
from datetime import datetime
import logging

from opensmile_aggregator import OpenSMILEAggregator
from upload_opensmile_summary import OpenSMILESummaryUploader

# FastAPIアプリ設定
app = FastAPI(
    title="OpenSMILE感情分析API",
    description="OpenSMILE特徴量データの収集・感情スコア集計・アップロードAPI",
    version="1.0.0"
)

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# タスク状況管理
task_status: Dict[str, Dict[str, Any]] = {}


class AnalysisRequest(BaseModel):
    """分析リクエストモデル"""
    user_id: str
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
        "user_id": request.user_id,
        "date": request.date,
        "created_at": datetime.now().isoformat()
    }
    
    # バックグラウンドタスク追加
    background_tasks.add_task(execute_emotion_analysis, task_id, request.user_id, request.date)
    
    logger.info(f"OpenSMILE感情分析開始: task_id={task_id}, user_id={request.user_id}, date={request.date}")
    
    return {
        "task_id": task_id,
        "status": "started",
        "message": f"{request.user_id}/{request.date} の感情分析を開始しました"
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


async def execute_emotion_analysis(task_id: str, user_id: str, date: str):
    """
    OpenSMILE感情分析の実行（バックグラウンドタスク）
    """
    try:
        logger.info(f"🚀 バックグラウンドタスク開始: task_id={task_id}, user_id={user_id}, date={date}")
        
        # ステップ1: OpenSMILEデータ収集・感情スコア計算
        task_status[task_id].update({
            "status": "running",
            "message": "OpenSMILEデータ収集・感情分析中...",
            "progress": 25
        })
        
        logger.info(f"📊 OpenSMILEAggregator インスタンス作成中...")
        # 環境変数でSSL検証を制御（デフォルトは無効化）
        verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        aggregator = OpenSMILEAggregator(verify_ssl=verify_ssl)
        logger.info(f"🎭 感情分析開始（SSL検証: {'有効' if verify_ssl else '無効'}）...")
        output_path = await aggregator.run(user_id, date)
        logger.info(f"📄 感情分析結果: output_path={output_path}")
        
        if not output_path:
            logger.error(f"❌ データ収集失敗: output_pathが空")
            task_status[task_id].update({
                "status": "failed",
                "message": "感情分析データ収集に失敗しました",
                "error": "取得できたデータがありません",
                "progress": 100
            })
            return
        
        logger.info(f"✅ 感情分析成功: {output_path}")
        
        # ステップ2: アップロード
        task_status[task_id].update({
            "status": "running",
            "message": "アップロード中...",
            "progress": 75
        })
        
        logger.info(f"☁️ アップロード開始...")
        # SSL検証を無効化してダッシュボード環境での接続問題を回避
        verify_ssl = os.getenv('VERIFY_SSL', 'false').lower() == 'true'
        uploader = OpenSMILESummaryUploader(verify_ssl=verify_ssl)
        upload_result = await uploader.run(user_id, date)
        logger.info(f"📤 アップロード結果: {upload_result}")
        
        # 結果ファイル読み込み
        logger.info(f"📖 結果ファイル読み込み中: {output_path}")
        with open(output_path, 'r', encoding='utf-8') as f:
            analysis_result = json.load(f)
        
        # 統計情報計算
        total_emotion_points = 0
        for emotion_data in analysis_result.get("emotion_graph", []):
            for emotion in ["anger", "fear", "anticipation", "surprise", "joy", "sadness", "trust", "disgust"]:
                total_emotion_points += emotion_data.get(emotion, 0)
        
        logger.info(f"🎉 感情分析完了: 総感情ポイント数={total_emotion_points}")
        
        # 成功
        task_status[task_id].update({
            "status": "completed",
            "message": "感情分析完了",
            "progress": 100,
            "result": {
                "analysis": analysis_result,
                "upload": upload_result,
                "total_emotion_points": total_emotion_points,
                "output_path": output_path,
                "emotion_graph_length": len(analysis_result.get("emotion_graph", []))
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