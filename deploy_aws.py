"""
AWS Lambda 與 API Gateway 自動部署腳本

這個腳本用於自動部署 TradingView Webhook 處理器到 AWS Lambda
並設置 API Gateway 以提供 HTTPS 端點。
"""
import os
import sys
import boto3
import json
import zipfile
import tempfile
import shutil
import time
import logging
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('deploy')

# 載入環境變數
ENV_FILE = '.env_production'
load_dotenv(ENV_FILE)

# AWS 設定
AWS_REGION = os.environ.get('AWS_REGION', 'ap-northeast-1')
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
CERT_SECRET_NAME = 'fubon/cert'  # AWS Secrets Manager 中憑證的名稱

# Lambda 設定
LAMBDA_FUNCTION_NAME = os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'fubon-tradingview-webhook')
LAMBDA_HANDLER = 'simple_webhook_handler.handler'
LAMBDA_RUNTIME = 'python3.9'
LAMBDA_TIMEOUT = 30
LAMBDA_MEMORY_SIZE = 256
LAMBDA_ROLE_NAME = 'fubon-tradingview-webhook-role'  # IAM角色名稱

# API Gateway 設定
API_NAME = 'fubon-tradingview-api'
STAGE_NAME = 'prod'
RESOURCE_PATH = 'webhook/tradingview'

# 打包設定
DEPLOY_DIR = './deploy_package'
ZIP_FILE = './webhook_lambda.zip'
REQUIRED_FILES = [
    'simple_webhook_handler.py',
    'config.py',
    'setup_sdk.py',
    '.env'  # 我們會複製 .env_production 為 .env
]
REQUIRED_DIRS = [
    'webhook',
    'fubon_api'
]

def create_clients():
    """創建 AWS 服務客戶端"""
    session = boto3.Session(
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )
    
    return {
        'lambda': session.client('lambda'),
        'iam': session.client('iam'),
        'apigateway': session.client('apigateway'),
        'secretsmanager': session.client('secretsmanager')
    }

def prepare_deployment_package():
    """準備 Lambda 部署套件"""
    logger.info("準備 Lambda 部署套件...")
    
    # 清理舊目錄和檔案
    if os.path.exists(DEPLOY_DIR):
        shutil.rmtree(DEPLOY_DIR)
    if os.path.exists(ZIP_FILE):
        os.remove(ZIP_FILE)
    
    # 創建部署目錄
    os.makedirs(DEPLOY_DIR)
    
    # 複製必要文件
    for file in REQUIRED_FILES:
        src = file
        dst = os.path.join(DEPLOY_DIR, file)
        
        # 特殊處理 .env_production
        if file == '.env':
            src = ENV_FILE
        
        if os.path.exists(src):
            shutil.copy2(src, dst)
            logger.info(f"已複製 {src} 到 {dst}")
        else:
            logger.warning(f"找不到檔案: {src}")
    
    # 複製必要目錄
    for dir_name in REQUIRED_DIRS:
        src = dir_name
        dst = os.path.join(DEPLOY_DIR, dir_name)
        
        if os.path.exists(src):
            shutil.copytree(src, dst)
            logger.info(f"已複製目錄 {src} 到 {dst}")
        else:
            logger.warning(f"找不到目錄: {src}")
    
    # 安裝依賴
    logger.info("安裝依賴套件...")
    requirements_file = 'requirements.txt'
    pip_cmd = [
        sys.executable, '-m', 'pip',
        'install', '-r', requirements_file,
        '-t', DEPLOY_DIR
    ]
    
    try:
        subprocess.check_call(pip_cmd)
        logger.info("依賴套件安裝成功")
    except subprocess.CalledProcessError as e:
        logger.error(f"安裝依賴套件失敗: {e}")
        sys.exit(1)
    
    # 創建 ZIP 檔案
    logger.info(f"創建 ZIP 部署套件: {ZIP_FILE}...")
    with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(DEPLOY_DIR):
            for file in files:
                # 跳過 .pyc, __pycache__ 等檔案
                if '__pycache__' in root or file.endswith('.pyc'):
                    continue
                
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, DEPLOY_DIR)
                zipf.write(file_path, arcname)
    
    logger.info(f"部署套件已建立完成: {ZIP_FILE}")
    return ZIP_FILE

