# -*- coding: utf-8 -*-
"""
AWS Secrets Manager 輔助模組

用於從 AWS Secrets Manager 讀取敏感憑證資訊
"""
import os
import json
import logging
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

def get_secret(secret_name=None):
    """
    從 AWS Secrets Manager 獲取密鑰
    
    Args:
        secret_name: 密鑰名稱，如果不提供則從環境變數 SECRETS_NAME 獲取
        
    Returns:
        包含解密後的密鑰數據的字典
    """
    # 如果沒有提供密鑰名稱，嘗試從環境變數獲取
    if not secret_name:
        secret_name = os.environ.get('SECRETS_NAME', 'fubon/cert')
    
    # 獲取區域名稱
    region_name = os.environ.get('AWS_REGION', 'ap-northeast-1')
    
    logger.info(f"從 AWS Secrets Manager 獲取密鑰: {secret_name}")
    
    # 創建 Secrets Manager 客戶端
    try:
        session = boto3.session.Session()
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
    except Exception as e:
        logger.error(f"建立 Secrets Manager 客戶端失敗: {e}")
        return None
    
    try:
        # 獲取密鑰
        response = client.get_secret_value(SecretId=secret_name)
        
        # 解析密鑰內容
        if 'SecretString' in response:
            secret = response['SecretString']
            try:
                # 嘗試將密鑰字符串解析為 JSON
                return json.loads(secret)
            except json.JSONDecodeError:
                # 如果不是 JSON 格式，則返回原始字符串
                return {"raw_secret": secret}
        else:
            logger.warning("密鑰不包含 SecretString")
            return None
            
    except ClientError as e:
        error_code = e.response['Error']['Code']
        error_message = e.response['Error']['Message']
        logger.error(f"獲取密鑰失敗: {error_code} - {error_message}")
        return None
    except Exception as e:
        logger.error(f"處理密鑰時發生未知錯誤: {e}")
        return None
