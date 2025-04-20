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

# Lambda 強制 production 環境，不載入任何 .env 檔案
if os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    ENV = "production"
    os.environ["APP_ENV"] = ENV
else:
    # 本地開發/測試可用命令行或環境變數
    if len(sys.argv) > 1 and sys.argv[1] in ["development", "test", "production"]:
        ENV = sys.argv[1]
        os.environ["APP_ENV"] = ENV
    else:
        ENV = os.getenv("APP_ENV", "development")
    # 只有本地才載入 .env
    env_files = {
        "development": ".env_development",
        "test": ".env_test",
        "production": ".env_production"
    }
    env_file = env_files.get(ENV, ".env_development")
    if os.path.exists(env_file):
        load_dotenv(env_file)
    else:
        logging.info(f"未載入任何 .env 檔案，僅用環境變數/Secrets Manager")

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
        # Lambda 啟動時自動載入 Secrets Manager
        self._load_secrets_manager()

    def _load_secrets_manager(self):
        """如 CERT_PATH 為 secrets:xxx，則自動從 Secrets Manager 載入帳密與憑證設定"""
        if isinstance(self.CERT_PATH, str) and self.CERT_PATH.startswith("secrets:"):
            secret_name = self.CERT_PATH[8:]
            try:
                secrets_client = boto3.client('secretsmanager', region_name=self.AWS_REGION)
                response = secrets_client.get_secret_value(SecretId=secret_name)
                if 'SecretString' in response:
                    secret_data = json.loads(response['SecretString'])
                else:
                    secret_data = json.loads(base64.b64decode(response['SecretBinary']))
                # 依照 Secrets Manager 的 key 名稱對應
                self.CERT_PASSWORD = secret_data.get("FUBON_CERT_PASSWORD", self.CERT_PASSWORD)
                self.PERSONAL_ID = secret_data.get("FUBON_PERSONAL_ID", self.PERSONAL_ID)
                self.PASSWORD = secret_data.get("FUBON_PASSWORD", self.PASSWORD)
            except Exception as e:
                logging.error(f"Secrets Manager 載入失敗: {e}")
    
    def __str__(self) -> str:
        """返回設定的字符串表示"""
        return f"Settings(APP_ENV={self.APP_ENV}, ENABLE_MOCK={self.ENABLE_MOCK})"
    
    def to_dict(self) -> Dict[str, Any]:
        """將設定轉換為字典"""
        return {
            key: value for key, value in self.__dict__.items() 
            if isinstance(key, str) and (key.startswith("FUBON") or key in ["ENABLE_MOCK", "APP_ENV"]) and key.isupper()
        }

# 創建設定實例
settings = Settings()

# 輸出當前環境信息
logging.info(f"載入環境: {settings.APP_ENV}")
logging.info(f"模擬模式: {'啟用' if settings.ENABLE_MOCK else '關閉'}")
logging.info(f"日誌級別: {settings.LOG_LEVEL}")
