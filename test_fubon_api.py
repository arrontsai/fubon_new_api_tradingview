"""
富邦API功能測試腳本

該腳本用於測試富邦API的各項功能，包括：
1. 登入功能
2. 帳戶資訊查詢
3. 下單交易功能
4. 訂單狀態查詢

注意：此腳本會使用模擬模式或實際富邦API進行測試，取決於環境設定。
"""
import os
import sys
import time
import logging
from dotenv import load_dotenv

from fubon_api.client import FubonClient
from config import settings

# 設置基本日誌格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_login(client):
    """測試登入功能"""
    logger.info("=== 測試登入功能 ===")
    try:
        login_success = client.login()
        if login_success:
            logger.info("✓ 登入成功")
            return True
        else:
            logger.error("✗ 登入失敗")
            return False
    except Exception as e:
        logger.error(f"✗ 登入時發生錯誤: {e}")
        return False

def test_get_account_info(client):
    """測試帳戶資訊查詢"""
    logger.info("=== 測試帳戶資訊查詢 ===")
    try:
        account_info = client.get_account_info()
        if account_info:
            logger.info(f"✓ 帳戶資訊查詢成功")
            logger.info(f"  帳號: {account_info.get('account_id', 'N/A')}")
            logger.info(f"  客戶名稱: {account_info.get('name', 'N/A')}")
            logger.info(f"  分公司代號: {account_info.get('branch_no', 'N/A')}")
            
            # 顯示帳戶摘要資訊
            summary = account_info.get('summary', {})
            logger.info(f"  初始保證金總額: {summary.get('total_initial_margin', 'N/A')}")
            logger.info(f"  維持保證金總額: {summary.get('total_maintenance_margin', 'N/A')}")
            logger.info(f"  總損益: {summary.get('total_profit_loss', 'N/A')}")
            logger.info(f"  總權利金: {summary.get('total_premium', 'N/A')}")
            logger.info(f"  部位數量: {summary.get('position_count', 0)}")
            
            # 顯示部位信息（如果有）
            positions = account_info.get('positions', [])
            if positions:
                logger.info(f"  部位資訊 ({len(positions)} 個):")
                for i, pos in enumerate(positions, 1):
                    logger.info(f"  #{i}: {pos.get('symbol', 'N/A')} "
                                f"{pos.get('buy_sell', 'N/A')} "
                                f"{pos.get('tradable_lot', 0)}張 "
                                f"成交價: {pos.get('price', 0)} "
                                f"市價: {pos.get('market_price', 'N/A')} "
                                f"損益: {pos.get('profit_or_loss', 0)}")
            
            return account_info
        else:
            logger.error("✗ 帳戶資訊查詢失敗")
            return None
    except Exception as e:
        logger.error(f"✗ 帳戶資訊查詢時發生錯誤: {e}")
        return None

def test_place_order(client, symbol="MXF", action="Buy", quantity=1):
    """測試下單功能"""
    logger.info(f"=== 測試下單功能 (商品: {symbol}, 動作: {action}, 數量: {quantity}) ===")
    try:
        order_result = client.place_order(symbol, action, quantity)
        
        # 檢查下單是否成功
        if order_result and order_result.get("status") != "Failed":
            logger.info(f"✓ 下單成功")
            logger.info(f"  訂單ID: {order_result.get('order_id', 'N/A')}")
            logger.info(f"  狀態: {order_result.get('status', 'N/A')}")
            logger.info(f"  成交價格: {order_result.get('price', 'N/A')}")
            logger.info(f"  成交時間: {order_result.get('order_time', 'N/A')}")
            return order_result.get("order_id")
        else:
            logger.error(f"✗ 下單失敗: {order_result.get('error_message', '未知錯誤')}")
            return None
    except Exception as e:
        logger.error(f"✗ 下單時發生錯誤: {e}")
        return None

def test_order_status(client, order_id):
    """測試訂單狀態查詢"""
    logger.info(f"=== 測試訂單狀態查詢 (訂單ID: {order_id}) ===")
    try:
        if not order_id:
            logger.error("✗ 無法查詢訂單狀態: 無效的訂單ID")
            return False
            
        order_status = client.get_order_status(order_id)
        if order_status:
            logger.info(f"✓ 訂單狀態查詢成功")
            logger.info(f"  訂單ID: {order_status.get('order_id', 'N/A')}")
            logger.info(f"  狀態: {order_status.get('status', 'N/A')}")
            logger.info(f"  已成交數量: {order_status.get('filled_quantity', 'N/A')}")
            logger.info(f"  待成交數量: {order_status.get('remaining_quantity', 'N/A')}")
            logger.info(f"  成交價格: {order_status.get('filled_price', 'N/A')}")
            logger.info(f"  成交時間: {order_status.get('filled_time', 'N/A')}")
            return True
        else:
            logger.error("✗ 訂單狀態查詢失敗")
            return False
    except Exception as e:
        logger.error(f"✗ 查詢訂單狀態時發生錯誤: {e}")
        return False

def run_tests(env):
    """運行所有測試"""
    logger.info(f"使用環境: {env}")
    logger.info(f"模擬模式: {'開啟' if settings.ENABLE_MOCK else '關閉'}")
    
    # 初始化客戶端
    try:
        client = FubonClient(
            cert_path=settings.CERT_PATH,
            cert_password=settings.CERT_PASSWORD,
            personal_id=settings.PERSONAL_ID,
            password=settings.PASSWORD
        )
        
        # 測試登入 (客戶端初始化時已經登入)
        if test_login(client):
            # 測試帳戶資訊查詢
            test_get_account_info(client)  # 使用已存儲的帳戶資訊
            
            # 測試下單
            order_id = test_place_order(client)
            
            if order_id:
                # 測試查詢訂單狀態
                test_order_status(client, order_id)
        else:
            logger.error("登入測試失敗，中止後續測試")
    except Exception as e:
        logger.error(f"初始化客戶端時發生錯誤: {e}", exc_info=True)

if __name__ == "__main__":
    # 獲取環境設定
    env = "development"
    if len(sys.argv) > 1 and sys.argv[1] in ["development", "test", "production"]:
        env = sys.argv[1]
    
    # 運行測試
    run_tests(env)
