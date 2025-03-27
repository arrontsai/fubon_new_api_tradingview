"""
配置模組 - 管理系統的各種配置項
用於載入和提供環境變數、API配置以及其他系統設定
"""
import os
import logging
import sys
from typing import Dict, Optional, List
from pydantic_settings import BaseSettings

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
from dotenv import load_dotenv
load_dotenv(env_file)

class Settings(BaseSettings):
    """應用程式配置類"""
    # 環境設置
    APP_ENV: str = ENV
    
    # 富邦API設置
    CERT_PATH: str = os.getenv("FUBON_CERT_PATH", "reference/S124709364.pfx")
    CERT_PASSWORD: str = os.getenv("FUBON_CERT_PASSWORD", "")
    PERSONAL_ID: str = os.getenv("FUBON_PERSONAL_ID", "")  # 個人ID（登入用）
    PASSWORD: str = os.getenv("FUBON_PASSWORD", "")  # 登入密碼
    
    # 商品代碼對照表
    SYMBOL_MAP: Dict[str, str] = {
        "小台指": "MXF",    # 小型台指期貨
        "台積電期": "TXF",   # 台積電期貨
        "那斯達克100": "NQF"  # 那斯達克100期貨
    }
    
    # API限制設定
    MAX_RETRY_COUNT: int = 3
    REQUEST_TIMEOUT: int = 30
    
    # 密鑰設定(用於保護webhook端點)
    WEBHOOK_SECRET: str = os.getenv("WEBHOOK_SECRET", "")
    
    # 日誌設定
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # 模擬模式設定
    ENABLE_MOCK: bool = os.getenv("ENABLE_MOCK", "False").lower() in ("true", "1", "yes")
    
    # 服務設定
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # HTTPS設定
    USE_HTTPS: bool = os.getenv("USE_HTTPS", "False").lower() in ("true", "1", "yes")
    SSL_CERT_PATH: str = os.getenv("SSL_CERT_PATH", "certs/cert.pem")
    SSL_KEY_PATH: str = os.getenv("SSL_KEY_PATH", "certs/key.pem")
    
    # 開發模式設定
    RELOAD_ON_CHANGE: bool = os.getenv("RELOAD_ON_CHANGE", "True").lower() in ("true", "1", "yes") and ENV != "production"
    
    # Pydantic 2.x配置
    model_config = {
        "env_file": env_file,
        "extra": "ignore"  # 忽略額外的輸入
    }

# 創建設定實例
settings = Settings()

# 輸出當前環境信息
logging.info(f"當前運行環境: {settings.APP_ENV}")
logging.info(f"使用配置文件: {env_file}")
logging.info(f"模擬模式: {'啟用' if settings.ENABLE_MOCK else '關閉'}")
logging.info(f"HTTPS: {'啟用' if settings.USE_HTTPS else '關閉'}")
