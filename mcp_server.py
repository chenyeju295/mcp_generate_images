# Description: Based on Together AI's image generation service, designed specifically for integration with Cursor IDE

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

# API configuration
TOGETHER_API_KEY = "132831df2130ff746e5cd984738dd1857d1a6a348e0bfb8a5d9986499a13b987"

# Service configuration
CONFIG = {
    "api": {
        "url": "https://api.together.xyz/v1/images/generations",
        "model": "black-forest-labs/FLUX.1-schnell-Free",
        "timeout": 60,
        "max_retries": 3,
        "retry_delay": 5
    },
    "image": {
        "max_width": 1024,
        "max_height": 1024,
        "default_width": 1024,
        "default_height": 1024,
        "default_steps": 3,
        "max_batch_size": 4
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
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        })
        self.executor = ThreadPoolExecutor(max_workers=4)

    async def generate(self, prompt: str, width: int = None, height: int = None, steps: int = None) -> Tuple[List[str], str]:
        """Generate images asynchronously
        
        Args:
            prompt: Image generation prompt
            width: Image width
            height: Image height
            steps: Generation steps, between 1-4
            
        Returns:
            Tuple[List[str], str]: List of base64 encoded images and error message (if any)
        """
        width = width or CONFIG["image"]["default_width"]
        height = height or CONFIG["image"]["default_height"]
        steps = steps or CONFIG["image"]["default_steps"]
        
        # Output parameters for diagnostics
        logger.info(f"Generation parameters: prompt='{prompt[:50]}...', width={width}, height={height}, steps={steps}")
        
        # Check maximum size supported by the model
        model_max_size = 1024  # Actual maximum size supported by the model
        if width > model_max_size or height > model_max_size:
            return [], f"Current model '{CONFIG['api']['model']}' only supports a maximum size of {model_max_size}x{model_max_size}"
        
        # Validate steps parameter
        if steps < 1 or steps > 4:
            return [], f"Steps parameter must be between 1-4, current value: {steps}"

        for attempt in range(CONFIG["api"]["max_retries"]):
            try:
                logger.info(f"Attempting to generate image (Attempt {attempt + 1}/{CONFIG['api']['max_retries']})")
                
                # Increase timeout for different image sizes
                timeout = CONFIG["api"]["timeout"] * (1 + (width * height) / (1024 * 1024))
                logger.info(f"API request timeout set to {timeout:.1f} seconds")
                
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
                        timeout=timeout
                    )
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and len(data['data']) > 0:
                        images = [img.get('b64_json', '') for img in data['data'] if img.get('b64_json')]
                        if images:
                            return images, ""
                        else:
                            return [], "API returned success but no image data"
                    else:
                        error_msg = f"API returned incorrect structure: {json.dumps(data)[:200]}..."
                        logger.error(error_msg)
                        return [], error_msg
                elif response.status_code == 401:
                    error_msg = "API authentication failed, please check API key"
                    logger.error(error_msg)
                    return [], error_msg
                elif response.status_code == 429:  # Rate limit
                    error_msg = "API rate limited"
                    logger.warning(error_msg)
                    if attempt < CONFIG["api"]["max_retries"] - 1:
                        wait_time = CONFIG["api"]["retry_delay"] * (attempt + 1)
                        logger.info(f"Waiting {wait_time} seconds before retrying...")
                        await asyncio.sleep(wait_time)
                        continue
                    return [], error_msg
                else:
                    try:
                        error_data = response.json()
                        error_msg = f"API request failed (HTTP {response.status_code}): {json.dumps(error_data)[:200]}..."
                    except:
                        error_msg = f"API request failed (HTTP {response.status_code}): {response.text[:200]}..."
                    
                    logger.error(error_msg)
                    
                    if attempt < CONFIG["api"]["max_retries"] - 1 and response.status_code >= 500:
                        wait_time = CONFIG["api"]["retry_delay"] * (attempt + 1)
                        logger.info(f"Server error, waiting {wait_time} seconds before retrying...")
                        await asyncio.sleep(wait_time)
                        continue
                    
                    return [], error_msg
                
            except requests.Timeout:
                error_msg = f"API request timeout (Attempt {attempt + 1}/{CONFIG['api']['max_retries']})"
                logger.error(error_msg)
                if attempt < CONFIG["api"]["max_retries"] - 1:
                    wait_time = CONFIG["api"]["retry_delay"] * (attempt + 1)
                    logger.info(f"Waiting {wait_time} seconds before retrying...")
                    await asyncio.sleep(wait_time)
                    continue
                return [], error_msg
            except requests.ConnectionError:
                error_msg = "Connection to API server failed, please check network connection"
                logger.error(error_msg)
                if attempt < CONFIG["api"]["max_retries"] - 1:
                    wait_time = CONFIG["api"]["retry_delay"] * (attempt + 1)
                    logger.info(f"Waiting {wait_time} seconds before retrying...")
                    await asyncio.sleep(wait_time)
                    continue
                return [], error_msg
            except Exception as e:
                error_msg = f"Error generating image: {str(e)}"
                logger.error(error_msg)
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
                "description": "Generate image",
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
                    },
                    "steps": {
                        "type": "number",
                        "description": "Number of inference/sampling steps — generally more steps produces higher quality but takes longer, supports values 1-4, default is 3",
                        "required": False
                    }
                }
            }
        ]
    }

@mcp.tool("generate_image")
async def generate_image(prompt: str, file_name: str, save_folder: str, aspect_ratio: str = "1:1", steps: int = 3) -> list[types.TextContent]:
    """Generate image
    
    Args:
        prompt: Image generation prompt
        file_name: Filename to save
        save_folder: Directory path to save
        aspect_ratio: Image aspect ratio, supports '1:1', '4:3', '16:9', '3:4', '9:16'
        steps: Number of inference/sampling steps, supports values 1-4
        
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
        
        # Validate steps parameter
        if steps < 1 or steps > 4:
            raise ValueError(f"Steps parameter must be between 1-4, current value: {steps}")
        
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
        logger.info(f"Using aspect ratio {aspect_ratio}, calculated width={width}, height={height}, steps={steps}")
        
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
        image_data_list, error_message = await generator.generate(prompt, width, height, steps)
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
    logger.info("Starting image generation service...")
    mcp.run()
