# 富邦期貨交易API與TradingView Webhook整合系統

## 專案概述

這個系統旨在接收TradingView的交易信號webhook，然後利用富邦證券的交易API自動執行特定期貨商品的交易，包括小台指、台積電期貨和那斯達克100期貨。

## 系統架構

### 主要元件

1. **Webhook接收服務**：
   - 接收來自TradingView的POST請求
   - 解析特定格式的交易信號
   - 驗證請求的有效性

2. **交易處理服務**：
   - 解析TradingView信號中的商品和操作
   - 轉換為富邦API可接受的交易參數
   - 呼叫富邦API執行交易

3. **富邦API整合模組**：
   - 管理與富邦API的連接
   - 處理登入與身份驗證
   - 執行特定期貨商品(小台指、台積電期、那斯達克100)的交易

4. **日誌與監控模組**：
   - 記錄交易操作與結果
   - 基本錯誤處理與通知
   - LINE 即時推播交易訊號與結果

## 功能需求

### 核心功能

1. **接收TradingView的webhook**：
   - 實作一個HTTP伺服器接收POST請求
   - 解析特定格式的交易信號，例如：
     ```
     SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單{{strategy.order.action}} @ {{strategy.order.contracts}}已成交{{ticker}}。新策略倉位是{{strategy.position_size}}
     ```

2. **富邦API連線與交易**：
   - 使用憑證進行API登入
   - 支援特定期貨商品的交易（小台指、台積電期、那斯達克100）
   - 執行買賣操作並處理交易回報

### 執行環境

1. **初期**：本地運行測試和開發
2. **後期**：部署到AWS雲端環境，確保穩定性和可靠性

## 技術規格

### 技術選擇

1. **Web框架**：
   - 不使用框架

2. **富邦API整合**：
   - 富邦NEO SDK (fubon_neo)

3. **雲端部署**：
   - AWS EC2或Lambda（視最終應用需求而定）
   - 考慮使用Docker容器化應用

### 系統需求

1. **Python 3.7+**
2. **初期**：Windows作業系統（基於富邦API支援的平台）
3. **後期**：AWS雲端環境（需確認富邦API在Linux環境的兼容性）

## 實作計劃

### 第一階段：最小可行產品(MVP)

1. **建立基本webhook接收服務**
   - 不使用框架
   - 解析TradingView特定格式的信號
   - 從訊息中提取關鍵交易資訊（動作、合約數量、商品）

2. **實現富邦API基本整合**
   - 設置API連線與登入
   - 實作特定期貨商品的下單功能
   - 基本訂單狀態查詢

3. **測試與驗證**
   - 在本地環境進行端對端測試
   - 模擬TradingView信號並驗證交易流程

### 第二階段：功能完善與雲端部署

1. **增強交易功能**
   - 完善錯誤處理機制
   - 透過 LINE 實時通知交易結果
   - 完整的請求與回應記錄

2. **準備雲端部署**
   - 確認富邦API在雲端環境的兼容性
   - 準備Docker容器和部署腳本

3. **部署至AWS**
   - 設置EC2實例或Lambda函數
   - 配置網路安全設置
   - 實施監控和日誌記錄

## 系統流程

1. **接收交易信號**：
   - TradingView根據策略發送webhook至系統端點
   - 系統解析訊息格式，提取交易資訊

2. **處理交易請求**：
   - 識別交易商品（小台指、台積電期、那斯達克100）
   - 確定交易動作（買入/賣出）和數量

3. **執行富邦API交易**：
   - 連線並登入富邦API
   - 提交交易請求
   - 處理交易回報

4. **記錄與通知**：
   - 記錄交易結果
   - 透過 LINE 即時推播通知
   - 完整追蹤請求與處理結果

## 數據格式與處理

### TradingView Webhook格式

基於提供的範例，系統需要解析如下格式：
```
策略名稱和參數：訂單{{strategy.order.action}} @ {{strategy.order.contracts}}已成交{{ticker}}。新策略倉位是{{strategy.position_size}}
SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單buy @ 1已成交MXF1!。新策略倉位是-1
```

其中關鍵資訊包括：
- `strategy.order.action`：買入或賣出操作
- `strategy.order.contracts`：合約數量
- `ticker`：交易商品
- `strategy.position_size`：交易後的部位大小

### 富邦API交易參數

需要將TradingView信號轉換為富邦API可接受的格式，包括：
- 商品代碼映射（例如：將TradingView的商品標識符轉換為富邦API的商品代碼）
- 交易方向轉換
- 數量轉換

## 限制和考量

1. **交易量考量**：
   - 系統設計針對低流量應用（平均每天10筆，最多不超過100筆）
   - 無需過度優化性能，但需確保穩定性

2. **雲端部署考量**：
   - 需確認富邦API在AWS環境的兼容性
   - 考慮AWS費用和資源分配

## 未來擴展計劃

1. **風險控制功能**：
   - 交易限額設置
   - 風險評估和預警機制

2. **更多交易商品支援**：
   - 擴展支援其他期貨商品

3. **使用者介面**：
   - 可能增加簡單的網頁界面進行監控和設置

4. **增強通知功能**：
   - 添加更多通知管道（如 Email、Telegram）
   - 自訂通知內容與觸發條件

4. **測試指令**：
   下單: curl.exe -X POST "https://ui4xcxhmpb.execute-api.ap-northeast-1.amazonaws.com/webhook/tradingview" -H "Content-Type: application/json" -d "{\"message\":\"SuperTrend + QQE 策略 - 波動過濾版 + Zero Lag Trend 過濾 (加倉條件) (15, 20, 1.3, 8, 8, 3, 15, EMA, close, 20, hl2, 4, 50, 1.5, 7)：訂單buy @ 1已成交MXF1!。新策略倉位是-1\"}"
   檢查狀態: curl -x GET "https://ui4xcxhmpb.execute-api.ap-northeast-1.amazonaws.com/health"
   
   