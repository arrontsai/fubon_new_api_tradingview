# 富邦 SDK 安裝腳本
import os
import sys
import subprocess
import logging
import glob
import traceback

# 設置日誌
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sdk_setup")

def setup_sdk():
    """設置 SDK 環境"""
    try:
        # 記錄環境信息
        logger.info(f"當前環境變數:")
        for key, value in os.environ.items():
            if key.startswith("FUBON") or key in ["ENABLE_MOCK", "APP_ENV"]:
                logger.info(f"  {key}={value}")
        
        # 添加搜索路徑
        sdk_paths = [
            "/opt/python",
            "/opt/python/site-packages",
            "/opt/python/lib/python3.11/site-packages",
            "/var/task",
            "/tmp/fubon_sdk"
        ]
        
        for path in sdk_paths:
            if path not in sys.path and os.path.exists(path):
                sys.path.insert(0, path)
                logger.info(f"添加路徑: {path}")
        
        logger.info(f"Python 搜索路徑: {sys.path}")
        
        # 列出所有 wheel 文件
        wheel_files = []
        for path in sdk_paths:
            if os.path.exists(path):
                wheels = glob.glob(f"{path}/*.whl")
                wheel_files.extend(wheels)
                
        if wheel_files:
            logger.info(f"找到 wheel 文件: {wheel_files}")
            
            # 安裝第一個 wheel 文件
            wheel_path = wheel_files[0]
            tmp_dir = "/tmp/fubon_sdk"
            os.makedirs(tmp_dir, exist_ok=True)
            
            logger.info(f"嘗試安裝 wheel: {wheel_path} 到 {tmp_dir}")
            
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", wheel_path, "--target", tmp_dir, "--no-cache-dir"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info("安裝成功")
                sys.path.insert(0, tmp_dir)
                return True
            else:
                logger.error(f"安裝失敗: {result.stderr}")
                return False
        else:
            logger.warning("未找到 wheel 文件")
            
            # 嘗試直接導入
            try:
                import fubon_neo
                logger.info("成功導入 fubon_neo 模組")
                logger.info(f"fubon_neo 位置: {fubon_neo.__file__}")
                return True
            except ImportError as e:
                logger.error(f"導入 fubon_neo 失敗: {e}")
                
                # 列出尋找到的模組
                try:
                    for path in sdk_paths:
                        if os.path.exists(path):
                            modules = glob.glob(f"{path}/*")
                            logger.info(f"路徑 {path} 中的模組: {modules}")
                except Exception as e:
                    logger.error(f"列出模組時出錯: {e}")
                    
                return False
    except Exception as e:
        logger.error(f"設置 SDK 時出錯: {str(e)}")
        logger.error(traceback.format_exc())
        return False

# 自動執行設置
try:
    logger.info("開始設置 SDK...")
    success = setup_sdk()
    logger.info(f"SDK 設置{'成功' if success else '失敗'}")
except Exception as e:
    logger.error(f"安裝腳本執行錯誤: {str(e)}")
    logger.error(traceback.format_exc())
