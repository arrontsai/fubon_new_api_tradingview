#!/bin/bash
set -e
# 1. 清空 python 目錄
rm -rf python/*
# 2. 安裝 whl 到 python 目錄（這裡 whl 必須在專案根目錄）
pip install ../fubon_neo-2.2.0-cp37-abi3-manylinux_2_17_x86_64.whl -t python/
# 3. 安裝其他依賴（如有）
pip install "requests>=2.25.0,<2.30.0" python-dotenv==1.0.0 setuptools>=65.0.0 -t python/
# 4. 打包成 zip
cd python
zip -r ../fubon_sdk_layer.zip .
cd ..
echo "Layer 打包完成，請上傳 layer/fubon_sdk_layer.zip 至 AWS Lambda Layer，並於 Lambda 設定掛載此 Layer。"
