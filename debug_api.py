#!/usr/bin/env python3
"""
调试火山引擎API连接问题
"""

import os
import asyncio
import time
from pathlib import Path

# 添加详细的日志
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

try:
    from volcenginesdkarkruntime import Ark
    logger.info("✅ volcenginesdkarkruntime导入成功")
except ImportError as e:
    logger.error(f"❌ 导入错误: {e}")
    exit(1)

async def test_api_step_by_step():
    """分步测试API"""
    
    # 1. 检查环境变量
    api_key = os.environ.get("ARK_API_KEY")
    if not api_key:
        logger.error("❌ ARK_API_KEY 环境变量未设置")
        return False
    logger.info(f"✅ API Key存在: {api_key[:10]}...")
    
    # 2. 初始化客户端
    try:
        client = Ark(
            base_url="https://ark.cn-beijing.volces.com/api/v3",
            api_key=api_key,
        )
        logger.info("✅ 客户端初始化成功")
    except Exception as e:
        logger.error(f"❌ 客户端初始化失败: {e}")
        return False
    
    # 3. 测试API调用
    try:
        logger.info("🔄 开始API调用...")
        start_time = time.time()
        
        response = client.images.generate(
            model="doubao-seedream-3-0-t2i-250415",
            prompt="猴子"
        )
        
        end_time = time.time()
        logger.info(f"✅ API调用成功，耗时: {end_time - start_time:.2f}秒")
        
        if response and response.data and len(response.data) > 0:
            logger.info(f"✅ 生成了 {len(response.data)} 张图片")
            for i, img in enumerate(response.data):
                logger.info(f"图片 {i+1} URL: {img.url}")
                
                # 测试URL是否可访问
                import requests
                try:
                    img_response = requests.head(img.url, timeout=10)
                    logger.info(f"✅ 图片URL可访问: {img_response.status_code}")
                except Exception as e:
                    logger.error(f"❌ 图片URL不可访问: {e}")
        else:
            logger.error("❌ API返回为空")
            return False
            
    except Exception as e:
        logger.error(f"❌ API调用失败: {e}")
        return False
    
    return True

if __name__ == "__main__":
    result = asyncio.run(test_api_step_by_step())
    if result:
        print("\n🎉 所有测试通过！")
    else:
        print("\n💥 测试失败！")
