#!/usr/bin/env python3
"""
测试MCP服务的完整流程
"""

import asyncio
import tempfile
import os
from pathlib import Path

# 直接导入我们的服务代码
import sys
sys.path.append(os.path.dirname(__file__))

from mcp_server import generate_image

async def test_full_mcp_service():
    """测试完整的MCP服务流程"""
    
    print("🔧 开始测试MCP图像生成服务...")
    
    # 创建临时目录用于测试
    temp_dir = Path(tempfile.mkdtemp())
    print(f"📁 使用临时目录: {temp_dir}")
    
    try:
        # 测试参数
        prompt = "一只可爱的小猫咪"
        file_name = "test_cat.png"
        save_folder = str(temp_dir)
        aspect_ratio = "1:1"
        
        print(f"🎨 测试参数:")
        print(f"   提示词: {prompt}")
        print(f"   文件名: {file_name}")
        print(f"   保存路径: {save_folder}")
        print(f"   宽高比: {aspect_ratio}")
        
        print("\n🔄 调用generate_image函数...")
        
        # 调用MCP函数
        result = await generate_image(
            prompt=prompt,
            file_name=file_name,
            save_folder=save_folder,
            aspect_ratio=aspect_ratio
        )
        
        print(f"✅ 函数调用完成，返回结果类型: {type(result)}")
        
        if result and len(result) > 0:
            # 解析结果
            import json
            result_data = json.loads(result[0].text)
            
            print(f"📊 结果解析:")
            print(f"   成功: {result_data.get('success', False)}")
            print(f"   错误: {result_data.get('error', 'None')}")
            print(f"   图片数量: {len(result_data.get('images', []))}")
            
            if result_data.get('success') and result_data.get('images'):
                for i, image_path in enumerate(result_data['images']):
                    if Path(image_path).exists():
                        file_size = Path(image_path).stat().st_size
                        print(f"   图片 {i+1}: {image_path} (大小: {file_size:,} 字节)")
                    else:
                        print(f"   图片 {i+1}: {image_path} (文件不存在)")
                        
                return True
            else:
                print(f"❌ 生成失败: {result_data.get('error', '未知错误')}")
                return False
        else:
            print("❌ 函数返回空结果")
            return False
            
    except Exception as e:
        print(f"❌ 测试过程中发生错误: {str(e)}")
        return False
    finally:
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(temp_dir)
            print(f"🧹 已清理临时目录: {temp_dir}")
        except Exception as e:
            print(f"⚠️  清理临时目录失败: {e}")

if __name__ == "__main__":
    result = asyncio.run(test_full_mcp_service())
    if result:
        print("\n🎉 MCP服务测试成功！")
    else:
        print("\n💥 MCP服务测试失败！")
