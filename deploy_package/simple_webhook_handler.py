"""
簡化版 TradingView Webhook 處理程序

專為 AWS Lambda 環境設計，移除 FastAPI 依賴，
直接處理來自 API Gateway 的 HTTPS 請求。
"""
import os
import json
import logging
import traceback
import time
import base64
from typing import Dict, Any, Optional

# 導入必要的模組
from webhook.parser import parse_tradingview_signal
from fubon_api.client import FubonClient
from config import settings

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_webhook(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    處理 TradingView webhook 請求的主要函數
    
    Args:
        event: AWS Lambda 事件對象
        context: AWS Lambda 上下文
        
    Returns:
        適合 API Gateway 的回應格式
    """
    try:
        # 記錄基本請求信息
        logger.info(f"收到請求: {event.get('httpMethod', 'UNKNOWN')} {event.get('path', 'UNKNOWN')}")
        
        # 解析請求體
        body = event.get("body", "{}")
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body).decode('utf-8')
            
        # 解析 JSON
        try:
            if isinstance(body, str):
                payload = json.loads(body)
            else:
                payload = body
        except json.JSONDecodeError as e:
            logger.error(f"無法解析 JSON: {e}")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "status": "error",
                    "message": "無效的 JSON 格式"
                })
            }
        
        # 取得訊息
        message = ""
        if isinstance(payload, dict):
            message = payload.get("message", "")
        
        if not message:
            logger.error("請求內容缺少 'message' 欄位或欄位為空")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "status": "error",
                    "message": "請求格式不正確，缺少有效的 'message' 欄位"
                })
            }
            
        logger.info(f"收到 TradingView 訊號: {message}")
        
        # 處理交易訊號
        mock_enabled = os.environ.get("ENABLE_MOCK", "false").lower() == "true"
        logger.info(f"模擬模式狀態: {mock_enabled}")
        
        # 解析交易信號
        trade_info = parse_tradingview_signal(message)
        if not trade_info:
            logger.warning("無法解析交易信號")
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "status": "error",
                    "message": "無法解析交易信號"
                })
            }
            
        logger.info(f"解析後的交易資訊: {trade_info}")
        
        # 建立富邦客戶端並執行下單
        try:
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
            
            # 返回成功結果
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "status": "success",
                    "message": "訂單已提交",
                    "received": message,
                    "mock_mode": mock_enabled,
                    "order_result": order_result,
                    "timestamp": str(time.time())
                })
            }
        except Exception as e:
            logger.error(f"執行下單操作時發生錯誤: {e}")
            logger.error(traceback.format_exc())
            return {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "application/json"
                },
                "body": json.dumps({
                    "status": "error",
                    "message": f"執行下單時發生錯誤: {str(e)}",
                    "received": message,
                    "timestamp": str(time.time())
                })
            }
            
    except Exception as e:
        logger.error(f"處理 webhook 時發生錯誤: {e}")
        logger.error(traceback.format_exc())
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "status": "error",
                "message": f"處理請求時發生錯誤: {str(e)}"
            })
        }

# 健康檢查處理函數
def health_check(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    健康檢查端點
    
    Args:
        event: AWS Lambda 事件對象
        context: AWS Lambda 上下文
        
    Returns:
        健康狀態回應
    """
    try:
        logger.info("處理健康檢查請求")
        
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "status": "ok",
                "message": "服務正常運作中",
                "env": os.environ.get("APP_ENV", "未知"),
                "mock_mode": os.environ.get("ENABLE_MOCK", "未設置"),
                "timestamp": str(time.time())
            })
        }
    except Exception as e:
        logger.error(f"處理健康檢查請求時發生錯誤: {e}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "status": "error",
                "message": f"處理健康檢查時發生錯誤: {str(e)}"
            })
        }

# Lambda 處理程序入口點
def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda 函數處理程序
    
    Args:
        event: AWS Lambda 事件對象
        context: AWS Lambda 上下文
        
    Returns:
        API Gateway 回應格式
    """
    # 記錄基本事件信息
    try:
        if 'httpMethod' in event:
            logger.info(f"收到 HTTP 事件: {event['httpMethod']} {event.get('path', '未知路徑')}")
        elif 'requestContext' in event and 'http' in event['requestContext']:
            logger.info(f"收到 HTTP API 事件: {event['requestContext']['http']['method']} {event['requestContext']['http'].get('path', '未知路徑')}")
        else:
            keys = list(event.keys())
            logger.info(f"收到非 HTTP 事件，包含鍵: {keys}")
    except Exception as e:
        logger.error(f"記錄事件信息時發生錯誤: {e}")
    
    # 獲取請求路徑
    path = None
    if 'path' in event:
        path = event['path']
    elif 'requestContext' in event and 'http' in event['requestContext']:
        path = event['requestContext']['http'].get('path')
    
    logger.info(f"處理請求路徑: {path}")
        
    # 根據路徑處理請求
    if path:
        if path.endswith('/health'):
            logger.info("處理健康檢查請求")
            return health_check(event, context)
        
        elif '/webhook' in path or '/tradingview' in path:
            logger.info("處理 webhook 請求")
            return process_webhook(event, context)
    
    # 如果不是專門處理的路徑，返回 404
    logger.warning(f"未知路徑: {path}")
    return {
        "statusCode": 404,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "status": "error",
            "message": "未找到請求的資源"
        })
    }
