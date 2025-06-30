#!/usr/bin/env python3
"""
OpenSMILE（感情分析）データ集計ツール

Vault API上のOpenSMILE特徴量JSONファイルを収集し、
eGeMapsベースの感情スコアリングで日次集計結果をローカルに保存する。
30分スロット単位で最大48個のファイルを非同期処理で取得・解析する。
"""

import asyncio
import aiohttp
import json
import os
import ssl
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import argparse

from emotion_scoring import EmotionScorer


class OpenSMILEAggregator:
    """OpenSMILE データ集計クラス"""
    
    def __init__(self, base_url: str = "https://api.hey-watch.me/download-opensmile", verify_ssl: bool = True):
        self.base_url = base_url
        self.verify_ssl = verify_ssl
        self.time_slots = self._generate_time_slots()
        self.emotion_scorer = EmotionScorer()
        
        # SSL設定を準備
        if not self.verify_ssl:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self.ssl_context = None
    
    def _generate_time_slots(self) -> List[str]:
        """30分スロットのリストを生成（00-00 から 23-30 まで）"""
        slots = []
        for hour in range(24):
            for minute in [0, 30]:
                slots.append(f"{hour:02d}-{minute:02d}")
        return slots
    
    def _build_url(self, user_id: str, date: str, time_slot: str) -> str:
        """指定されたパラメータからOpenSMILE専用Vault API URLを構築"""
        return f"{self.base_url}?user_id={user_id}&date={date}&slot={time_slot}"
    
    async def _fetch_json(self, session: aiohttp.ClientSession, url: str) -> Optional[Dict]:
        """単一のOpenSMILE JSONファイルを非同期で取得"""
        try:
            print(f"🔍 取得開始: {url}")
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                print(f"📊 レスポンス状態: {response.status} - {url}")
                if response.status == 404:
                    print(f"ファイルが存在しません: {url}")
                    return None
                if response.status != 200:
                    print(f"HTTPエラー {response.status}: {url}")
                    return None
                
                content = await response.text()
                if not content.strip():
                    print(f"空のファイル: {url}")
                    return None
                
                print(f"✅ JSON解析開始: {url} (content length: {len(content)})")
                json_data = await response.json()
                print(f"🎉 JSON解析成功: {url}")
                return json_data
                
        except asyncio.TimeoutError:
            print(f"⏰ タイムアウト: {url}")
            return None
        except aiohttp.ClientError as e:
            print(f"🔌 接続エラー: {url}, {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析エラー: {url}, {e}")
            return None
        except Exception as e:
            print(f"💥 予期しないエラー: {url}, {e}")
            return None
    
    async def fetch_all_data(self, user_id: str, date: str) -> Dict[str, Dict]:
        """指定日の全OpenSMILEデータを並列取得"""
        print(f"データ取得開始: user_id={user_id}, date={date}")
        
        results = {}
        
        # SSL設定を含むConnectorを作成
        connector = aiohttp.TCPConnector(
            ssl=self.ssl_context if not self.verify_ssl else True,
            limit=100,
            limit_per_host=30
        )
        
        async with aiohttp.ClientSession(connector=connector) as session:
            # 全スロットのタスクを並列実行
            tasks = []
            for slot in self.time_slots:
                url = self._build_url(user_id, date, slot)
                task = self._fetch_json(session, url)
                tasks.append((slot, task))
            
            # 結果を収集
            for slot, task in tasks:
                data = await task
                if data is not None:
                    results[slot] = data
                    print(f"取得完了: {slot}")
        
        print(f"データ取得完了: {len(results)}/{len(self.time_slots)} ファイル")
        return results
    
    def process_emotion_scores(self, slot_data: Dict[str, Dict]) -> Dict[str, Dict[str, int]]:
        """OpenSMILEデータから感情スコアを計算"""
        print("感情スコア処理開始...")
        
        slot_scores = {}
        total_emotions = 0
        
        for slot, opensmile_data in slot_data.items():
            try:
                # OpenSMILEデータから感情スコアを計算
                emotion_scores = self.emotion_scorer.process_opensmile_data(opensmile_data)
                slot_scores[slot] = emotion_scores
                
                # 統計情報
                total_score = sum(emotion_scores.values())
                total_emotions += total_score
                print(f"スロット {slot}: 感情スコア合計 {total_score}")
                
            except Exception as e:
                print(f"❌ スロット {slot} の感情分析エラー: {e}")
                # エラー時は全て0
                slot_scores[slot] = {emotion: 0 for emotion in self.emotion_scorer.emotions}
        
        print(f"感情スコア処理完了: 総感情ポイント数 {total_emotions}")
        return slot_scores
    
    def save_result(self, result: Dict, user_id: str, date: str) -> str:
        """結果をローカルファイルに保存"""
        # 保存パスを構築
        base_path = Path(f"/Users/kaya.matsumoto/data/data_accounts/{user_id}/{date}/opensmile-summary")
        base_path.mkdir(parents=True, exist_ok=True)
        
        output_path = base_path / "result.json"
        
        # JSON保存
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"結果保存完了: {output_path}")
        return str(output_path)
    
    async def run(self, user_id: str, date: str) -> str:
        """メイン処理実行"""
        print(f"OpenSMILE感情分析集計処理開始: {user_id}, {date}")
        
        # データ取得
        slot_data = await self.fetch_all_data(user_id, date)
        
        if not slot_data:
            print("取得できたデータがありません")
            return ""
        
        # 感情スコア計算
        slot_scores = self.process_emotion_scores(slot_data)
        
        # 1日分のグラフデータ生成
        result = self.emotion_scorer.generate_full_day_data(slot_scores, date)
        
        # 結果保存
        output_path = self.save_result(result, user_id, date)
        
        print("OpenSMILE感情分析集計処理完了")
        return output_path


async def main():
    """コマンドライン実行用メイン関数"""
    parser = argparse.ArgumentParser(description="OpenSMILE感情分析データ集計ツール")
    parser.add_argument("user_id", help="ユーザーID（例: user123）")
    parser.add_argument("date", help="対象日付（YYYY-MM-DD形式）")
    parser.add_argument("--base-url", default="https://api.hey-watch.me/download-opensmile", help="OpenSMILE専用Vault API ベースURL")
    
    args = parser.parse_args()
    
    # 日付形式検証
    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print("エラー: 日付はYYYY-MM-DD形式で指定してください")
        return
    
    # 集計実行
    aggregator = OpenSMILEAggregator(args.base_url)
    output_path = await aggregator.run(args.user_id, args.date)
    
    if output_path:
        print(f"\n✅ 処理完了")
        print(f"結果ファイル: {output_path}")
    else:
        print("\n❌ 処理失敗")


if __name__ == "__main__":
    asyncio.run(main())