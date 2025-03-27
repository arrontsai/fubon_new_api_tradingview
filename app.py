"""
富邦期貨交易API與TradingView Webhook整合系統 - 主應用程式

這個模組是系統的入口點，負責設置FastAPI服務並處理來自TradingView的webhook請求。
"""
import os
import logging
import json
import sys
import ssl
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

from webhook.parser import parse_tradingview_signal
from fubon_api.client import FubonClient
from config import settings

# 獲取命令行參數
env_override = None
if len(sys.argv) > 1 and sys.argv[1] in ["development", "test", "production"]:
    env_override = sys.argv[1]
    os.environ["APP_ENV"] = env_override

# 設置日誌
log_level = getattr(logging, settings.LOG_LEVEL)
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"app_{settings.APP_ENV}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 輸出環境信息
logger.info(f"當前運行環境: {settings.APP_ENV}")
logger.info(f"模擬模式: {'啟用' if settings.ENABLE_MOCK else '關閉'}")
logger.info(f"HTTPS模式: {'啟用' if settings.USE_HTTPS else '關閉'}")

# 創建FastAPI應用
app = FastAPI(
    title="富邦期貨交易API與TradingView Webhook整合系統",
    description="接收TradingView的交易信號並通過富邦API執行期貨交易",
    version="0.1.0"
)

# 依賴注入：獲取富邦客戶端
def get_fubon_client():
    """建立並返回富邦API客戶端"""
    try:
        client = FubonClient(
            cert_path=settings.CERT_PATH,
            cert_password=settings.CERT_PASSWORD,
            personal_id=settings.PERSONAL_ID,
            password=settings.PASSWORD
        )
        return client
    except Exception as e:
        logger.error(f"無法初始化富邦客戶端: {e}")
        raise HTTPException(status_code=500, detail="富邦API服務暫時不可用")

# Webhook請求模型
class WebhookRequest(BaseModel):
    """TradingView Webhook請求模型"""
    message: str

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: WebhookRequest, fubon_client: FubonClient = Depends(get_fubon_client)):
    """
    處理來自TradingView的webhook請求
    
    接收格式例如：
    SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單買入 @ 1已成交小台指。新策略倉位是1
    """
    try:
        logger.info(f"收到TradingView webhook: {request.message}")
        
        # 解析交易信號
        trade_info = parse_tradingview_signal(request.message)
        if not trade_info:
            return JSONResponse(
                status_code=400, 
                content={"status": "error", "message": "無法解析交易信號"}
            )
        
        logger.info(f"解析的交易信息: {trade_info}")
        
        # 執行交易操作
        order_result = fubon_client.place_order(
            symbol=trade_info["symbol"],
            action=trade_info["action"],
            quantity=trade_info["quantity"]
        )
        
        # 返回處理結果
        return {
            "status": "success",
            "message": "訂單已提交",
            "data": order_result
        }
        
    except Exception as e:
        logger.error(f"處理webhook時發生錯誤: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"處理請求時發生錯誤: {str(e)}"}
        )

@app.get("/health")
async def health_check():
    """健康檢查端點"""
    return {
        "status": "ok", 
        "version": "0.1.0",
        "environment": settings.APP_ENV,
        "mock_mode": settings.ENABLE_MOCK,
        "https_mode": settings.USE_HTTPS
    }

def check_ssl_cert_files():
    """檢查SSL憑證文件是否存在"""
    if settings.USE_HTTPS:
        cert_exists = os.path.exists(settings.SSL_CERT_PATH)
        key_exists = os.path.exists(settings.SSL_KEY_PATH)
        
        if not cert_exists:
            logger.error(f"SSL憑證文件不存在: {settings.SSL_CERT_PATH}")
        if not key_exists:
            logger.error(f"SSL密鑰文件不存在: {settings.SSL_KEY_PATH}")
            
        return cert_exists and key_exists
    return True

def get_webhook_url():
    """獲取webhook的完整URL"""
    protocol = "https" if settings.USE_HTTPS else "http"
    host = settings.HOST if settings.HOST != "0.0.0.0" else "localhost"
    port = settings.PORT
    
    # 標準端口可以省略
    if (protocol == "http" and port == 80) or (protocol == "https" and port == 443):
        return f"{protocol}://{host}/webhook/tradingview"
    else:
        return f"{protocol}://{host}:{port}/webhook/tradingview"

if __name__ == "__main__":
    # 啟動服務
    logger.info(f"啟動服務於環境: {settings.APP_ENV}, 模擬模式: {'啟用' if settings.ENABLE_MOCK else '關閉'}")
    
    # 確認SSL憑證
    if settings.USE_HTTPS and not check_ssl_cert_files():
        logger.error("無法啟用HTTPS: SSL憑證文件不存在或不可訪問")
        sys.exit(1)
    
    # 顯示webhook URL
    webhook_url = get_webhook_url()
    logger.info(f"TradingView webhook URL: {webhook_url}")
    logger.info("請在 TradingView 警報設置中使用此 URL")
    
    # 啟動uvicorn服務器
    try:
        uvicorn.run(
            "app:app", 
            host=settings.HOST, 
            port=settings.PORT, 
            reload=settings.RELOAD_ON_CHANGE,
            ssl_keyfile=settings.SSL_KEY_PATH if settings.USE_HTTPS else None,
            ssl_certfile=settings.SSL_CERT_PATH if settings.USE_HTTPS else None
        )
    except Exception as e:
        logger.error(f"啟動服務時發生錯誤: {e}")
        if settings.USE_HTTPS and "SSL" in str(e):
            logger.error("HTTPS啟動失敗，請檢查SSL憑證和密鑰文件")
            logger.info("如果在Windows上使用低於1024的端口，請確保以管理員身份運行")
        sys.exit(1)
