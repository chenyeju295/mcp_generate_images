# Description: Based on Volcengine (Doubao) image generation service, designed specifically for integration with Cursor IDE

import os
import logging
from sys import stdin, stdout
import json
from fastmcp import FastMCP
import mcp.types as types
import base64
import requests
from typing import Optional, List, Dict, Tuple
from concurrent.futures import ThreadPoolExecutor
import asyncio
from pathlib import Path
# 通过 pip install 'volcengine-python-sdk[ark]' 安装方舟SDK
from volcenginesdkarkruntime import Ark

# API configuration - 从环境变量读取火山引擎API密钥
VOLCENGINE_API_KEY = os.environ.get("ARK_API_KEY")

if not VOLCENGINE_API_KEY:
    raise ValueError(
        "ARK_API_KEY environment variable is not set. "
        "Please set it using: export ARK_API_KEY=your_api_key_here"
    )

# Service configuration
CONFIG = {
    "api": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "doubao-seedream-3-0-t2i-250415",  # 火山引擎豆包模型
        "timeout": 180,  # 增加超时时间到3分钟
        "max_retries": 2,  # 减少重试次数以避免总体超时
        "retry_delay": 3
    },
    "image": {
        "max_width": 1024,
        "max_height": 1024,
        "default_width": 1024,
        "default_height": 1024,
        "max_batch_size": 1  # 火山引擎一次生成一张图片
    },
    "output": {
        "base_folder": str(Path.home() / "Documents/generate_images"),
        "allowed_extensions": [".png", ".jpg", ".jpeg"],
        "default_extension": ".png"
    }
}

def validate_save_path(save_folder: str) -> tuple[bool, str, Path]:
    """Validate the save path
    
    Args:
        save_folder: Directory path to save files
        
    Returns:
        tuple: (is_valid, error_message, Path object)
    """
    try:
        # Convert to Path object
        save_path = Path(save_folder)
        
        # Check if absolute path
        if not save_path.is_absolute():
            example_path = Path.home() / "Documents/images"
            return False, f"Please use an absolute path. Example: {example_path}", save_path
            
        # Check if parent directory exists and has write permissions
        parent = save_path.parent
        if not parent.exists():
            return False, f"Parent directory does not exist: {parent}", save_path
            
        # Try to create directory to test permissions
        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return False, f"No permission to create or access directory: {save_path}", save_path
            
        # Test write permissions
        test_file = save_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except PermissionError:
            return False, f"No write permission for directory: {save_path}", save_path
            
        return True, "", save_path
        
    except Exception as e:
        return False, f"Path validation failed: {str(e)}", Path(save_folder)

# Configure encoding
stdin.reconfigure(encoding='utf-8')
stdout.reconfigure(encoding='utf-8')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastMCP instance
mcp = FastMCP("image-generation-service")

