# 任務清單（task.md）

## MVP階段
1. 移除 FastAPI、Mangum 等不必要依賴，精簡 requirements.txt
2. 完成 Lambda handler 主架構（handler、webhook_handler、health_check_handler、setup_sdk）
3. 完成 TradingView webhook 訊號解析模組
4. 完成富邦 API 整合模組（登入、下單、回報）
5. 撰寫本地測試腳本，驗證端對端流程
6. 設計與撰寫日誌與錯誤處理機制
7. 撰寫 Lambda 部署腳本與說明文件
8. 建立 Lambda Layer，整合富邦 SDK
9. 部署 Lambda 至 AWS，串接 API Gateway，測試 webhook 流程
10. 設定 CloudWatch 監控與警報
11. 撰寫健康檢查端點

## 進階/優化
12. 將憑證與敏感資訊移至 Secrets Manager
13. 強化 API Gateway 安全性與流量控管
14. 增加交易結果通知（如 email、SNS）
15. 增加商品支援與參數彈性
16. 增加風險控管機制
17. 撰寫前端監控頁面（如有需求）
