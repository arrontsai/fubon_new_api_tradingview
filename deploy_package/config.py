"""
配置模組 - 管理系統的各種配置項
用於載入和提供環境變數、API配置以及其他系統設定
"""
import os
import logging
import sys
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 設置基本日誌格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# 從命令行參數獲取環境設定
if len(sys.argv) > 1 and sys.argv[1] in ["development", "test", "production"]:
    ENV = sys.argv[1]
    # 設置環境變數
    os.environ["APP_ENV"] = ENV
else:
    # 使用環境變數或預設值
    ENV = os.getenv("APP_ENV", "development")

# 選擇對應環境的配置文件
env_files = {
    "development": ".env_development",
    "test": ".env_test",
    "production": ".env_production"
}
env_file = env_files.get(ENV, ".env_development")

# 檢查配置文件是否存在
if not os.path.exists(env_file):
    logging.warning(f"配置文件 {env_file} 不存在，使用預設配置文件 .env_development")
    env_file = ".env_development"
    if not os.path.exists(env_file):
        logging.error(f"預設配置文件 {env_file} 也不存在！將使用環境變數或預設值")

# 載入環境變數
load_dotenv(env_file)

# 輔助函數：轉換字符串到布爾值
def str_to_bool(value: str) -> bool:
    return str(value).lower() in ("true", "t", "yes", "y", "1")

# 輔助函數：轉換字符串到整數，失敗時返回預設值
def str_to_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

class Settings:
    """應用程式配置類"""
    
    def __init__(self):
        # 環境設置
        self.APP_ENV = ENV
        
        # 富邦API設置
        self.CERT_PATH = os.getenv("FUBON_CERT_PATH", "reference/S124709364.pfx")
        self.CERT_PASSWORD = os.getenv("FUBON_CERT_PASSWORD", "")
        self.PERSONAL_ID = os.getenv("FUBON_PERSONAL_ID", "")
        self.PASSWORD = os.getenv("FUBON_PASSWORD", "")
        
        # 日誌設置
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
        
        # 模擬交易設置
        self.ENABLE_MOCK = str_to_bool(os.getenv("ENABLE_MOCK", "False"))
        
        # 伺服器設置
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = str_to_int(os.getenv("PORT", "8000"))
        self.USE_HTTPS = str_to_bool(os.getenv("USE_HTTPS", "False"))
        self.SSL_CERT = os.getenv("SSL_CERT", "ssl/cert.pem")
        self.SSL_KEY = os.getenv("SSL_KEY", "ssl/key.pem")
        
        # 期貨交易相關設定
        self.DEFAULT_MARKET = os.getenv("DEFAULT_MARKET", "TW")  # 預設市場
        
        # 期貨商品代碼映射
        self.SYMBOL_MAPPING: Dict[str, str] = {
            "小台指": "MXF",   # 小型台指期貨
            "台積電期": "TXF",  # 台積電期貨
            "那斯達克100": "NQF"  # 那斯達克100期貨
        }
        
        # API限制設定
        self.MAX_RETRY_COUNT = str_to_int(os.getenv("MAX_RETRY_COUNT", "3"))
        self.REQUEST_TIMEOUT = str_to_int(os.getenv("REQUEST_TIMEOUT", "30"))
        
        # 密鑰設定(用於保護webhook端點)
        self.WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
        
        # AWS設置
        self.AWS_REGION = os.getenv("AWS_REGION", "ap-northeast-1")
        self.LAMBDA_FUNCTION_NAME = os.getenv("LAMBDA_FUNCTION_NAME", "fubon-trade-api")
        self.API_GATEWAY_NAME = os.getenv("API_GATEWAY_NAME", "fubon-trade-api")
        self.S3_BUCKET = os.getenv("S3_BUCKET", "")
        
        # 通知設置
        self.ENABLE_NOTIFICATION = str_to_bool(os.getenv("ENABLE_NOTIFICATION", "False"))
        self.LINE_NOTIFY_TOKEN = os.getenv("LINE_NOTIFY_TOKEN", "")
        self.TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
        
        # 開發設置
        self.DEBUG = str_to_bool(os.getenv("DEBUG", "False"))
        self.RELOAD_ON_CHANGE = str_to_bool(os.getenv("RELOAD_ON_CHANGE", "True")) and ENV != "production"
    
    def __str__(self) -> str:
        """返回設定的字符串表示"""
        return f"Settings(APP_ENV={self.APP_ENV}, ENABLE_MOCK={self.ENABLE_MOCK})"
    
    def to_dict(self) -> Dict[str, Any]:
        """將設定轉換為字典"""
        return {
            key: value for key, value in self.__dict__.items() 
            if not key.startswith('_') and key.isupper()
        }

# 創建設定實例
settings = Settings()

# 輸出當前環境信息
logging.info(f"載入環境: {settings.APP_ENV}")
logging.info(f"模擬模式: {'啟用' if settings.ENABLE_MOCK else '關閉'}")
logging.info(f"日誌級別: {settings.LOG_LEVEL}")
