# 描述：基于 Together AI 的图像生成服务，专门设计用于与 Cursor IDE 集成

import os
import logging
from sys import stdin, stdout
import json
from fastmcp import FastMCP
import mcp.types as types
import base64
import requests
from typing import Optional, List, Dict
from concurrent.futures import ThreadPoolExecutor
import asyncio
from pathlib import Path

# API 配置
TOGETHER_API_KEY = "132831df2130ff746e5cd984738dd1857d1a6a348e0bfb8a5d9986499a13b987"

# 服务配置
CONFIG = {
    "api": {
        "url": "https://api.together.xyz/v1/images/generations",
        "model": "black-forest-labs/FLUX.1-schnell-Free",
        "timeout": 30,
        "max_retries": 3,
        "retry_delay": 5
    },
    "image": {
        "max_width": 1024,
        "max_height": 1024,
        "default_width": 1024,
        "default_height": 1024,
        "default_steps": 2,
        "max_batch_size": 4
    },
    "output": {
        "base_folder": str(Path.home() / "Documents/generate_images"),
        "allowed_extensions": [".png", ".jpg", ".jpeg"],
        "default_extension": ".png"
    }
}

def validate_save_path(save_folder: str) -> tuple[bool, str, Path]:
    """验证保存路径
    
    Args:
        save_folder: 保存目录路径
        
    Returns:
        tuple: (是否有效, 错误信息, Path对象)
    """
    try:
        # 转换为 Path 对象
        save_path = Path(save_folder)
        
        # 检查是否是绝对路径
        if not save_path.is_absolute():
            example_path = Path.home() / "Documents/images"
            return False, f"请使用绝对路径。例如: {example_path}", save_path
            
        # 检查父目录是否存在且有写权限
        parent = save_path.parent
        if not parent.exists():
            return False, f"父目录不存在: {parent}", save_path
            
        # 尝试创建目录以测试权限
        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return False, f"没有权限创建或访问目录: {save_path}", save_path
            
        # 测试写权限
        test_file = save_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            return False, f"没有目录的写入权限: {save_path}", save_path
            
        return True, "", save_path
        
    except Exception as e:
        return False, f"路径验证失败: {str(e)}", Path(save_folder)

# 配置编码
stdin.reconfigure(encoding='utf-8')
stdout.reconfigure(encoding='utf-8')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 创建 FastMCP 实例
mcp = FastMCP("image-generation-service")

class ImageGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        })
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def generate(self, prompt: str, width: int = None, height: int = None, steps: int = None) -> List[str]:
        """异步生成图像
        
        Args:
            prompt: 图片生成提示词
            width: 图片宽度
            height: 图片高度
            steps: 生成步数
            
        Returns:
            List[str]: 生成的图片的 base64 编码列表
        """
        width = width or CONFIG["image"]["default_width"]
        height = height or CONFIG["image"]["default_height"]
        steps = steps or CONFIG["image"]["default_steps"]

        for attempt in range(CONFIG["api"]["max_retries"]):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    self.executor,
                    lambda: self.session.post(
                        CONFIG["api"]["url"],
                        json={
                            "model": CONFIG["api"]["model"],
                            "prompt": prompt,
                            "width": width,
                            "height": height,
                            "steps": steps,
                            "n": CONFIG["image"]["max_batch_size"],
                            "response_format": "b64_json"
                        },
                        timeout=CONFIG["api"]["timeout"]
                    )
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and len(data['data']) > 0:
                        return [img.get('b64_json', '') for img in data['data'] if img.get('b64_json')]
                elif response.status_code == 429:  # Rate limit
                    if attempt < CONFIG["api"]["max_retries"] - 1:
                        await asyncio.sleep(CONFIG["api"]["retry_delay"])
                        continue
                
                logger.error(f"API请求失败: {response.status_code}")
                logger.error(f"响应: {response.text}")
                return []
                
            except requests.Timeout:
                logger.error(f"API请求超时 (尝试 {attempt + 1}/{CONFIG['api']['max_retries']})")
                if attempt < CONFIG["api"]["max_retries"] - 1:
                    await asyncio.sleep(CONFIG["api"]["retry_delay"])
                    continue
                return []
            except Exception as e:
                logger.error(f"生成图片时出错: {str(e)}")
                return []
        
        return []

