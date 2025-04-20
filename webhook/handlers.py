"""
TradingView webhook 處理邏輯模組

這個模組包含用於處理 TradingView webhook 的核心業務邏輯，
被 FastAPI 路由和 Lambda 處理程序共同使用，避免代碼重複和循環引用。
"""
import logging
import time
import json
from typing import Dict, Any, Optional
import os

from webhook.parser import parse_tradingview_signal
from fubon_api.client import FubonClient
from config import settings

# 配置日誌
logger = logging.getLogger(__name__)

def process_tradingview_signal(message: str, use_mock: bool = None) -> Dict[str, Any]:
    """
    處理 TradingView 交易信號的核心邏輯
    
    這個函數負責解析信號、驗證內容並執行交易操作
    會被 FastAPI 路由和 Lambda 處理程序共同調用
    
    Args:
        message: TradingView 發送的交易信號字符串
        use_mock: 是否使用模擬模式，默認為 None 表示使用配置中的設置
        
    Returns:
        返回包含處理結果的字典
        {
            'status_code': int,  # HTTP 狀態碼
            'status': str,       # 狀態 ('success' 或 'error')
            'message': str,      # 處理結果訊息
            'data': Optional[Dict]  # 訂單資料 (僅在成功時)
        }
    """
    try:
        logger.info(f"處理 TradingView 交易信號: {message}")
        
        # 解析交易信號
        trade_info = parse_tradingview_signal(message)
        if not trade_info:
            logger.warning("無法解析交易信號")
            return {
                'status_code': 400,
                'status': 'error',
                'message': '無法解析交易信號'
            }
            
        logger.info(f"解析後的交易資訊: {trade_info}")
        
        # 決定是否使用模擬模式
        if use_mock is None:
            # 使用配置中的設置
            enable_mock = settings.ENABLE_MOCK
        else:
            # 使用傳入的設置
            enable_mock = use_mock
            
        logger.info(f"下單模式: {'模擬' if enable_mock else '實際'}")
        
        # 建立富邦客戶端並執行下單
        client = FubonClient(
            cert_path=settings.CERT_PATH,
            cert_password=settings.CERT_PASSWORD,
            personal_id=settings.PERSONAL_ID,
            password=settings.PASSWORD
        )
        
        # 執行下單操作
        order_result = client.place_order(
            symbol=trade_info["symbol"],
            action=trade_info["action"],
            quantity=trade_info["quantity"]
        )
        
        logger.info(f"訂單結果: {order_result}")
        
        return {
            'status_code': 200,
            'status': 'success',
            'message': '訂單已提交',
            'data': order_result
        }
        
    except Exception as e:
        logger.error(f"處理交易信號時發生錯誤: {e}", exc_info=True)
        return {
            'status_code': 500,
            'status': 'error',
            'message': f'處理請求時發生錯誤: {str(e)}'
        }
