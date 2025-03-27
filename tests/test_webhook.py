"""
測試TradingView webhook的工具

這個腳本用於模擬TradingView發送的webhook請求，幫助測試系統功能
"""
import requests
import json
import argparse
import logging

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def send_test_webhook(url: str, message: str):
    """
    發送測試webhook到指定URL
    
    參數:
        url: webhook接收端點
        message: 要發送的交易信號
    """
    try:
        logger.info(f"發送測試webhook到 {url}")
        logger.info(f"訊息內容: {message}")
        
        # 準備請求數據
        payload = {"message": message}
        headers = {"Content-Type": "application/json"}
        
        # 發送POST請求
        response = requests.post(url, json=payload, headers=headers)
        
        # 輸出結果
        logger.info(f"狀態碼: {response.status_code}")
        logger.info(f"回應: {response.text}")
        
        # 格式化輸出JSON回應（如果是JSON格式）
        try:
            json_response = response.json()
            logger.info(f"JSON回應: {json.dumps(json_response, indent=4, ensure_ascii=False)}")
        except:
            pass
        
        return response
    except Exception as e:
        logger.error(f"發送webhook時發生錯誤: {e}", exc_info=True)
        return None

def main():
    """主程序"""
    parser = argparse.ArgumentParser(description="發送測試TradingView webhook")
    parser.add_argument("--url", default="http://localhost:8000/webhook/tradingview", help="webhook URL")
    parser.add_argument("--action", choices=["buy", "sell", "invalid_action"], default="buy", help="交易動作")
    parser.add_argument("--symbol", choices=["小台指", "台積電期", "那斯達克100", "黃金", "invalid_symbol"], default="小台指", help="交易商品")
    parser.add_argument("--quantity", type=int, default=1, help="合約數量")
    parser.add_argument("--format", choices=["valid", "invalid"], default="valid", help="訊息格式")
    
    args = parser.parse_args()
    
    # 構建訊息（模擬TradingView格式）
    if args.action == "buy":
        action_text = "買入"
    elif args.action == "sell":
        action_text = "賣出"
    else:
        action_text = "未知操作"  # 無效操作類型
    
    # 根據格式類型構建消息
    if args.format == "valid":
        message = f"SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單{action_text} @ {args.quantity}已成交{args.symbol}。新策略倉位是{args.quantity}"
    else:
        # 無效格式
        message = f"SuperTrend + QQE 策略 - 波動過濾版：{action_text} {args.quantity} {args.symbol}"
    
    # 發送測試webhook
    send_test_webhook(args.url, message)

if __name__ == "__main__":
    main()
