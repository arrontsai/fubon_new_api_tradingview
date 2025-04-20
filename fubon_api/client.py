"""
富邦API客戶端模組

負責與富邦期貨交易API進行交互，執行登入、下單等操作
"""
import os
import time
import json
import logging
import datetime
import base64
import tempfile
from datetime import date, timedelta
from typing import Dict, List, Any, Union, Optional

import boto3
from config import settings

# 導入富邦SDK
try:
    # 首先嘗試直接導入SDK（由Layer提供）
    from fubon_neo import _fubon_neo
    logging.getLogger(__name__).info("成功直接導入富邦SDK")
except ImportError:
    # 嘗試使用層中的安裝腳本
    try:
        # 檢查是否在Lambda環境中運行
        if os.environ.get('AWS_LAMBDA_FUNCTION_NAME'):
            # 嘗試從site-packages導入安裝腳本
            logging.getLogger(__name__).info("嘗試從Lambda Layer導入SDK安裝腳本")
            try:
                import fubon_sdk_setup
                logging.getLogger(__name__).info("成功導入SDK安裝腳本")
                
                # 再次嘗試導入
                try:
                    from fubon_neo import _fubon_neo
                    logging.getLogger(__name__).info("通過安裝腳本成功導入富邦SDK")
                except ImportError:
                    logging.getLogger(__name__).error("安裝後仍無法導入富邦SDK，切換到模擬模式")
                    _fubon_neo = None
            except ImportError:
                logging.getLogger(__name__).error("未找到SDK安裝腳本，切換到模擬模式")
                _fubon_neo = None
        else:
            # 非Lambda環境
            logging.getLogger(__name__).warning("無法導入富邦SDK: ImportError，切換到模擬模式")
            _fubon_neo = None
    except Exception as e:
        logging.getLogger(__name__).error(f"導入SDK時發生未知錯誤: {str(e)}，切換到模擬模式")
        _fubon_neo = None

# 確認SDK版本
if hasattr(_fubon_neo, 'version'):
    logging.info(f"富邦SDK版本: {_fubon_neo.version}")

# 嘗試導入SDK
FUBON_SDK_AVAILABLE = _fubon_neo is not None
logging.info("富邦SDK已成功導入" if FUBON_SDK_AVAILABLE else "無法導入富邦SDK，使用模擬模式")

