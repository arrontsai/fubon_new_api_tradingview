"""
簡化版 TradingView Webhook 處理程序

專為 AWS Lambda 環境設計，使用 Serverless Framework 部署，
直接處理來自 API Gateway 的 HTTPS 請求。
"""
import os
import json
import logging
import traceback
import time
import base64
import boto3
import sys
from typing import Dict, Any, Optional

# Lambda 啟動時自動載入 Secrets Manager 並寫入 os.environ

def load_secrets_to_env(secret_name, region_name="ap-northeast-1"):
    import boto3
    import json
    client = boto3.client('secretsmanager', region_name=region_name)
    secret_value = client.get_secret_value(SecretId=secret_name)
    secrets = secret_value.get('SecretString')
    if secrets:
        secrets = json.loads(secrets)
        # 將 Secrets Manager 的 key 寫入 os.environ
        for k, v in secrets.items():
            os.environ[k] = v
        # 如果有 pfx（base64），寫成檔案並設 FUBON_CERT_PATH
        if 'pfx' in secrets:
            cert_path = "/tmp/fubon_cert.pfx"
            import base64
            with open(cert_path, "wb") as f:
                f.write(base64.b64decode(secrets['pfx']))
            os.environ["FUBON_CERT_PATH"] = cert_path

# 僅在 Lambda 環境自動載入
if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
    load_secrets_to_env("fubon/cert")

# 嘗試設置 SDK 環境
try:
    # 檢查是否在 Lambda 環境中
    if os.getenv('AWS_LAMBDA_FUNCTION_NAME'):
        # 添加 Lambda 層路徑
        sys_paths = [
            '/opt/python',
            '/tmp/fubon_sdk'
        ]
        for path in sys_paths:
            if path not in sys.path and os.path.exists(path):
                sys.path.insert(0, path)
    # 確認環境變數
    for key, value in os.environ.items():
        if key.startswith('FUBON_') or key in ['APP_ENV', 'ENABLE_MOCK']:
            logging.info(f'環境變數: {key}={value}')
except Exception as e:
    logging.error(f'設置環境時出錯: {e}')

# 導入必要的模組
from webhook.parser import parse_tradingview_signal
from fubon_api.client import FubonClient
from config import settings
from secret_manager import get_secret

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
        mock_enabled = False
        logger.info("模擬模式已強制關閉，僅走正式下單流程")
        try:
            # 這裡是正式下單流程
            trade_info = parse_tradingview_signal(message)
            if not trade_info:
                logger.warning("無法解析交易信號")
                return {
                    "statusCode": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({
                        "status": "error",
                        "message": "無法解析交易信號"
                    })
                }
            # 呼叫富邦 API 下單（只傳遞必要欄位）
            fubon_client = FubonClient(settings)
            order_args = {k: trade_info[k] for k in ['symbol', 'action', 'quantity'] if k in trade_info}
            order_result = fubon_client.place_order(**order_args)
            logger.info(f"下單結果: {order_result}")

            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "status": "success",
                    "message": "訂單已提交",
                    "received": message,
                    "mock_mode": False,
                    "order_result": order_result
                })
            }
        except Exception as e:
            # 詳細印出錯誤
            logger.error(f"正式下單流程發生錯誤: {e}", exc_info=True)
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "status": "error",
                    "message": f"正式下單流程發生錯誤: {str(e)}"
                })
            }
        
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
        
        # 從 AWS Secrets Manager 獲取憑證
        try:
            # 獲取環境變數中指定的 secrets 名稱
            secrets_name = os.environ.get('SECRETS_NAME', 'fubon/cert')
            secrets = get_secret(secrets_name)
            
            if not secrets:
                logger.error("無法從 AWS Secrets Manager 讀取憑證信息")
                return {
                    "statusCode": 500,
                    "headers": {
                        "Content-Type": "application/json"
                    },
                    "body": json.dumps({
                        "status": "error",
                        "message": "系統配置錯誤，無法讀取憑證"
                    })
                }
            
            logger.info(f"成功從 Secrets Manager 讀取憑證: {secrets_name}")
            
            # 建立富邦客戶端並執行下單
            # 優先使用 Secrets Manager 中的值，如果沒有則使用環境變數
            client = FubonClient(
                cert_path=os.environ.get('FUBON_CERT_PATH', '/opt/python/S124709364.pfx'),
                cert_password=secrets.get('FUBON_CERT_PASSWORD', os.environ.get('FUBON_CERT_PASSWORD', '')),
                personal_id=secrets.get('FUBON_PERSONAL_ID', os.environ.get('FUBON_PERSONAL_ID', '')),
                password=secrets.get('FUBON_PASSWORD', os.environ.get('FUBON_PASSWORD', ''))
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
