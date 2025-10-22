#!/usr/bin/env python3
"""
感情スコアリングエンジン (wav2vec2対応版)

wav2vec2の感情分類結果（4感情）を既存の8感情体系にマッピングする。
OpenSMILE形式との後方互換性を保ちながら、新しいAIモデルの結果を処理。
"""

import yaml
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime


class EmotionScorer:
    """感情スコアリングクラス"""
    
    def __init__(self, rules_path: str = "emotion_scoring_rules.yaml"):
        self.rules_path = rules_path
        self.rules = self._load_rules()
        self.emotions = ["anger", "fear", "anticipation", "surprise", "joy", "sadness", "trust", "disgust"]
        
        # wav2vec2の4感情から8感情へのマッピング定義
        self.emotion_mapping = {
            'ang': {  # 怒り
                'anger': 1.0,      # 直接マッピング
                'disgust': 0.3,    # 怒りは嫌悪感も含む
                'fear': 0.1        # 軽い恐怖感も含む可能性
            },
            'sad': {  # 悲しみ
                'sadness': 1.0,    # 直接マッピング
                'fear': 0.2,       # 悲しみは不安も含む
                'trust': -0.3      # 信頼感の低下
            },
            'neu': {  # 中立
                'trust': 0.5,      # 中立は安定した信頼感
                'anticipation': 0.2 # 軽い期待感
            },
            'hap': {  # 喜び
                'joy': 1.0,        # 直接マッピング
                'surprise': 0.3,   # 喜びは驚きも含む
                'anticipation': 0.4,  # 期待感も含む
                'trust': 0.5       # 信頼感も高まる
            }
        }
    
    def _load_rules(self) -> Dict[str, Any]:
        """YAMLルールファイルを読み込み"""
        try:
            with open(self.rules_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            print(f"⚠️ ルールファイルが見つかりません: {self.rules_path}")
            return {"emotions": {}}
        except yaml.YAMLError as e:
            print(f"⚠️ YAMLパースエラー: {e}")
            return {"emotions": {}}
    
    def _evaluate_rule(self, features: Dict[str, float], rule: Dict[str, Any]) -> bool:
        """単一ルールの評価"""
        feature_name = rule.get('feature')
        if not feature_name or feature_name not in features:
            return False
        
        value = features[feature_name]
        op = rule.get('op')
        th = rule.get('th')
        
        if op is None or th is None:
            return False
        
        # 基本比較
        if op == ">" and value <= th:
            return False
        elif op == "<" and value >= th:
            return False
        elif op == "==" and value != th:
            return False
        
        # 範囲チェック（op2, th2がある場合）
        op2 = rule.get('op2')
        th2 = rule.get('th2')
        if op2 and th2 is not None:
            if op2 == ">" and value <= th2:
                return False
            elif op2 == "<" and value >= th2:
                return False
            elif op2 == "==" and value != th2:
                return False
        
        return True
    
    def score_features(self, features: Dict[str, float]) -> Dict[str, int]:
        """特徴量から感情スコアを計算"""
        scores = {emotion: 0 for emotion in self.emotions}
        
        for emotion in self.emotions:
            emotion_rules = self.rules.get("emotions", {}).get(emotion, [])
            
            for rule in emotion_rules:
                if self._evaluate_rule(features, rule):
                    scores[emotion] += self.rules.get("meta", {}).get("max_points_per_rule", 1)
        
        return scores
    
    def process_opensmile_data(self, opensmile_data: Dict[str, Any]) -> Dict[str, int]:
        """OpenSMILEのJSONデータから感情スコアを抽出（後方互換性用）"""
        # OpenSMILEのJSON構造に応じて特徴量を抽出
        # 通常は "features" や "data" キーの下にある
        features = {}
        
        # データ構造を探索してeGeMAPS特徴量を抽出
        def extract_features(obj, prefix=""):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if isinstance(value, (int, float)):
                        # eGeMAPS特徴量名にマッチする場合
                        if any(pattern in key for pattern in [
                            "Loudness_sma3", "shimmerLocaldB_sma3nz", "HNRdBACF_sma3nz",
                            "jitterLocal_sma3nz", "F0semitoneFrom27.5Hz_sma3nz", 
                            "spectralFlux_sma3", "mfcc", "alphaRatio_sma3",
                            "HammarbergIndex_sma3", "logRelF0", "slope500-1500_sma3"
                        ]):
                            features[key] = float(value)
                    elif isinstance(value, (dict, list)):
                        extract_features(value, f"{prefix}{key}_")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    extract_features(item, f"{prefix}{i}_")
        
        extract_features(opensmile_data)
        
        # 特徴量が見つからない場合の処理
        if not features:
            print(f"⚠️ eGeMAPS特徴量が見つかりません。利用可能なキー: {list(opensmile_data.keys())}")
            return {emotion: 0 for emotion in self.emotions}
        
        return self.score_features(features)
    
    def process_wav2vec2_data(self, emotion_data: Dict[str, Any]) -> Dict[str, int]:
        """wav2vec2の感情分類結果から8感情スコアを計算"""
        # 初期化
        scores = {emotion: 0 for emotion in self.emotions}
        
        # wav2vec2の感情スコアを取得
        wav2vec2_scores = emotion_data.get('emotion_scores', {})
        
        if not wav2vec2_scores:
            print(f"⚠️ wav2vec2感情スコアが見つかりません")
            return scores
        
        # 4感情から8感情へマッピング
        for wav2vec2_emotion, score_value in wav2vec2_scores.items():
            if wav2vec2_emotion in self.emotion_mapping:
                # スコアを0-100の範囲に変換（wav2vec2は0-1の確率値）
                base_score = int(score_value * 100)
                
                # マッピング定義に従って8感情に分配
                for target_emotion, weight in self.emotion_mapping[wav2vec2_emotion].items():
                    if weight > 0:
                        # 正の重みは加算
                        scores[target_emotion] += int(base_score * weight)
                    elif weight < 0:
                        # 負の重みは減算（ただし0未満にはしない）
                        scores[target_emotion] = max(0, scores[target_emotion] + int(base_score * weight))
        
        # スコアを適切な範囲に正規化（0-10の範囲に収める）
        max_score = max(scores.values()) if max(scores.values()) > 0 else 1
        if max_score > 10:
            normalization_factor = 10 / max_score
            scores = {emotion: int(score * normalization_factor) for emotion, score in scores.items()}
        
        return scores
    
    def create_time_slot_data(self, time_slot: str, emotion_scores: Dict[str, int]) -> Dict[str, Any]:
        """時間スロット用のデータ構造を作成"""
        return {
            "time": f"{time_slot[:2]}:{time_slot[3:]}",  # "00-00" -> "00:00"
            **emotion_scores
        }
    
    def generate_full_day_data(self, slot_scores: Dict[str, Dict[str, int]], date: str) -> Dict[str, Any]:
        """1日分の感情グラフデータを生成（48スロット）"""
        time_slots = []
        for hour in range(24):
            for minute in [0, 30]:
                time_slots.append(f"{hour:02d}-{minute:02d}")
        
        emotion_graph = []
        for slot in time_slots:
            if slot in slot_scores:
                # データがある場合
                emotion_data = self.create_time_slot_data(slot, slot_scores[slot])
            else:
                # データがない場合は全て0
                emotion_data = self.create_time_slot_data(slot, {emotion: 0 for emotion in self.emotions})
            
            emotion_graph.append(emotion_data)
        
        return {
            "date": date,
            "emotion_graph": emotion_graph
        }


def main():
    """テスト用メイン関数"""
    scorer = EmotionScorer()
    
    # サンプル特徴量でテスト
    sample_features = {
        "Loudness_sma3": 0.35,
        "shimmerLocaldB_sma3nz": 0.45,
        "HNRdBACF_sma3nz": 0.8,
        "logRelF0-H1-A3_sma3nz": 12.0
    }
    
    scores = scorer.score_features(sample_features)
    print("感情スコア:", scores)
    
    # 1日分のデータ生成テスト
    slot_scores = {
        "04-30": {"anger": 4, "fear": 1, "anticipation": 2, "surprise": 1, "joy": 1, "sadness": 1, "trust": 1, "disgust": 1},
        "07-00": {"anger": 0, "fear": 0, "anticipation": 2, "surprise": 1, "joy": 8, "sadness": 0, "trust": 4, "disgust": 0}
    }
    
    full_day = scorer.generate_full_day_data(slot_scores, "2025-06-26")
    print(f"\n1日分データ: {len(full_day['emotion_graph'])} スロット")


if __name__ == "__main__":
    main()