"""
Supabaseサービスレイヤー
emotion_opensmileテーブルからデータを取得
emotion_opensmile_summaryテーブルへデータを保存
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
        self.table_name = "emotion_opensmile"
        self.summary_table_name = "emotion_opensmile_summary"
    
    async def fetch_opensmile_data(
        self,
        device_id: str,
        date: str,
        time_slot: str
    ) -> Optional[Dict]:
        """
        指定されたdevice_id、date、time_slotのOpenSMILEデータを取得
        
        Args:
            device_id: デバイスID
            date: 日付 (YYYY-MM-DD形式)
            time_slot: 時間スロット (HH-MM形式)
            
        Returns:
            Dict: OpenSMILEデータ（features_timelineを含む）
        """
        try:
            response = self.supabase.table(self.table_name).select(
                "device_id,date,time_block,filename,duration_seconds,features_timeline,processing_time,error"
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
        指定されたdevice_idとdateの全OpenSMILEデータを取得
        
        Args:
            device_id: デバイスID
            date: 日付 (YYYY-MM-DD形式)
            
        Returns:
            List[Dict]: その日の全OpenSMILEデータのリスト
        """
        try:
            response = self.supabase.table(self.table_name).select(
                "device_id,date,time_block,filename,duration_seconds,features_timeline,processing_time,error"
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
        感情グラフデータをemotion_opensmile_summaryテーブルに保存
        
        Args:
            device_id: デバイスID
            date: 日付 (YYYY-MM-DD形式)
            emotion_graph: 時間スロットごとの感情スコアのリスト（48スロット）
            
        Returns:
            bool: 保存成功時True
        """
        try:
            # レコードデータを作成（ワイド型）
            record = {
                "device_id": device_id,
                "date": date,
                "emotion_graph": emotion_graph  # JSONBとして保存される
            }
            
            # UPSERT実行（既存データがあれば更新、なければ挿入）
            response = self.supabase.table(self.summary_table_name).upsert(
                record,
                on_conflict="device_id,date"
            ).execute()
            
            print(f"✅ Supabase emotion_opensmile_summaryにデータを保存: {device_id}/{date}")
            print(f"   保存スロット数: {len(emotion_graph)}")
            return True
                
        except Exception as e:
            print(f"❌ Supabase保存エラー: {str(e)}")
            return False