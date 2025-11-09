"""
Supabaseサービスレイヤー
audio_features.emotion_extractor_resultからデータを取得
audio_aggregator.emotion_aggregator_resultへデータを保存
"""

import os
from typing import Dict, List, Optional
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()


class SupabaseService:
    """Supabaseとの連携を管理するサービスクラス"""
    
    def __init__(self):
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_KEY")
        
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URLとSUPABASE_KEY環境変数が必要です")
        
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.table_name = "audio_features"
        self.summary_table_name = "audio_aggregator"
    
    async def fetch_opensmile_data(
        self,
        device_id: str,
        date: str,
        time_slot: str
    ) -> Optional[Dict]:
        """
        指定されたdevice_id、date、time_slotの感情分析データを取得

        Args:
            device_id: デバイスID
            date: 日付 (YYYY-MM-DD形式)
            time_slot: 時間スロット (HH-MM形式)

        Returns:
            Dict: 感情分析データ（emotion_extractor_resultを含む）
        """
        try:
            response = self.supabase.table(self.table_name).select(
                "device_id,date,time_block,emotion_extractor_result"
            ).eq(
                "device_id", device_id
            ).eq(
                "date", date
            ).eq(
                "time_block", time_slot
            ).execute()

            if response.data and len(response.data) > 0:
                print(f"✅ Supabaseからデータ取得成功: {device_id}/{date}/{time_slot}")
                return response.data[0]
            else:
                print(f"📭 データなし: {device_id}/{date}/{time_slot}")
                return None

        except Exception as e:
            print(f"❌ Supabase取得エラー: {str(e)}")
            return None
    
    async def fetch_all_opensmile_data_for_day(
        self,
        device_id: str,
        date: str
    ) -> List[Dict]:
        """
        指定されたdevice_idとdateの全感情分析データを取得

        Args:
            device_id: デバイスID
            date: 日付 (YYYY-MM-DD形式)

        Returns:
            List[Dict]: その日の全感情分析データのリスト
        """
        try:
            response = self.supabase.table(self.table_name).select(
                "device_id,date,time_block,emotion_extractor_result"
            ).eq(
                "device_id", device_id
            ).eq(
                "date", date
            ).order(
                "time_block"
            ).execute()

            if response.data:
                print(f"✅ Supabaseから{len(response.data)}件のデータ取得成功: {device_id}/{date}")
                return response.data
            else:
                print(f"📭 データなし: {device_id}/{date}")
                return []

        except Exception as e:
            print(f"❌ Supabase取得エラー: {str(e)}")
            return []
    
    async def save_emotion_summary(
        self,
        device_id: str,
        date: str,
        emotion_graph: List[Dict]
    ) -> bool:
        """
        感情グラフデータをaudio_aggregator.emotion_aggregator_resultに保存

        Args:
            device_id: デバイスID
            date: 日付 (YYYY-MM-DD形式)
            emotion_graph: 時間スロットごとの感情スコアのリスト（48スロット、time_blocks相当）

        Returns:
            bool: 保存成功時True
        """
        try:
            # レコードデータを作成（1日1レコード）
            record = {
                "device_id": device_id,
                "date": date,
                "emotion_aggregator_result": emotion_graph,  # time_blocksを保存
                "emotion_aggregator_processed_at": datetime.utcnow().isoformat()
            }

            # UPSERT実行（既存データがあれば更新、なければ挿入）
            response = self.supabase.table(self.summary_table_name).upsert(
                record,
                on_conflict="device_id,date"
            ).execute()

            print(f"✅ Supabase audio_aggregatorにデータを保存: {device_id}/{date}")
            print(f"   emotion_aggregator_result に time_blocks を保存")
            print(f"   保存スロット数: {len(emotion_graph)}")
            return True

        except Exception as e:
            print(f"❌ Supabase保存エラー: {str(e)}")
            return False