def create_lambda_role(iam_client):
    """創建或獲取 Lambda 執行角色"""
    logger.info(f"設定 Lambda 角色: {LAMBDA_ROLE_NAME}...")
    
    # 檢查角色是否已存在
    try:
        response = iam_client.get_role(RoleName=LAMBDA_ROLE_NAME)
        logger.info(f"角色已存在: {LAMBDA_ROLE_NAME}")
        return response['Role']['Arn']
    except iam_client.exceptions.NoSuchEntityException:
        # 創建新角色
        logger.info(f"創建新角色: {LAMBDA_ROLE_NAME}")
        
        # 基本 Lambda 信任策略
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "lambda.amazonaws.com"
                    },
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        
        # 創建角色
        response = iam_client.create_role(
            RoleName=LAMBDA_ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description="Role for Fubon TradingView webhook Lambda function"
        )
        
        # 附加基本 Lambda 執行權限
        iam_client.attach_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyArn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        )
        
        # 附加 Secrets Manager 讀取權限
        secrets_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:GetSecretValue"
                    ],
                    "Resource": f"arn:aws:secretsmanager:{AWS_REGION}:*:secret:{CERT_SECRET_NAME}*"
                }
            ]
        }
        
        iam_client.put_role_policy(
            RoleName=LAMBDA_ROLE_NAME,
            PolicyName="SecretsManagerReadAccess",
            PolicyDocument=json.dumps(secrets_policy)
        )
        
        logger.info(f"角色已創建並添加適當權限: {LAMBDA_ROLE_NAME}")
        
        # 等待角色傳播 (IAM 變更需要時間同步)
        logger.info("等待 IAM 角色傳播...")
        time.sleep(10)
        
        return response['Role']['Arn']