class ImageGenerator:
    def __init__(self):
        # 初始化Ark客户端
        self.client = Ark(
            base_url=CONFIG["api"]["base_url"],
            api_key=VOLCENGINE_API_KEY,
        )
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def generate(self, prompt: str, width: int = None, height: int = None) -> Tuple[List[str], str]:
        """Generate images asynchronously using Volcengine API
        
        Args:
            prompt: Image generation prompt
            width: Image width (ignored for now, as Volcengine API handles sizing automatically)
            height: Image height (ignored for now, as Volcengine API handles sizing automatically)
            
        Returns:
            Tuple[List[str], str]: List of image URLs (not base64) and error message (if any)
        """
        width = width or CONFIG["image"]["default_width"]
        height = height or CONFIG["image"]["default_height"]
        
        # Output parameters for diagnostics
        logger.info(f"Generation parameters: prompt='{prompt[:50]}...', width={width}, height={height}")
        
        # Check maximum size supported by the model
        model_max_size = 1024
        if width > model_max_size or height > model_max_size:
            return [], f"Current model '{CONFIG['api']['model']}' only supports a maximum size of {model_max_size}x{model_max_size}"

        for attempt in range(CONFIG["api"]["max_retries"]):
            try:
                logger.info(f"Attempting to generate image (Attempt {attempt + 1}/{CONFIG['api']['max_retries']})")
                
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    self.executor,
                    lambda: self.client.images.generate(
                        model=CONFIG["api"]["model"],
                        prompt=prompt,
                        watermark= False,
                    )
                )
                
                if response and response.data and len(response.data) > 0:
                    # 火山引擎返回的是图片URL，需要下载并转换为base64
                    image_urls = [img.url for img in response.data if img.url]
                    logger.info(f"Received {len(image_urls)} image URLs from API")
                    
                    if image_urls:
                        # 下载图片并转换为base64
                        base64_images = []
                        for i, url in enumerate(image_urls):
                            try:
                                logger.info(f"Downloading image {i+1}/{len(image_urls)} from URL...")
                                # 使用较短的超时时间下载图片
                                img_response = requests.get(url, timeout=30)
                                if img_response.status_code == 200:
                                    img_base64 = base64.b64encode(img_response.content).decode('utf-8')
                                    base64_images.append(img_base64)
                                    logger.info(f"Successfully downloaded and encoded image {i+1}")
                                else:
                                    logger.warning(f"Failed to download image from URL: {url}, status: {img_response.status_code}")
                                    # 如果下载失败，仍然返回已有的图片（如果有的话）
                            except requests.Timeout:
                                logger.error(f"Timeout downloading image from {url}")
                                continue
                            except Exception as e:
                                logger.error(f"Error downloading image from {url}: {str(e)}")
                                continue
                        
                        if base64_images:
                            logger.info(f"Successfully processed {len(base64_images)} images")
                            return base64_images, ""
                        else:
                            return [], "Failed to download any generated images"
                    else:
                        return [], "API returned success but no image URLs"
                else:
                    error_msg = "API returned empty or invalid response"
                    logger.error(error_msg)
                    return [], error_msg
                
            except Exception as e:
                error_str = str(e)
                
                # 检查特定的错误类型
                if "ModelNotOpen" in error_str:
                    error_msg = (
                        f"模型未激活: 您的账户还未激活模型 {CONFIG['api']['model']}。"
                        "请在火山引擎方舟控制台中激活该模型服务。"
                    )
                    logger.error(error_msg)
                    return [], error_msg
                elif "401" in error_str or "Unauthorized" in error_str:
                    error_msg = "API认证失败，请检查ARK_API_KEY环境变量是否正确设置"
                    logger.error(error_msg)
                    return [], error_msg
                elif "timeout" in error_str.lower():
                    error_msg = f"API请求超时 (尝试 {attempt + 1}/{CONFIG['api']['max_retries']})"
                    logger.error(error_msg)
                else:
                    error_msg = f"图像生成错误 (尝试 {attempt + 1}/{CONFIG['api']['max_retries']}): {error_str}"
                    logger.error(error_msg)
                
                # 对于非永久性错误，进行重试
                if attempt < CONFIG["api"]["max_retries"] - 1 and "ModelNotOpen" not in error_str and "401" not in error_str:
                    wait_time = CONFIG["api"]["retry_delay"] * (attempt + 1)
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                    continue
                
                return [], error_msg
        
        return [], "Maximum retry attempts reached, image generation failed"

# Create generator instance
generator = ImageGenerator()

@mcp.tool("use_description")
async def list_tools():
    """List all available tools and their parameters"""
    example_path = str(Path.home() / "Documents/images")
    return {
        "tools": [
            {
                "name": "generate_image",
                "description": "Generate image using Volcengine Doubao model",
                "parameters": {
                    "prompt": {
                        "type": "string",
                        "description": "Image generation prompt, recommended to be under 500 characters",
                        "required": True
                    },
                    "file_name": {
                        "type": "string",
                        "description": "Filename to save (without path, defaults to .png if no extension)",
                        "required": True
                    },
                    "save_folder": {
                        "type": "string",
                        "description": f"Absolute path to save directory (example: {example_path})",
                        "required": True
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "description": "Image aspect ratio, supports '1:1', '4:3', '16:9', '3:4', '9:16'. Default is '1:1'",
                        "required": False
                    }
                }
            }
        ]
    }