# 创建生成器实例
generator = ImageGenerator()

@mcp.tool("use_description")
async def list_tools():
    """列出所有可用的工具及其参数"""
    example_path = str(Path.home() / "Documents/images")
    return {
        "tools": [
            {
                "name": "generate_image",
                "description": "生成图片",
                "parameters": {
                    "prompt": {
                        "type": "string",
                        "description": "图片生成提示词，建议不超过500字符",
                        "required": True
                    },
                    "file_name": {
                        "type": "string",
                        "description": "保存的文件名(不含路径，如果没有后缀则默认使用.png)",
                        "required": True
                    },
                    "save_folder": {
                        "type": "string",
                        "description": f"保存目录的绝对路径 (例如: {example_path})",
                        "required": True
                    },
                    "width": {
                        "type": "number",
                        "description": f"生成图片的宽度(可选,默认{CONFIG['image']['default_width']},最大{CONFIG['image']['max_width']})",
                        "required": False
                    },
                    "height": {
                        "type": "number",
                        "description": f"生成图片的高度(可选,默认{CONFIG['image']['default_height']},最大{CONFIG['image']['max_height']})",
                        "required": False
                    }
                }
            }
        ]
    }

@mcp.tool("generate_image")
async def generate_image(prompt: str, file_name: str, save_folder: str, width: int = None, height: int = None) -> list[types.TextContent]:
    """生成图片
    
    Args:
        prompt: 图片生成提示词
        file_name: 保存的文件名
        save_folder: 保存目录路径
        width: 生成图片的宽度(可选)
        height: 生成图片的高度(可选)
        
    Returns:
        List: 包含生成结果的 JSON 字符串
    """
    logger.info(f"收到生成请求: {prompt}")
    
    try:
        # 参数验证
        if not prompt:
            raise ValueError("prompt不能为空")
            
        if not save_folder:
            save_folder = CONFIG["output"]["base_folder"]
            
        # 验证保存路径
        is_valid, error_msg, save_path = validate_save_path(save_folder)
        if not is_valid:
            raise ValueError(error_msg)
            
        width = width or CONFIG["image"]["default_width"]
        height = height or CONFIG["image"]["default_height"]
        
        if width <= 0 or height <= 0 or width > CONFIG["image"]["max_width"] or height > CONFIG["image"]["max_height"]:
            raise ValueError(
                f"width和height必须大于0且不超过{CONFIG['image']['max_width']}，"
                f"当前值: width={width}, height={height}"
            )
            
        # 确保文件名有正确的扩展名
        file_ext = Path(file_name).suffix.lower()
        if not file_ext or file_ext not in CONFIG["output"]["allowed_extensions"]:
            file_name = f"{Path(file_name).stem}{CONFIG['output']['default_extension']}"
            
        # 生成图片
        image_data_list = await generator.generate(prompt, width, height)
        if not image_data_list:
            raise Exception("未能生成图片")
            
        # 保存图片
        saved_images = []
        for i, image_data in enumerate(image_data_list):
            try:
                # 构造保存路径
                if i > 0:
                    current_save_path = save_path / f"{Path(file_name).stem}_{i}{Path(file_name).suffix}"
                else:
                    current_save_path = save_path / file_name
                    
                # 保存图片
                current_save_path.write_bytes(base64.b64decode(image_data))
                saved_images.append(str(current_save_path))
                logger.info(f"图片已保存: {current_save_path}")
            except PermissionError:
                logger.error(f"没有权限保存图片到: {current_save_path}")
                continue
            except Exception as e:
                logger.error(f"保存图片失败: {str(e)}")
                continue
        
        if not saved_images:
            raise Exception(
                "所有图片保存失败。请确保:\n"
                "1. 使用绝对路径 (例如: /Users/username/Documents/images)\n"
                "2. 目录具有写入权限\n"
                "3. 磁盘空间充足"
            )
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "error": None,
                    "images": saved_images
                }, ensure_ascii=False)
            )
        ]

    except Exception as e:
        error_msg = str(e)
        logger.error(f"生成图片失败: {error_msg}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": error_msg,
                    "images": []
                }, ensure_ascii=False)
            )
        ]

if __name__ == "__main__":
    logger.info("启动图像生成服务...")
    mcp.run()