def create_or_update_lambda(lambda_client, role_arn, zip_file):
    """創建或更新 Lambda 函數"""
    env_vars = {}
    
    # 從 .env_production 讀取環境變數
    logger.info("從 .env_production 讀取環境變數...")
    with open(ENV_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    
    # 移除 AWS Lambda 保留的環境變數名稱
    reserved_keys = [
        'AWS_REGION', 
        'AWS_ACCESS_KEY_ID', 
        'AWS_SECRET_ACCESS_KEY', 
        'AWS_LAMBDA_FUNCTION_NAME',
        'AWS_SESSION_TOKEN',
        'AWS_DEFAULT_REGION',
        'TZ'
    ]
    
    for key in reserved_keys:
        if key in env_vars:
            del env_vars[key]
            logger.info(f"移除保留環境變數: {key}")
    
    # 設定憑證路徑為 AWS Secrets Manager 路徑
    env_vars['FUBON_CERT_PATH'] = f"secrets:{CERT_SECRET_NAME}"
    
    # 確保模擬模式在生產環境中關閉
    env_vars['ENABLE_MOCK'] = 'False'
    env_vars['APP_ENV'] = 'production'
    
    logger.info(f"設定 Lambda 環境變數: {json.dumps(env_vars, indent=2)}")
    
    # 讀取 ZIP 檔案內容
    with open(zip_file, 'rb') as f:
        zip_content = f.read()
    
    try:
        # 嘗試更新現有函數
        try:
            logger.info(f"嘗試更新現有 Lambda 函數: {LAMBDA_FUNCTION_NAME}")
            response = lambda_client.update_function_code(
                FunctionName=LAMBDA_FUNCTION_NAME,
                ZipFile=zip_content
            )
            
            # 更新環境變數
            lambda_client.update_function_configuration(
                FunctionName=LAMBDA_FUNCTION_NAME,
                Timeout=LAMBDA_TIMEOUT,
                MemorySize=LAMBDA_MEMORY_SIZE,
                Environment={
                    'Variables': env_vars
                }
            )
            
            logger.info(f"Lambda 函數已更新: {LAMBDA_FUNCTION_NAME}")
            return response['FunctionArn']
            
        except lambda_client.exceptions.ResourceNotFoundException:
            # 函數不存在，創建新函數
            logger.info(f"創建新 Lambda 函數: {LAMBDA_FUNCTION_NAME}")
            response = lambda_client.create_function(
                FunctionName=LAMBDA_FUNCTION_NAME,
                Runtime=LAMBDA_RUNTIME,
                Role=role_arn,
                Handler=LAMBDA_HANDLER,
                Code={
                    'ZipFile': zip_content
                },
                Timeout=LAMBDA_TIMEOUT,
                MemorySize=LAMBDA_MEMORY_SIZE,
                Environment={
                    'Variables': env_vars
                },
                Description="富邦期貨TradingView webhook處理器"
            )
            
            logger.info(f"Lambda 函數已創建: {LAMBDA_FUNCTION_NAME}")
            return response['FunctionArn']
            
    except Exception as e:
        logger.error(f"創建/更新 Lambda 函數時發生錯誤: {e}")
        raise

def create_api_gateway(api_client, lambda_client, lambda_arn):
    """創建或獲取 API Gateway"""
    # 查找現有 API
    logger.info(f"查找現有 API: {API_NAME}")
    apis = api_client.get_rest_apis()
    
    api_id = None
    for item in apis['items']:
        if item['name'] == API_NAME:
            api_id = item['id']
            logger.info(f"找到現有 API: {API_NAME}, ID: {api_id}")
            break
    
    # 如果沒有找到，創建新 API
    if not api_id:
        logger.info(f"創建新 API: {API_NAME}")
        response = api_client.create_rest_api(
            name=API_NAME,
            description="富邦期貨TradingView Webhook API",
            endpointConfiguration={
                'types': ['REGIONAL']
            }
        )
        api_id = response['id']
        logger.info(f"已創建新 API: {API_NAME}, ID: {api_id}")
    
    # 獲取根資源 ID
    resources = api_client.get_resources(restApiId=api_id)
    root_id = None
    webhook_resource_id = None
    tradingview_resource_id = None
    
    for resource in resources['items']:
        if resource['path'] == '/':
            root_id = resource['id']
        elif resource['path'] == '/webhook':
            webhook_resource_id = resource['id']
        elif resource['path'] == '/webhook/tradingview':
            tradingview_resource_id = resource['id']
    
    # 創建 webhook 資源 (如果不存在)
    if not webhook_resource_id:
        logger.info("創建 '/webhook' 資源...")
        response = api_client.create_resource(
            restApiId=api_id,
            parentId=root_id,
            pathPart='webhook'
        )
        webhook_resource_id = response['id']
    
    # 創建 tradingview 資源 (如果不存在)
    if not tradingview_resource_id:
        logger.info("創建 '/webhook/tradingview' 資源...")
        response = api_client.create_resource(
            restApiId=api_id,
            parentId=webhook_resource_id,
            pathPart='tradingview'
        )
        tradingview_resource_id = response['id']
    
    # 創建 POST 方法
    try:
        logger.info("檢查 POST 方法是否存在...")
        api_client.get_method(
            restApiId=api_id,
            resourceId=tradingview_resource_id,
            httpMethod='POST'
        )
        logger.info("POST 方法已存在")
    except api_client.exceptions.NotFoundException:
        logger.info("創建 POST 方法...")
        api_client.put_method(
            restApiId=api_id,
            resourceId=tradingview_resource_id,
            httpMethod='POST',
            authorizationType='NONE',
            apiKeyRequired=False
        )
    
    # 設置 Lambda 整合
    logger.info("設置 Lambda 整合...")
    region = AWS_REGION
    account_id = boto3.client('sts').get_caller_identity()['Account']
    
    api_client.put_integration(
        restApiId=api_id,
        resourceId=tradingview_resource_id,
        httpMethod='POST',
        type='AWS_PROXY',
        integrationHttpMethod='POST',
        uri=f'arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{lambda_arn}/invocations'
    )
    
    # 授予 API Gateway 調用 Lambda 的權限
    try:
        lambda_client.add_permission(
            FunctionName=LAMBDA_FUNCTION_NAME,
            StatementId=f'apigateway-post-{int(time.time())}',
            Action='lambda:InvokeFunction',
            Principal='apigateway.amazonaws.com',
            SourceArn=f'arn:aws:execute-api:{region}:{account_id}:{api_id}/*/*/webhook/tradingview'
        )
        logger.info("已授予 API Gateway 調用 Lambda 的權限")
    except lambda_client.exceptions.ResourceConflictException:
        logger.info("API Gateway 已有調用 Lambda 的權限")
    
    # 部署 API
    logger.info(f"部署 API 到 {STAGE_NAME} 階段...")
    api_client.create_deployment(
        restApiId=api_id,
        stageName=STAGE_NAME,
        description=f'部署到 {STAGE_NAME} 階段'
    )
    
    # 獲取調用 URL
    invoke_url = f'https://{api_id}.execute-api.{region}.amazonaws.com/{STAGE_NAME}/webhook/tradingview'
    logger.info(f"API 部署完成，調用 URL: {invoke_url}")
    
    return {
        'api_id': api_id,
        'invoke_url': invoke_url
    }

def create_test_script(invoke_url):
    """創建測試腳本以模擬 TradingView 發送的 webhook"""
    script_path = 'test_webhook.py'
    
    script_content = f'''"""
TradingView Webhook 測試腳本

用於模擬 TradingView 發送的 webhook 請求。
"""
import requests
import json
import time

# API Gateway URL
URL = "{invoke_url}"

# 測試數據 (模擬 TradingView 發送的訊息)
PAYLOAD = {{
    "message": "訂單buy @ 1已成交MXF1!。新策略倉位是-1"
}}

def test_webhook():
    """發送測試 webhook 請求"""
    print(f"發送 webhook 請求到: {{URL}}")
    print(f"請求內容: {{json.dumps(PAYLOAD, indent=2, ensure_ascii=False)}}")
    
    try:
        # 發送 POST 請求
        response = requests.post(URL, json=PAYLOAD)
        
        # 輸出結果
        print(f"狀態碼: {{response.status_code}}")
        print(f"回應內容:")
        
        try:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        except json.JSONDecodeError:
            print(response.text)
            
    except Exception as e:
        print(f"發送請求時發生錯誤: {{e}}")

if __name__ == "__main__":
    test_webhook()
'''
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    logger.info(f"測試腳本已創建: {script_path}")
    return script_path

def main():
    """主函數"""
    logger.info("開始部署 TradingView Webhook 到 AWS...")
    
    try:
        # 創建 AWS 客戶端
        clients = create_clients()
        
        # 準備部署套件
        zip_file = prepare_deployment_package()
        
        # 創建 Lambda 角色
        role_arn = create_lambda_role(clients['iam'])
        
        # 創建或更新 Lambda 函數
        lambda_arn = create_or_update_lambda(clients['lambda'], role_arn, zip_file)
        
        # 創建 API Gateway
        api_info = create_api_gateway(clients['apigateway'], clients['lambda'], lambda_arn)
        
        # 創建測試腳本
        test_script = create_test_script(api_info['invoke_url'])
        
        # 顯示總結信息
        logger.info("\n部署完成！")
        logger.info("=== 部署摘要 ===")
        logger.info(f"Lambda 函數名稱: {LAMBDA_FUNCTION_NAME}")
        logger.info(f"Lambda 函數 ARN: {lambda_arn}")
        logger.info(f"API Gateway ID: {api_info['api_id']}")
        logger.info(f"API Gateway 階段: {STAGE_NAME}")
        logger.info(f"webhook 調用 URL: {api_info['invoke_url']}")
        logger.info(f"測試腳本路徑: {test_script}")
        logger.info("\n使用以下命令運行測試腳本：")
        logger.info(f"  python {test_script}")
        
    except Exception as e:
        logger.error(f"部署過程中發生錯誤: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