class FubonClient:
    """富邦期貨交易API客戶端"""
    
    def __init__(self, cert_path: str = None, cert_password: str = None, personal_id: str = "", password: str = ""):
        """
        初始化富邦API客戶端
        
        參數:
            cert_path: 憑證路徑、Secrets Manager密鑰路徑（使用 secrets: 前綴）或Parameter Store參數名稱
            cert_password: 憑證密碼
            personal_id: 個人ID（登入用）
            password: 登入密碼
        """
        # 只從 settings 取得，確保所有敏感資訊皆由 config.py 控制
        self.cert_path = settings.CERT_PATH
        self.cert_password = settings.CERT_PASSWORD
        self.personal_id = settings.PERSONAL_ID
        self.password = settings.PASSWORD
        self.logger = logging.getLogger(__name__)
        
        # 檢查是否強制使用模擬模式
        self.use_mock = os.environ.get("ENABLE_MOCK", "false").lower() in ['true', '1', 'yes', 'y']
        
        # AWS區域
        self.aws_region = os.environ.get("AWS_REGION", "ap-northeast-1")
        
        # 連線狀態
        self.connected = False
        
        # 富邦API實例 (根據文檔中的示例和實際模組結構初始化)
        self.sdk = None
        
        # 臨時憑證檔案路徑（從Parameter Store加載時使用）
        self.temp_cert_path = None
        
        # 初始化API連線
        self._initialize_connection()
    
    def _get_cert_from_secrets_manager(self, secret_name):
        """從AWS Secrets Manager獲取憑證並保存為臨時文件"""
        try:
            # 移除前綴標記符
            if isinstance(secret_name, str) and secret_name.startswith('secrets:'):
                secret_name = secret_name[8:]
                
            self.logger.info(f"從Secrets Manager獲取憑證: {secret_name}")
            
            # 創建Secrets Manager客戶端
            secrets_client = boto3.client('secretsmanager', region_name=self.aws_region)
            
            # 獲取密鑰
            response = secrets_client.get_secret_value(
                SecretId=secret_name
            )
            
            # 獲取密鑰內容
            if 'SecretString' in response:
                # 如果是JSON字符串
                try:
                    secret_data = json.loads(response['SecretString'])
                    cert_base64 = secret_data.get('pfx')
                except json.JSONDecodeError:
                    # 如果不是JSON格式，直接使用字符串
                    cert_base64 = response['SecretString']
            elif 'SecretBinary' in response:
                # 如果是二進制數據
                cert_base64 = base64.b64encode(response['SecretBinary']).decode('utf-8')
            else:
                raise Exception("密鑰格式不正確")
            
            # 解碼Base64
            cert_bytes = base64.b64decode(cert_base64)
            
            # 創建臨時文件
            fd, temp_path = tempfile.mkstemp(suffix='.pfx')
            with os.fdopen(fd, 'wb') as temp_file:
                temp_file.write(cert_bytes)
            
            self.logger.info(f"憑證已保存到臨時文件: {temp_path}")
            self.temp_cert_path = temp_path
            return temp_path
            
        except Exception as e:
            self.logger.error(f"從Secrets Manager獲取憑證時發生錯誤: {e}")
            return None
    
    def _get_cert_from_parameter_store(self, param_name):
        """從AWS Parameter Store獲取憑證並保存為臨時文件"""
        try:
            # 檢查是否是Parameter Store參數路徑格式
            if not (isinstance(param_name, str) and param_name.startswith('/')):
                return None
                
            self.logger.info(f"從Parameter Store獲取憑證: {param_name}")
            
            # 創建SSM客戶端
            ssm = boto3.client('ssm', region_name=self.aws_region)
            
            # 獲取參數
            response = ssm.get_parameter(
                Name=param_name,
                WithDecryption=True  # 自動解密SecureString類型的參數
            )
            
            # 獲取Base64編碼的憑證內容
            cert_base64 = response['Parameter']['Value']
            
            # 解碼Base64
            cert_bytes = base64.b64decode(cert_base64)
            
            # 創建臨時文件
            fd, temp_path = tempfile.mkstemp(suffix='.pfx')
            with os.fdopen(fd, 'wb') as temp_file:
                temp_file.write(cert_bytes)
            
            self.logger.info(f"憑證已保存到臨時文件: {temp_path}")
            self.temp_cert_path = temp_path
            return temp_path
            
        except Exception as e:
            self.logger.error(f"從Parameter Store獲取憑證時發生錯誤: {e}")
            return None
    
    def _initialize_connection(self):
        """初始化與富邦API的連線"""
        try:
            # 檢查是否強制使用模擬模式
            self.use_mock = os.environ.get("ENABLE_MOCK", "false").lower() in ['true', '1', 'yes', 'y']
            
            # 如果在生產環境，禁止使用模擬模式
            if os.environ.get("APP_ENV", "").lower() == "production":
                self.use_mock = False
                self.logger.info("在生產環境中，強制停用模擬模式")
                
            # 記錄模擬狀態
            if self.use_mock:
                self.logger.warning("⚠️ 當前使用模擬模式，不會執行實際交易")
            else:
                self.logger.info("使用真實交易模式")
                
            # 如果不使用模擬模式，嘗試初始化SDK
            if not self.use_mock and _fubon_neo is not None:
                try:
                    # 初始化SDK並連接
                    self.sdk = _fubon_neo
                    self.logger.info("成功初始化富邦SDK")
                    
                    # 實際連線富邦API
                    self.logger.info("正在連線富邦API...")
                    
                    try:
                        # 憑證路徑已由 config.py 處理，直接使用
                        cert_path = self.cert_path
                        self.sdk = _fubon_neo.CoreSDK()
                        login_result = self.sdk.login(
                            self.personal_id, 
                            self.password,
                            cert_path,
                            self.cert_password)
                        
                        if login_result.is_success:
                            self.connected = True
                            # 取得帳戶資訊
                            account_data = login_result.data
                            # 帳戶資訊可能是列表，處理這種情況
                            if isinstance(account_data, list) and account_data:
                                # 使用第二個帳戶
                                self.account_list = account_data
                                account = account_data[1]
                                self.account_id = account.account if hasattr(account, 'account') else ""
                                self.logger.info(f"富邦API登入成功，找到 {len(account_data)} 個帳戶")
                                self.logger.info(f"使用第二個帳戶: {account.account if hasattr(account, 'account') else 'N/A'}")
                                self.logger.info(f"  客戶名稱: {account.name if hasattr(account, 'name') else 'N/A'}")
                                self.logger.info(f"  分公司代號: {account.branch_no if hasattr(account, 'branch_no') else 'N/A'}")
                                self.logger.info(f"  帳號類型: {account.account_type if hasattr(account, 'account_type') else 'N/A'}")
                            else:
                                # 單一帳戶
                                self.account_list = [account_data] if account_data else []
                                self.account_id = account_data.account if hasattr(account_data, 'account') else ""
                                self.logger.info(f"富邦API登入成功，帳戶: {account_data.account if hasattr(account_data, 'account') else 'N/A'}")
                        else:
                            self.logger.error(f"富邦API登入失敗: {login_result.message}")
                            self.connected = False
                            
                    except Exception as e:
                        self.logger.error(f"SDK初始化失敗: {e}")
                        self.connected = False
                        raise
                        
                except Exception as e:
                    self.logger.error(f"初始化連線時發生錯誤: {e}", exc_info=True)
                    self.connected = False
                    raise
            else:
                # 在開發環境或強制模擬模式下使用模擬模式
                self.logger.warning("使用模擬模式連線")
                self.connected = True
        except Exception as e:
            self.logger.error(f"連線富邦API時發生錯誤: {e}", exc_info=True)
            self.connected = False
            raise
        finally:
            # 如果使用了臨時文件，在連接建立後可以刪除
            if self.temp_cert_path and os.path.exists(self.temp_cert_path):
                try:
                    os.unlink(self.temp_cert_path)
                    self.logger.info(f"已刪除臨時憑證文件: {self.temp_cert_path}")
                    self.temp_cert_path = None
                except Exception as e:
                    self.logger.warning(f"無法刪除臨時憑證文件: {e}")
    
    def login(self) -> object:
        """
        登入富邦API
        
        返回:
            bool: 登入是否成功
        """
        try:
            if not self.connected:
                self._initialize_connection()

                
            if FUBON_SDK_AVAILABLE and not self.use_mock and self.sdk:
                # 已經在_initialize_connection方法中登入了
                self.logger.info("已經登入富邦API")
                return True
            else:
                # 模擬登入
                self.logger.info("模擬模式：登入成功")
                return True
        except Exception as e:
            self.logger.error(f"登入富邦API時發生錯誤: {e}", exc_info=True)
            return False
    
    def get_account_info(self) -> Dict[str, Any]:
        """
        獲取帳戶資訊，包含餘額、部位等
        
        返回:
            Dict: 帳戶資訊
        """
        try:
            if not self.connected:
                self._initialize_connection()
                
            self.logger.info("查詢帳戶資訊")
            
            if FUBON_SDK_AVAILABLE and not self.use_mock and self.sdk:
                # 實際查詢
                result = {
                    "account_id": self.account_id,
                    "name": "",
                    "branch_no": "",
                    "account_type": "",
                    "summary": {
                        "total_initial_margin": 0,
                        "total_maintenance_margin": 0,
                        "total_profit_loss": 0,
                        "total_premium": 0,
                        "position_count": 0
                    },
                    "positions": []
                }
                
                try:
                    # 確保有帳戶資料
                    if hasattr(self, 'account_list') and self.account_list:
                        # 使用第二個帳戶
                        account = self.account_list[1] if len(self.account_list) > 1 else self.account_list[0]
                        
                        # 使用 futopt_accounting.query_single_position 方法查詢部位
                        if hasattr(self.sdk, 'futopt_accounting') and hasattr(self.sdk.futopt_accounting, 'query_single_position'):
                            account_position_result = self.sdk.futopt_accounting.query_single_position(account)
                            
                            if hasattr(account_position_result, 'is_success') and account_position_result.is_success:
                                self.logger.info("帳戶部位查詢成功")
                                
                                # 填充基本帳戶資訊
                                result["account_id"] = account.account if hasattr(account, 'account') else self.account_id
                                result["name"] = account.name if hasattr(account, 'name') else ""
                                result["branch_no"] = account.branch_no if hasattr(account, 'branch_no') else ""
                                result["account_type"] = account.account_type if hasattr(account, 'account_type') else "futopt"
                                
                                # 計算總體資訊
                                total_initial_margin = 0
                                total_maintenance_margin = 0
                                total_profit_loss = 0
                                total_premium = 0
                                
                                positions = []
                                # 處理部位資料
                                if hasattr(account_position_result, 'data') and account_position_result.data:
                                    for position in account_position_result.data:
                                        # 計算總值
                                        total_initial_margin += position.initial_margin if hasattr(position, 'initial_margin') else 0
                                        total_maintenance_margin += position.maintenance_margin if hasattr(position, 'maintenance_margin') else 0
                                        total_profit_loss += position.profit_or_loss if hasattr(position, 'profit_or_loss') else 0
                                        total_premium += position.premium if hasattr(position, 'premium') else 0
                                        
                                        # 添加到部位列表
                                        positions.append({
                                            "date": position.date if hasattr(position, 'date') else "",
                                            "branch_no": position.branch_no if hasattr(position, 'branch_no') else "",
                                            "account": position.account if hasattr(position, 'account') else "",
                                            "order_no": position.order_no if hasattr(position, 'order_no') else "",
                                            "position_kind": position.position_kind if hasattr(position, 'position_kind') else 0,
                                            "symbol": position.symbol if hasattr(position, 'symbol') else "",
                                            "expiry_date": position.expiry_date if hasattr(position, 'expiry_date') else "",
                                            "strike_price": position.strike_price if hasattr(position, 'strike_price') else None,
                                            "call_put": str(position.call_put) if hasattr(position, 'call_put') else None,
                                            "buy_sell": str(position.buy_sell) if hasattr(position, 'buy_sell') else "",
                                            "price": position.price if hasattr(position, 'price') else 0,
                                            "orig_lots": position.orig_lots if hasattr(position, 'orig_lots') else 0,
                                            "tradable_lot": position.tradable_lot if hasattr(position, 'tradable_lot') else 0,
                                            "order_type": str(position.order_type) if hasattr(position, 'order_type') else "",
                                            "currency": position.currency if hasattr(position, 'currency') else "TWD",
                                            "market_price": position.market_price if hasattr(position, 'market_price') else "0",
                                            "initial_margin": position.initial_margin if hasattr(position, 'initial_margin') else 0,
                                            "maintenance_margin": position.maintenance_margin if hasattr(position, 'maintenance_margin') else 0,
                                            "clearing_margin": position.clearing_margin if hasattr(position, 'clearing_margin') else 0,
                                            "profit_or_loss": position.profit_or_loss if hasattr(position, 'profit_or_loss') else 0,
                                            "premium": position.premium if hasattr(position, 'premium') else 0
                                        })
                                    
                                # 更新總體統計資訊
                                result["summary"]["total_initial_margin"] = total_initial_margin
                                result["summary"]["total_maintenance_margin"] = total_maintenance_margin
                                result["summary"]["total_profit_loss"] = total_profit_loss
                                result["summary"]["total_premium"] = total_premium
                                result["summary"]["position_count"] = len(positions)
                                result["positions"] = positions
                            else:
                                error_message = account_position_result.message if hasattr(account_position_result, 'message') else "未知錯誤"
                                self.logger.error(f"帳戶部位查詢失敗: {error_message}")
                        else:
                            self.logger.warning("SDK不支持 futopt_accounting.query_single_position 方法")
                    else:
                        self.logger.error("未找到帳戶資訊")
                except Exception as e:
                    self.logger.error(f"帳戶資訊查詢失敗: {e}")
                
                return result
            else:
                # 模擬資料
                self.logger.warning("使用模擬帳戶資訊")
                return {
                    "account_id": "DEMO123456",
                    "name": "測試使用者",
                    "branch_no": "15901",
                    "account_type": "futopt",
                    "summary": {
                        "total_initial_margin": 1000000,
                        "total_maintenance_margin": 800000,
                        "total_profit_loss": 50000,
                        "total_premium": 0,
                        "position_count": 2
                    },
                    "positions": [
                        {
                            "date": time.strftime("%Y/%m/%d"),
                            "branch_no": "15901",
                            "account": "DEMO123456",
                            "order_no": "SIM-0001",
                            "position_kind": 1,
                            "symbol": "MXFD5",
                            "expiry_date": int(time.strftime("%Y%m")),
                            "strike_price": None,
                            "call_put": None,
                            "buy_sell": "Buy",
                            "price": 18500,
                            "orig_lots": 1,
                            "tradable_lot": 1,
                            "order_type": "New",
                            "currency": "TWD",
                            "market_price": "18600.0000",
                            "initial_margin": 100000,
                            "maintenance_margin": 80000,
                            "clearing_margin": 78000,
                            "profit_or_loss": 5000,
                            "premium": 0
                        },
                        {
                            "date": time.strftime("%Y/%m/%d"),
                            "branch_no": "15901",
                            "account": "DEMO123456",
                            "order_no": "SIM-0002",
                            "position_kind": 1,
                            "symbol": "TXFD5",
                            "expiry_date": int(time.strftime("%Y%m")),
                            "strike_price": None,
                            "call_put": None,
                            "buy_sell": "Buy",
                            "price": 19200,
                            "orig_lots": 1,
                            "tradable_lot": 1,
                            "order_type": "New",
                            "currency": "TWD",
                            "market_price": "19500.0000",
                            "initial_margin": 170000,
                            "maintenance_margin": 140000,
                            "clearing_margin": 135000,
                            "profit_or_loss": 12000,
                            "premium": 0
                        }
                    ]
                }
        except Exception as e:
            self.logger.error(f"獲取帳戶資訊時發生錯誤: {e}", exc_info=True)
            raise
    
    def _get_front_month_code(self, symbol_base: str) -> str:
        """
        取得期貨近月合約代碼（如 TXF2405, MXF2405），優先使用 SDK 轉換
        """
        try:
            today = date.today()
            current_year = today.year
            current_month = today.month
            # 計算第三個週三（到期日）
            first_day = date(current_year, current_month, 1)
            weekday = first_day.weekday()
            days_until_first_wednesday = (2 - weekday) % 7
            first_wednesday = first_day.replace(day=1 + days_until_first_wednesday)
            third_wednesday = first_wednesday.replace(day=first_wednesday.day + 14)
            # 若今天超過到期日，則進入次月
            if today > third_wednesday:
                if current_month == 12:
                    target_year = current_year + 1
                    target_month = 1
                else:
                    target_year = current_year
                    target_month = current_month + 1
            else:
                target_year = current_year
                target_month = current_month

            # 優先嘗試 SDK 轉換
            if FUBON_SDK_AVAILABLE and hasattr(self.sdk, "futopt") and hasattr(self.sdk.futopt, "convert_symbol"):
                exchange_symbol = None
                if symbol_base.upper() == "TXF":
                    exchange_symbol = "FITX"
                elif symbol_base.upper() == "MXF":
                    exchange_symbol = "FIMTX"
                if exchange_symbol:
                    date_string = f"{target_year}{target_month:02d}"
                    complete_symbol = self.sdk.futopt.convert_symbol(exchange_symbol, date_string)
                    self.logger.info(f"近月合約代碼: {complete_symbol} (對應 {date_string})")
                    return complete_symbol
            # fallback: 組合合約代碼（取年份後兩碼）
            return f"{symbol_base}{str(target_year)[2:]}{target_month:02d}"
        except Exception as e:
            self.logger.error(f"近月合約代碼轉換失敗: {e}", exc_info=True)
            return ""


    def _get_next_month_code(self, symbol_base: str) -> str:
        """
        取得期貨次月合約代碼
        """
        today = date.today()
        current_year = today.year
        current_month = today.month
        # 計算第三個週三
        first_day = date(current_year, current_month, 1)
        weekday = first_day.weekday()
        days_until_first_wednesday = (2 - weekday) % 7
        first_wednesday = first_day.replace(day=1 + days_until_first_wednesday)
        third_wednesday = first_wednesday.replace(day=first_wednesday.day + 14)
        # 決定次月
        if current_month == 12:
            next_month = 1
            next_year = current_year + 1
        else:
            next_month = current_month + 1
            next_year = current_year
        # 產生合約代碼格式（如 MXF505）
        date_string = f"{next_year}{next_month:02d}"
        try:
            if hasattr(self.sdk, 'futopt') and hasattr(self.sdk.futopt, 'convert_symbol'):
                exchange_symbol = symbol_base
                if symbol_base.upper() == "TXF":
                    exchange_symbol = "FITX"
                elif symbol_base.upper() == "MXF":
                    exchange_symbol = "FIMTX"
                complete_symbol = self.sdk.futopt.convert_symbol(exchange_symbol, date_string)
                self.logger.info(f"次月合約代碼: {complete_symbol} (對應 {date_string})")
                return complete_symbol
            else:
                self.logger.warning("SDK不支持convert_symbol方法，使用通用格式")
                return f"{symbol_base}{str(next_year)[2:]}{next_month:02d}"
        except Exception as e:
            self.logger.error(f"合約代碼轉換失敗: {e}", exc_info=True)
            return f"{symbol_base}{str(next_year)[2:]}{next_month:02d}"

    def is_rollover_period(self, days_before_expiry: int = 1) -> bool:
        """
        判斷是否進入轉倉區間（預設到期日前1天）
        """
        today = date.today()
        current_year = today.year
        current_month = today.month
        first_day = date(current_year, current_month, 1)
        weekday = first_day.weekday()
        days_until_first_wednesday = (2 - weekday) % 7
        first_wednesday = first_day.replace(day=1 + days_until_first_wednesday)
        third_wednesday = first_wednesday.replace(day=first_wednesday.day + 14)
        rollover_start = third_wednesday - timedelta(days=days_before_expiry)
        return today >= rollover_start and today <= third_wednesday

    def get_target_symbol(self, symbol_base: str, rollover_days: int = 1) -> str:
        """
        根據是否進入轉倉區間，自動決定下單合約（近月或次月）
        支援 symbol_base 為 MXF、MXF1、MXF01、MXF1! 等格式
        """
        import re
        # 先判斷 symbol_base 是否已經帶有數字（如 MXF1、MXF01、MXF1!）
        match = re.match(r"^([A-Z]+)(1|01)(!?)$", symbol_base)
        if match:
            # 只取商品代碼，不帶月份
            symbol_base = match.group(1)
        # 進入自動轉倉判斷
        if self.is_rollover_period(days_before_expiry=rollover_days):
            self.logger.info(f"進入轉倉區間，下次月合約")
            symbol = self._get_next_month_code(symbol_base)
        else:
            symbol = self._get_front_month_code(symbol_base)
        # 若 symbol 為 None 或空值，回傳空字串
        if not symbol or not isinstance(symbol, str) or not symbol.strip():
            self.logger.error(f"[get_target_symbol] symbol_base: {symbol_base} 轉換後為 None 或空字串")
            return ""
        return symbol

        """
        取得期貨近月合約代碼
        
        臺灣期貨交易所的合約月份規則:
        - 每月的第三個週三為合約到期日
        - 近月合約為最近到期的合約
        
        參數:
            symbol_base: 基本商品代碼，例如 "MXF"
            
        返回:
            包含近月到期月份的完整商品代碼，符合富邦API格式
        """
        today = date.today()
        current_year = today.year
        current_month = today.month
        
        # 計算當月第三個週三的日期
        first_day = date(current_year, current_month, 1)
        # 找出第一個週三的日期
        weekday = first_day.weekday()
        days_until_first_wednesday = (2 - weekday) % 7
        first_wednesday = first_day.replace(day=1 + days_until_first_wednesday)
        # 第三個週三
        third_wednesday = first_wednesday.replace(day=first_wednesday.day + 14)
        
        # 如果今天已經過了當月第三個週三，則近月合約為下個月
        target_year = current_year
        if today > third_wednesday:
            if current_month == 12:
                next_month = 1
                target_year = current_year + 1
            else:
                next_month = current_month + 1
            target_month = next_month
        else:
            target_month = current_month
            
        # 使用富邦SDK提供的轉換函數
        # 構建YYYYMM格式的時間字串
        date_string = f"{target_year}{target_month:02d}"
        
        try:
            # 使用SDK的convert_symbol函數獲取正確的合約代碼
            # 例如: convert_symbol("FITX", "202404") 返回 "TXFD4"
            if hasattr(self.sdk, 'futopt') and hasattr(self.sdk.futopt, 'convert_symbol'):
                # 轉換商品代碼為對應的交易所代碼
                exchange_symbol = symbol_base
                if symbol_base.upper() == "TXF":
                    exchange_symbol = "FITX"  
                elif symbol_base.upper() == "MXF":
                    exchange_symbol = "FIMTX"  
                
                complete_symbol = self.sdk.futopt.convert_symbol(exchange_symbol, date_string)
                self.logger.info(f"近月合約代碼: {complete_symbol} (對應 {date_string})")
                return complete_symbol
            else:
                self.logger.warning("SDK不支持convert_symbol方法，使用通用格式")
                # 如果SDK沒有提供轉換函數，就使用通用格式
                # 例如: TXF2404 表示2024年4月的台指期
                return f"{symbol_base}{str(target_year)[-1]}{target_month:02d}"
        except Exception as e:
            self.logger.error(f"合約代碼轉換失敗: {e}", exc_info=True)
            # 使用通用格式作為後備
            return f"{symbol_base}{str(target_year)[-1]}{target_month:02d}"
    
    def place_order(self, symbol: str, action: str, quantity: int) -> Dict[str, Any]:
        """
        下單交易
        
        參數:
            symbol: 商品代碼，例如 "MXF"（小台指）
            action: 交易動作，"Buy" 或 "Sell"
            quantity: 交易數量
            
        返回:
            Dict: 訂單結果
        """
        try:
            # --- symbol 檢查與轉換 ---
            if not symbol or not isinstance(symbol, str) or not symbol.strip():
                self.logger.error(f"[下單失敗] symbol 參數異常，收到: {symbol!r}")
                raise ValueError("symbol 參數不能為空或非字串，請檢查呼叫端傳入值")
            symbol = symbol.strip().upper()
            self.logger.info(f"[下單請求] 原始商品代碼: {symbol}, 動作: {action}, 數量: {quantity}")

            # 自動轉換合約格式，支援 MXF1、MXF01、MXF1!、MXF 這些格式，並於轉倉區間自動下次月合約
            import re
            symbol_original = symbol
            match = re.match(r"^([A-Z]+)(1|01)(!?)$", symbol)
            rollover_days = getattr(self, 'rollover_days', 1)  # 預設1天，可由 class 參數調整
            if match:
                symbol_base = match.group(1)
                temp_symbol = self.get_target_symbol(symbol_base, rollover_days)
                if not temp_symbol or not isinstance(temp_symbol, str) or not temp_symbol.strip():
                    self.logger.error(f"[symbol自動轉換] '{symbol_original}' 轉換後為 None 或空字串，終止下單")
                    raise ValueError(f"symbol 自動轉換失敗，請檢查合約代碼來源: {symbol_original}")
                symbol = temp_symbol
                self.logger.info(f"[symbol自動轉換] '{symbol_original}' → '{symbol}'（自動轉倉邏輯）")
            elif len(symbol) <= 4:
                temp_symbol = self.get_target_symbol(symbol, rollover_days)
                if not temp_symbol or not isinstance(temp_symbol, str) or not temp_symbol.strip():
                    self.logger.error(f"[symbol自動轉換] '{symbol_original}' 轉換後為 None 或空字串，終止下單")
                    raise ValueError(f"symbol 自動轉換失敗，請檢查合約代碼來源: {symbol_original}")
                symbol = temp_symbol
                self.logger.info(f"[symbol自動轉換] '{symbol_original}' → '{symbol}'（自動轉倉邏輯）")
            # 其餘情況直接使用傳入的 symbol

            # 如果 symbol 已經包含到期月份 (如MXF04)，則保持不變
            if len(symbol) <= 3 and not any(c.isdigit() for c in symbol):
                if symbol.upper() in ["MXF", "TXF"]:
                    temp_symbol = self._get_front_month_code(symbol)
                    if not temp_symbol or not isinstance(temp_symbol, str) or not temp_symbol.strip():
                        self.logger.error(f"[symbol補全] '{symbol_original}' 補全近月合約後為 None 或空字串，終止下單")
                        raise ValueError(f"symbol 補全近月合約失敗，請檢查來源: {symbol_original}")
                    symbol = temp_symbol
                    self.logger.info(f"[symbol補全] '{symbol_original}' 自動補全近月合約 → '{symbol}'")

            # 最後再檢查一次 symbol
            if not symbol or not isinstance(symbol, str) or not symbol.strip():
                self.logger.error(f"[下單失敗] symbol 處理後仍為空或 None，終止下單。來源: {symbol_original}")
                raise ValueError("symbol 處理後仍為空或 None，請檢查自動轉換流程。")

            # 檢查是否使用模擬模式或SDK不可用
            if self.use_mock or not FUBON_SDK_AVAILABLE or not self.sdk:
                # 模擬下單
                self.logger.info(f"[模擬下單] 商品: {symbol}, 動作: {action}, 數量: {quantity}")
                order_id = f"SIM-{int(time.time())}"
                filled_price = 18000.0 if symbol == "MXF" else (700.0 if symbol == "TXF" else 700.0)
                self.logger.info(f"[模擬下單成功] 模擬價格: {filled_price}，訂單編號: {order_id}")
                return {
                    "order_id": order_id,
                    "symbol": symbol,
                    "action": action,
                    "quantity": quantity,
                    "status": "Filled",
                    "filled_price": filled_price,
                    "filled_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "mock": True,
                    "message": "這是模擬訂單，非實際交易"
                }
            
            # 實際下單 (SDK可用且非模擬模式)
            try:
                # 確保有帳戶資料
                if not hasattr(self, 'account_list') or not self.account_list:
                    self.logger.error(f"[下單失敗] 找不到 account_list，symbol: {symbol}, action: {action}")
                    return {
                        "order_id": "",
                        "symbol": symbol,
                        "action": action,
                        "quantity": quantity,
                        "status": "Failed",
                        "error_message": "未找到帳戶資料"
                    }

                # 使用第二個帳戶（如需調整可參數化）
                account = self.account_list[1]
                self.logger.info(f"[下單帳戶] 使用 account: {account}")

                # 轉換交易動作
                buy_sell_action = _fubon_neo.BSAction.Buy if action == "Buy" else _fubon_neo.BSAction.Sell

                # 判斷商品類型 (期貨或選擇權)
                is_option = 'TXO' in symbol.upper()
                market_type = _fubon_neo.FutOptMarketType.Option if is_option else _fubon_neo.FutOptMarketType.Future

                # 建立訂單物件 (參照API文檔範例)
                order = _fubon_neo.FutOptOrder(
                    buy_sell=buy_sell_action,
                    symbol=symbol,
                    lot=quantity,
                    market_type=market_type,
                    price_type=_fubon_neo.FutOptPriceType.Market,  # 市價單
                    time_in_force=_fubon_neo.TimeInForce.IOC,  # 立即成交否則取消
                    order_type=_fubon_neo.FutOptOrderType.Auto,
                    user_def="API_Order"  # 自訂欄位
                )
                self.logger.info(f"[下單送出] symbol: {symbol}, action: {action}, quantity: {quantity}, market_type: {market_type}")

                # 市價單不需要設定價格
                # 使用 futopt.place_order 方法下單
                if hasattr(self.sdk, 'futopt') and hasattr(self.sdk.futopt, 'place_order'):
                    self.logger.info("[SDK下單] 呼叫 futopt.place_order")
                    order_result = self.sdk.futopt.place_order(account, order)

                    # 檢查下單結果
                    if order_result.is_success:
                        self.logger.info(f"[下單成功] 訂單編號: {getattr(order_result.data, 'order_no', 'N/A')}，symbol: {symbol}")
                        return {
                            "order_id": getattr(order_result.data, 'order_no', ''),
                            "symbol": symbol,
                            "action": action,
                            "quantity": quantity,
                            "status": "Placed",
                            "price_type": str(getattr(order_result.data, 'price_type', '')),
                            "price": getattr(order_result.data, 'price', 0.0),
                            "time_in_force": str(getattr(order_result.data, 'time_in_force', '')),
                            "order_time": getattr(order_result.data, 'last_time', '')
                        }
                    else:
                        self.logger.error(f"[下單失敗] SDK回傳失敗，訊息: {getattr(order_result, 'message', '')}")
                        return {
                            "order_id": "",
                            "symbol": symbol,
                            "action": action,
                            "quantity": quantity,
                            "status": "Failed",
                            "error_message": getattr(order_result, 'message', '')
                        }
                else:
                    raise AttributeError("找不到 futopt.place_order 方法")
                    
            except AttributeError as e:
                self.logger.error(f"[下單失敗] futopt.place_order 方法不存在: {e}，自動切換至模擬模式！")
                self.use_mock = True
                mock_order_no = f"MOCK-{int(time.time())}"
                self.logger.info(f"[模擬下單] symbol: {symbol}, action: {action}, quantity: {quantity}, 訂單編號: {mock_order_no}")
                return {
                    "order_id": mock_order_no,
                    "symbol": symbol,
                    "action": action,
                    "quantity": quantity,
                    "status": "Placed (Mock)",
                    "price_type": "Market",
                    "price": 0,
                    "time_in_force": "IOC",
                    "order_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "mock": True,
                    "message": "這是模擬訂單，非實際交易"
                }
                
        except Exception as e:
            self.logger.error(f"[下單異常] 發生未預期錯誤: {e}", exc_info=True)
            return {
                "order_id": "",
                "symbol": symbol if 'symbol' in locals() else None,
                "action": action,
                "quantity": quantity,
                "status": "Error",
                "error_message": str(e)
            }
    
    def get_order_status(self, order_id: str) -> Dict[str, Any]:
        """
        查詢訂單狀態
        
        參數:
            order_id: 訂單ID
            
        返回:
            Dict: 訂單狀態資訊
        """
        try:
            if not self.connected:
                self._initialize_connection()
                
            self.logger.info(f"查詢訂單狀態 - 訂單ID: {order_id}")
            
            if FUBON_SDK_AVAILABLE and not self.use_mock and self.sdk:
                # 實際查詢
                try:
                    # 根據富邦API文檔，查詢方法可能為 query_order 或 query_orders
                    if hasattr(self.sdk, 'futopt') and hasattr(self.sdk.futopt, 'query_order'):
                        self.logger.info("使用 futopt.query_order 方法查詢")
                        order_result = self.sdk.futopt.query_order(order_id)
                        if order_result:
                            return self._format_order_result(order_result)
                        else:
                            self.logger.warning(f"未找到訂單: {order_id}")
                            return {"error": "未找到訂單", "order_id": order_id}
                    elif hasattr(self.sdk, 'futopt') and hasattr(self.sdk.futopt, 'query_orders'):
                        self.logger.info("使用 futopt.query_orders 方法查詢")
                        orders = self.sdk.futopt.query_orders()
                        if orders:
                            # 從所有訂單中查找特定ID的訂單
                            for order in orders:
                                if hasattr(order, 'order_id') and order.order_id == order_id:
                                    return self._format_order_result(order)
                        self.logger.warning(f"未找到訂單: {order_id}")
                        return {"error": "未找到訂單", "order_id": order_id}
                    elif hasattr(self.sdk, 'futopt') and hasattr(self.sdk.futopt, 'query_order_status'):
                        self.logger.info("使用 futopt.query_order_status 方法查詢")
                        order_result = self.sdk.futopt.query_order_status(order_id)
                        if order_result:
                            return self._format_order_result(order_result)
                        else:
                            self.logger.warning(f"未找到訂單: {order_id}")
                            return {"error": "未找到訂單", "order_id": order_id}
                    else:
                        self.logger.error(f"找不到適當的訂單查詢方法，使用模擬模式")
                        return self._mock_order_status(order_id)
                except Exception as e:
                    self.logger.error(f"查詢訂單狀態失敗: {e}")
                    return {"error": str(e), "order_id": order_id}
            else:
                # 模擬訂單狀態
                return self._mock_order_status(order_id)
        except Exception as e:
            self.logger.error(f"查詢訂單狀態時發生錯誤: {e}", exc_info=True)
            return {"error": str(e), "order_id": order_id}
            
    def _format_order_result(self, order) -> Dict[str, Any]:
        """格式化訂單結果為一致的字典格式"""
        try:
            result = {
                "order_id": getattr(order, 'order_id', 'N/A'),
                "status": getattr(order, 'status', 'Unknown'),
                "symbol": getattr(order, 'symbol', 'N/A'),
                "price": getattr(order, 'price', 0.0),
                "filled_price": getattr(order, 'filled_price', 0.0),
                "quantity": getattr(order, 'quantity', 0),
                "filled_quantity": getattr(order, 'filled_quantity', 0),
                "order_time": getattr(order, 'order_time', 'N/A'),
                "order_type": getattr(order, 'order_type', 'N/A'),
                "action": getattr(order, 'action', 'N/A'),
                "error_message": getattr(order, 'error_message', '')
            }
            return result
        except Exception as e:
            self.logger.error(f"格式化訂單結果時發生錯誤: {e}")
            return {"error": str(e)}
            
    def _mock_order_status(self, order_id: str) -> Dict[str, Any]:
        """提供模擬的訂單狀態"""
        self.logger.info(f"查詢訂單狀態 - 訂單ID: {order_id}")
        self.logger.warning("使用模擬訂單狀態")
        
        import random
        status_options = ["Placed", "Filled", "PartiallyFilled", "Canceled", "Rejected"]
        status = random.choice(status_options)
        
        return {
            "order_id": order_id,
            "status": status,
            "symbol": "MXFD5",  # 模擬近月小台指
            "price": 18500.0 if status in ["Filled", "PartiallyFilled"] else 0.0,
            "filled_price": 18500.0 if status in ["Filled", "PartiallyFilled"] else 0.0,
            "quantity": 1,
            "filled_quantity": 1 if status == "Filled" else (0.5 if status == "PartiallyFilled" else 0),
            "order_time": time.strftime("%H:%M:%S"),
            "order_type": "Market",
            "action": "Buy"
        }
    
    def close(self):
        """關閉連線"""
        try:
            if self.connected and FUBON_SDK_AVAILABLE and not self.use_mock and self.sdk:
                # 實際關閉連線
                self.logger.info("關閉富邦API連線")
                try:
                    # 登出
                    logout_result = self.sdk.logout()
                    
                    if logout_result.is_success:
                        self.logger.info("登出成功")
                    else:
                        self.logger.error(f"登出失敗: {logout_result.message}")
                        
                except Exception as e:
                    self.logger.error(f"登出失敗: {e}")
                finally:
                    self.connected = False
            else:
                self.logger.info("模擬模式：關閉連線")
                self.connected = False
        except Exception as e:
            self.logger.error(f"關閉連線時發生錯誤: {e}", exc_info=True)
            raise