@mcp.tool("generate_image")
async def generate_image(prompt: str, file_name: str, save_folder: str, aspect_ratio: str = "1:1") -> list[types.TextContent]:
    """Generate image using Volcengine Doubao model
    
    Args:
        prompt: Image generation prompt
        file_name: Filename to save
        save_folder: Directory path to save
        aspect_ratio: Image aspect ratio, supports '1:1', '4:3', '16:9', '3:4', '9:16'
        
    Returns:
        List: JSON string containing generation results
    """
    logger.info(f"Received generation request: {prompt}")
    
    try:
        # Parameter validation
        if not prompt:
            raise ValueError("Prompt cannot be empty")
            
        if not save_folder:
            save_folder = CONFIG["output"]["base_folder"]
            
        # Validate save path
        is_valid, error_msg, save_path = validate_save_path(save_folder)
        if not is_valid:
            raise ValueError(error_msg)
        
        # Calculate dimensions from aspect ratio
        aspect_ratios = {
            "1:1": (1024, 1024),
            "4:3": (1024, 768),
            "16:9": (1024, 576),
            "3:4": (768, 1024),
            "9:16": (576, 1024)
        }
        
        if aspect_ratio not in aspect_ratios:
            valid_ratios = ", ".join(aspect_ratios.keys())
            raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}, please use one of: {valid_ratios}")
        
        width, height = aspect_ratios[aspect_ratio]
        logger.info(f"Using aspect ratio {aspect_ratio}, calculated width={width}, height={height}")
        
        if width <= 0 or height <= 0 or width > CONFIG["image"]["max_width"] or height > CONFIG["image"]["max_height"]:
            raise ValueError(
                f"Width and height must be greater than 0 and not exceed {CONFIG['image']['max_width']}x{CONFIG['image']['max_height']}, "
                f"current values: width={width}, height={height}"
            )
            
        # Ensure filename has correct extension
        file_ext = Path(file_name).suffix.lower()
        if not file_ext or file_ext not in CONFIG["output"]["allowed_extensions"]:
            file_name = f"{Path(file_name).stem}{CONFIG['output']['default_extension']}"
            
        # Generate image
        image_data_list, error_message = await generator.generate(prompt, width, height)
        if not image_data_list:
            if error_message:
                raise Exception(f"Failed to generate image: {error_message}")
            else:
                raise Exception("Failed to generate image: Unknown error")
            
        # Save images
        saved_images = []
        for i, image_data in enumerate(image_data_list):
            try:
                # Construct save path
                if i > 0:
                    current_save_path = save_path / f"{Path(file_name).stem}_{i}{Path(file_name).suffix}"
                else:
                    current_save_path = save_path / file_name
                    
                # Save image
                current_save_path.write_bytes(base64.b64decode(image_data))
                saved_images.append(str(current_save_path))
                logger.info(f"Image saved: {current_save_path}")
            except PermissionError:
                logger.error(f"No permission to save image to: {current_save_path}")
                continue
            except Exception as e:
                logger.error(f"Failed to save image: {str(e)}")
                continue
        
        if not saved_images:
            raise Exception(
                "All image saves failed. Please ensure:\n"
                "1. Using absolute path (example: /Users/username/Documents/images)\n"
                "2. Directory has write permissions\n"
                "3. Sufficient disk space"
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
        logger.error(f"Image generation failed: {error_msg}")
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
    logger.info("Starting Volcengine (Doubao) image generation service...")
    mcp.run()
