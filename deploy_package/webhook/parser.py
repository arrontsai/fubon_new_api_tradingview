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
    
    實際信號格式例如：
    快訊： SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單buy @ 1已成交MXF1!。新策略倉位是-1
    
    返回解析後的交易信息字典，包含：
    - symbol: 交易商品代碼
    - action: 買入/賣出操作
    - quantity: 合約數量
    - position_size: 交易後的倉位大小
    """
    try:
        logger.info(f"嘗試解析信號: {signal}")
        
        # 支持實際TradingView發送的訊息格式
        # 標準格式: 訂單buy @ 1已成交MXF1!。新策略倉位是-1
        
        # 先嘗試最可能的格式 (包含感嘆號和負倉位)
        order_pattern = r"訂單(\w+)\s*@\s*(\d+)已成交([\w\d!]+).*?新策略倉位是(-?\d+)"
        match = re.search(order_pattern, signal)
        
        # 如果沒有匹配，嘗試更寬鬆的格式
        if not match:
            logger.warning(f"標準模式未匹配，嘗試備用模式...")
            # 寬鬆格式，不依賴於"訂單"前綴
            simplified_pattern = r"(\w+)\s*@\s*(\d+)已成交([\w\d!]+).*?新策略倉位是(-?\d+)"
            match = re.search(simplified_pattern, signal)
            
            # 最後嘗試極度寬鬆的格式
            if not match:
                logger.warning(f"備用模式未匹配，嘗試極寬鬆模式...")
                flexible_pattern = r"(\w+)\s*@\s*(\d+).*?([\w\d!]+).*?(-?\d+)"
                match = re.search(flexible_pattern, signal)
        
        if not match:
            logger.warning(f"無法匹配交易信號模式: {signal}")
            return None
        
        action, quantity, ticker, position_size = match.groups()
        logger.info(f"匹配結果 - 操作: {action}, 數量: {quantity}, 商品: {ticker}, 倉位: {position_size}")
        
        # 轉換操作類型 (支持英文操作代碼)
        action = action.lower()  # 轉小寫以便匹配
        action_code = None
        
        if action in ["買入", "buy", "long"]:
            action_code = "Buy"
        elif action in ["賣出", "sell", "short"]:
            action_code = "Sell"
        else:
            logger.warning(f"未知的操作類型: {action}")
            return None
        
        # 處理商品代碼 (移除感嘆號等特殊符號)
        cleaned_ticker = re.sub(r'[^\w\d]', '', ticker)  # 移除非字母數字字符
        logger.info(f"清理後的商品代碼: {cleaned_ticker}")
        
        # 默認映射表
        default_mapping = {
            "MXF": "MXF",  # 小台指期貨
            "TXF": "TXF",  # 台指期貨
            "ZME": "ZME",  # 小道瓊期貨
            "ZNQ": "ZNQ",  # 小納斯達克期貨
            "ZES": "ZES"   # 小標普期貨
        }
        
        # 取得商品映射表 (如果設定中沒有，使用默認)
        symbol_mapping = getattr(settings, "SYMBOL_MAPPING", default_mapping)
        
        # 商品代碼映射 (處理包含月份數字的情況，如MXF1)
        base_symbol = re.sub(r'\d+$', '', cleaned_ticker)  # 移除尾部數字
        
        if cleaned_ticker in symbol_mapping:
            # 完全匹配
            symbol = symbol_mapping[cleaned_ticker]
        elif base_symbol in symbol_mapping:
            # 基本代碼匹配 (如MXF1 -> MXF)
            symbol = symbol_mapping[base_symbol]
            logger.info(f"基本代碼匹配: {cleaned_ticker} -> {base_symbol} -> {symbol}")
        else:
            # 使用原始代碼
            symbol = cleaned_ticker
            logger.info(f"無匹配，使用原始代碼: {symbol}")
        
        # 解析交易數量和倉位
        try:
            quantity = int(quantity)
            position_size = int(position_size)  # 支持負數倉位
        except ValueError:
            logger.warning(f"無法解析交易數量: {quantity} 或倉位大小: {position_size}")
            return None
        
        # 返回解析後的交易信息
        result = {
            "symbol": symbol,
            "action": action_code,
            "quantity": quantity,
            "position_size": position_size,
            "original_ticker": ticker
        }
        logger.info(f"成功解析信號: {result}")
        return result
        
    except Exception as e:
        logger.error(f"解析交易信號時發生錯誤: {e}", exc_info=True)
        return None
