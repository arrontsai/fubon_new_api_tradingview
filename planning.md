# 專案規格書（planning.md）

## 一、專案目標
本專案旨在建立一個自動化交易系統，能夠將 TradingView 的 webhook 訊號，透過 AWS Lambda 與 API Gateway，轉換並執行於富邦期貨 API，達到自動下單與回報監控。

## 二、架構設計
- **Webhook 接收服務**：API Gateway + Lambda，接收 TradingView POST 訊號。
- **訊號解析模組**：將訊號格式解析為富邦 API 可用參數。
- **富邦 API 整合**：Lambda 直接呼叫富邦期貨 API（需 SDK 層）。
- **日誌與監控**：CloudWatch 日誌與警報，錯誤通知與健康檢查。

## 三、技術選型
- Python 3.9（Lambda 支援版本）
- AWS Lambda + API Gateway
- 富邦 NEO SDK（以 Lambda Layer 方式整合）
- boto3、requests、python-dotenv 等基礎套件

## 四、環境規劃
- **開發/測試**：本地 Windows
- **生產**：AWS Lambda（需確認 SDK 與憑證兼容性）

## 五、功能範圍
1. TradingView webhook 解析與驗證
2. 富邦 API 下單、查詢、登入
3. 交易紀錄與日誌
4. 錯誤處理與通知
5. AWS 雲端部署與監控
6. 基本健康檢查端點

## 六、安全與合規
- 所有 API 經 HTTPS 傳輸
- 憑證與敏感資訊存放於 AWS Secrets Manager
- Lambda 執行環境變數管理
- API Gateway 強制 TLS 1.2 以上

## 七、未來擴充
- 支援更多商品
- 風險控管與額度限制
- 加入簡易前端監控頁面
