# -*- coding: utf-8 -*-
"""
TradingView Webhook 測試腳本

用於模擬 TradingView 發送的 webhook 請求。
"""
import requests
import json
import time

# API Gateway URL
URL = "https://3h0ebe25p5.execute-api.ap-northeast-1.amazonaws.com/prod/webhook/tradingview"

# 測試數據 (模擬 TradingView 發送的訊息)
PAYLOAD = {
    "message": "快訊： SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單sell @ 1已成交MXF1!。新策略倉位是-1"
}

def test_webhook():
    """發送測試 webhook 請求"""
    print(f"發送 webhook 請求到: {URL}")
    print(f"請求內容: {json.dumps(PAYLOAD, indent=2, ensure_ascii=False)}")
    
    try:
        # 發送 POST 請求
        response = requests.post(URL, json=PAYLOAD)
        
        # 輸出結果
        print(f"狀態碼: {response.status_code}")
        print(f"回應內容:")
        
        try:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(response.text)
            
    except Exception as e:
        print(f"發送請求時發生錯誤: {e}")

if __name__ == "__main__":
    test_webhook()
