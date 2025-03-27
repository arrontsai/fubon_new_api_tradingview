"""
AWS 部署腳本

用於將富邦交易 API 應用程式部署到 AWS EC2 實例，並配置與 ACM 憑證的集成。
此腳本需要安裝 AWS CLI 並配置對應的權限。

使用方法:
    python deploy_to_aws.py [環境名稱]
"""
import os
import sys
import subprocess
import logging
import boto3
from pathlib import Path

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS 設定
AWS_REGION = "ap-northeast-1"  # 東京區域，您可以根據需要更改
EC2_INSTANCE_ID = ""  # 您的 EC2 實例 ID
ALB_NAME = ""  # 您的 Application Load Balancer 名稱
TARGET_GROUP_ARN = ""  # 您的目標群組 ARN
DOMAIN_NAME = ""  # 您的域名

def check_aws_cli():
    """檢查 AWS CLI 是否已安裝和配置"""
    try:
        result = subprocess.run(["aws", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("AWS CLI 已安裝")
            
            # 檢查配置
            result = subprocess.run(["aws", "sts", "get-caller-identity"], capture_output=True, text=True)
            if result.returncode == 0:
                logger.info("AWS CLI 已配置")
                return True
            else:
                logger.error("AWS CLI 未配置")
                logger.info("請運行 'aws configure' 配置您的 AWS 憑證")
                return False
        else:
            logger.error("AWS CLI 未安裝")
            logger.info("請安裝 AWS CLI: https://aws.amazon.com/cli/")
            return False
    except Exception as e:
        logger.error(f"檢查 AWS CLI 時發生錯誤: {e}")
        return False

def get_certificate_arn():
    """獲取 ACM 憑證 ARN"""
    try:
        acm = boto3.client('acm', region_name=AWS_REGION)
        certificates = acm.list_certificates(CertificateStatuses=['ISSUED'])
        
        if not certificates['CertificateSummaryList']:
            logger.error("找不到已發行的 ACM 憑證")
            return None
        
        # 如果有多個憑證，列出來讓用戶選擇
        if len(certificates['CertificateSummaryList']) > 1:
            logger.info("找到多個 ACM 憑證:")
            for i, cert in enumerate(certificates['CertificateSummaryList']):
                logger.info(f"{i+1}. {cert['DomainName']} - {cert['CertificateArn']}")
            
            choice = int(input("請選擇要使用的憑證 (輸入編號): ")) - 1
            if 0 <= choice < len(certificates['CertificateSummaryList']):
                return certificates['CertificateSummaryList'][choice]['CertificateArn']
            else:
                logger.error("無效的選擇")
                return None
        else:
            # 只有一個憑證
            cert_arn = certificates['CertificateSummaryList'][0]['CertificateArn']
            logger.info(f"找到 ACM 憑證: {cert_arn}")
            return cert_arn
    except Exception as e:
        logger.error(f"獲取 ACM 憑證時發生錯誤: {e}")
        return None

def configure_alb_with_cert(cert_arn):
    """配置 ALB 使用 ACM 憑證"""
    try:
        if not cert_arn:
            logger.error("未提供有效的憑證 ARN")
            return False
        
        # 創建 HTTPS 監聽器
        elb = boto3.client('elbv2', region_name=AWS_REGION)
        
        # 獲取 ALB ARN
        albs = elb.describe_load_balancers(Names=[ALB_NAME])
        if not albs['LoadBalancers']:
            logger.error(f"找不到名為 {ALB_NAME} 的負載均衡器")
            return False
        
        alb_arn = albs['LoadBalancers'][0]['LoadBalancerArn']
        
        # 創建 HTTPS 監聽器
        response = elb.create_listener(
            LoadBalancerArn=alb_arn,
            Protocol='HTTPS',
            Port=443,
            Certificates=[
                {
                    'CertificateArn': cert_arn
                }
            ],
            SslPolicy='ELBSecurityPolicy-2016-08',
            DefaultActions=[
                {
                    'Type': 'forward',
                    'TargetGroupArn': TARGET_GROUP_ARN
                }
            ]
        )
        
        logger.info(f"已成功創建 HTTPS 監聽器: {response['Listeners'][0]['ListenerArn']}")
        return True
    except Exception as e:
        logger.error(f"配置 ALB 時發生錯誤: {e}")
        return False

def deploy_application():
    """部署應用程式到 EC2 實例"""
    # 此處實現部署應用程式的邏輯
    # 可以使用 AWS CLI、Boto3 或其他部署工具
    # 例如使用 SSH 或 AWS Systems Manager 執行遠程命令
    
    # 假設實現細節
    logger.info("開始部署應用程式...")
    logger.info("部署完成")
    
    # 提示用戶下一步操作
    logger.info(f"部署完成後，您可以通過 https://{DOMAIN_NAME} 訪問您的應用程式")
    logger.info("請確保您的域名 DNS 已正確指向 ALB 的 DNS 名稱")

def main():
    """主函數"""
    env = "production"
    if len(sys.argv) > 1:
        env = sys.argv[1]
    
    logger.info(f"準備為 {env} 環境部署到 AWS...")
    
    # 檢查 AWS CLI
    if not check_aws_cli():
        return
    
    # 檢查配置
    if not EC2_INSTANCE_ID or not ALB_NAME or not TARGET_GROUP_ARN or not DOMAIN_NAME:
        logger.error("請先在腳本中配置 AWS 相關設定")
        return
    
    # 獲取 ACM 憑證
    cert_arn = get_certificate_arn()
    if not cert_arn:
        return
    
    # 配置 ALB
    if not configure_alb_with_cert(cert_arn):
        return
    
    # 部署應用程式
    deploy_application()

if __name__ == "__main__":
    main()
