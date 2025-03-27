"""
自簽名 SSL 憑證生成腳本 (Python 版本)

使用 Python 的 cryptography 庫生成自簽名 SSL 憑證，無需依賴 OpenSSL 命令行工具。
適合用於開發和測試環境。

使用方法:
    python generate_cert.py [環境名稱]
    
    環境名稱可以是:
    - development (預設)
    - test
    - production
"""
import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# 設置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def install_dependencies():
    """安裝所需的依賴庫"""
    try:
        import cryptography
        logger.info("依賴庫已安裝")
        return True
    except ImportError:
        logger.info("正在安裝所需的依賴庫...")
        import subprocess
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "cryptography"])
            logger.info("依賴庫安裝成功")
            return True
        except Exception as e:
            logger.error(f"安裝依賴庫時出錯: {e}")
            return False

def generate_self_signed_cert(env="development"):
    """生成自簽名 SSL 憑證"""
    # 確保依賴庫已安裝
    if not install_dependencies():
        return
    
    # 動態導入依賴庫
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    
    # 確保證書目錄存在
    cert_dir = Path("certs")
    cert_dir.mkdir(exist_ok=True)
    
    # 設定證書檔案路徑
    cert_file = cert_dir / f"{env}_cert.pem"
    key_file = cert_dir / f"{env}_key.pem"
    
    # 檢查是否已存在
    if cert_file.exists() and key_file.exists():
        logger.warning(f"憑證和密鑰文件已存在: {cert_file}, {key_file}")
        overwrite = input("是否覆蓋現有檔案? (y/n): ").lower() == 'y'
        if not overwrite:
            logger.info("操作已取消")
            return
    
    logger.info("正在生成 RSA 密鑰...")
    # 生成私鑰
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )
    
    # 設定證書主體
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "TW"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Taiwan"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Taipei"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "FubonTradeAPI"),
        x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
    ])
    
    # 設定證書有效期
    valid_from = datetime.utcnow()
    valid_to = valid_from + timedelta(days=365)  # 一年有效期
    
    logger.info("正在生成證書...")
    # 生成證書
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(valid_to)
        .add_extension(
            x509.SubjectAlternativeName([
                x509.DNSName("localhost"),
                x509.DNSName("127.0.0.1")
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )
    
    # 保存私鑰到文件
    with open(key_file, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
        )
    
    # 保存證書到文件
    with open(cert_file, "wb") as f:
        f.write(
            cert.public_bytes(
                encoding=serialization.Encoding.PEM
            )
        )
    
    logger.info(f"自簽名 SSL 憑證已成功生成:")
    logger.info(f"憑證檔案: {cert_file}")
    logger.info(f"密鑰檔案: {key_file}")
    logger.info("注意: 這是自簽名憑證，瀏覽器會顯示警告。在生產環境中，應使用由受信任的憑證機構簽發的憑證。")
    
    # 返回檔案路徑
    return {
        "cert_file": str(cert_file),
        "key_file": str(key_file)
    }

if __name__ == "__main__":
    # 獲取命令行參數
    env = "development"
    if len(sys.argv) > 1:
        env = sys.argv[1]
        if env not in ["development", "test", "production"]:
            logger.warning(f"未知的環境: {env}，使用預設值 'development'")
            env = "development"
    
    logger.info(f"為 {env} 環境生成自簽名 SSL 憑證")
    generate_self_signed_cert(env)
