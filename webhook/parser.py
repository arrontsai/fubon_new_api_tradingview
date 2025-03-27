"""
TradingView信號解析模組

負責解析從TradingView接收的webhook信號
"""
import re
import logging
from typing import Dict, Optional

from config import settings

logger = logging.getLogger(__name__)

def parse_tradingview_signal(signal: str) -> Optional[Dict]:
    """
    解析來自TradingView的交易信號
    
    信號格式例如：
    SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單買入 @ 1已成交小台指。新策略倉位是1
    
    返回解析後的交易信息字典，包含：
    - symbol: 交易商品代碼
    - action: 買入/賣出操作
    - quantity: 合約數量
    - position_size: 交易後的倉位大小
    """
    try:
        # 檢查信號是否包含必要的部分
        if "訂單" not in signal or "@" not in signal or "已成交" not in signal:
            logger.warning(f"信號格式不符合預期: {signal}")
            return None
        
        # 使用正則表達式解析信號
        order_pattern = r"訂單(\w+)\s*@\s*(\d+)已成交(\w+)。新策略倉位是(-?\d+)"
        match = re.search(order_pattern, signal)
        
        if not match:
            logger.warning(f"無法匹配交易信號模式: {signal}")
            return None
        
        action, quantity, ticker, position_size = match.groups()
        
        # 轉換操作類型
        if action == "買入":
            action_code = "Buy"
        elif action == "賣出":
            action_code = "Sell"
        else:
            logger.warning(f"未知的操作類型: {action}")
            return None
        
        # 將TradingView的商品名稱映射到富邦API的商品代碼
        if ticker in settings.SYMBOL_MAPPING:
            symbol = settings.SYMBOL_MAPPING[ticker]
        else:
            logger.warning(f"未知的交易商品: {ticker}")
            return None
        
        # 解析交易數量
        try:
            quantity = int(quantity)
            position_size = int(position_size)
        except ValueError:
            logger.warning(f"無法解析交易數量: {quantity} 或倉位大小: {position_size}")
            return None
        
        # 返回解析後的交易信息
        return {
            "symbol": symbol,
            "action": action_code,
            "quantity": quantity,
            "position_size": position_size,
            "original_ticker": ticker
        }
        
    except Exception as e:
        logger.error(f"解析交易信號時發生錯誤: {e}", exc_info=True)
        return None
