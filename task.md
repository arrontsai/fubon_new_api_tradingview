# 任務清單（task.md）

## MVP階段
1. 移除 FastAPI、Mangum 等不必要依賴，精簡 requirements.txt
2. 完成 Lambda handler 主架構（handler、webhook_handler、health_check_handler、setup_sdk）
3. 完成 TradingView webhook 訊號解析模組
4. 完成富邦 API 整合模組（登入、下單、回報）
5. 撰寫本地測試腳本，驗證端對端流程
6. 設計與撰寫日誌與錯誤處理機制
7. 完成 LINE 推播功能，即時通知交易訊息
8. 撰寫 Lambda 部署腳本與說明文件
9. 建立 Lambda Layer，整合富邦 SDK
10. 部署 Lambda 至 AWS，串接 API Gateway，測試 webhook 流程
11. 設定 CloudWatch 監控與警報
12. 撰寫健康檢查端點

## 進階/優化
13. 將憑證與敏感資訊移至 Secrets Manager
14. 強化 API Gateway 安全性與流量控管
15. 擴展 LINE 推播功能，優化訊息格式與內容
16. 增加更多通知管道（如 email、Telegram）
17. 增加商品支援與參數彈性
18. 增加風險控管機制
19. 撰寫前端監控頁面（如有需求）
