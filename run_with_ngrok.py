"""
使用 ngrok 啟動應用程式 - 創建公開的 HTTPS 端點以供 TradingView 訪問

此腳本會啟動 FastAPI 應用程式，並使用 ngrok 創建一個臨時的公開 HTTPS 端點。
這個端點可以直接用於 TradingView webhook，無需公開 IP 或域名。
"""
import os
import sys
import time
import logging
import threading
from pyngrok import ngrok, conf
import uvicorn
from dotenv import load_dotenv

# 設置基本日誌格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 獲取環境參數
if len(sys.argv) > 1 and sys.argv[1] in ["development", "test", "production"]:
    env = sys.argv[1]
    os.environ["APP_ENV"] = env
else:
    env = os.getenv("APP_ENV", "development")
    
# 載入環境設定
env_file = f".env_{env}"
load_dotenv(env_file)

# 獲取設定
port = int(os.getenv("PORT", "8000"))
host = os.getenv("HOST", "0.0.0.0")
use_https = os.getenv("USE_HTTPS", "False").lower() in ("true", "1", "yes")

# 如果指定了 ngrok 授權碼，則設置它
ngrok_auth_token = os.getenv("NGROK_AUTH_TOKEN")
if ngrok_auth_token:
    conf.get_default().auth_token = ngrok_auth_token
    logger.info("已設置 ngrok 授權碼")
else:
    logger.warning("未設置 ngrok 授權碼，將使用未認證的連接（每日限額和連接時間有限制）")
    logger.info("若要設置授權碼，請在環境變數檔案中添加 NGROK_AUTH_TOKEN")

def start_uvicorn():
    """啟動 uvicorn 伺服器"""
    logger.info(f"正在啟動 uvicorn 伺服器 (環境: {env})")
    
    ssl_args = {}
    if use_https:
        ssl_cert_path = os.getenv("SSL_CERT_PATH")
        ssl_key_path = os.getenv("SSL_KEY_PATH")
        if ssl_cert_path and ssl_key_path:
            logger.info("使用 SSL 憑證啟動本地 HTTPS 伺服器")
            ssl_args = {
                "ssl_keyfile": ssl_key_path,
                "ssl_certfile": ssl_cert_path
            }
    
    uvicorn.run(
        "app:app", 
        host=host, 
        port=port,
        log_level="info",
        **ssl_args
    )

def start_ngrok():
    """啟動 ngrok 隧道"""
    # 等待 uvicorn 啟動
    time.sleep(2)
    
    try:
        # 創建隧道 (使用最新的API格式)
        # 注意: 無需明確指定'https'，ngrok將自動處理
        public_url = ngrok.connect(port)
        
        # 取得並顯示URL
        tunnel_url = public_url.public_url
        logger.info(f"ngrok 隧道已創建: {tunnel_url}")
        logger.info("----------------------------------------------------")
        logger.info(f"TradingView Webhook URL: {tunnel_url}/webhook/tradingview")
        logger.info("請將此 URL 複製到 TradingView 警報設置中")
        logger.info("----------------------------------------------------")
        
        # 持續運行，保持腳本不退出
        while True:
            time.sleep(600)
    except KeyboardInterrupt:
        logger.info("正在關閉 ngrok 隧道...")
    except Exception as e:
        logger.error(f"ngrok 發生錯誤: {e}")
    finally:
        # 關閉隧道
        ngrok.kill()
        
if __name__ == "__main__":
    # 啟動 uvicorn 伺服器（在另一個線程中）
    uvicorn_thread = threading.Thread(target=start_uvicorn)
    uvicorn_thread.daemon = True
    uvicorn_thread.start()
    
    # 啟動 ngrok 隧道（在主線程中）
    try:
        start_ngrok()
    except KeyboardInterrupt:
        logger.info("應用程式已停止")
        sys.exit(0)
