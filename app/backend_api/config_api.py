from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv, set_key
import os
import base64
import re
from typing import Optional

load_dotenv()

router = APIRouter(
    prefix="/config",
    tags=["配置管理"],
    responses={404: {"description": "Not found"}},
)

config_params = {
    'confidence': 0.8,
    'topN': 5
}

def decrypt_api_key(encrypted_key: str) -> str:
    if not encrypted_key:
        return ''
    try:
        return base64.b64decode(encrypted_key).decode('utf-8')
    except Exception as e:
        print(f"解密API密钥失败: {e}")
        return encrypted_key  # 如果解密失败，返回原始字符串

def encrypt_api_key(api_key: str) -> str:
    if not api_key:
        return ''
    try:
        return base64.b64encode(api_key.encode('utf-8')).decode('utf-8')
    except Exception as e:
        print(f"加密API密钥失败: {e}")
        return api_key 

def set_env_value_without_quotes(env_path: str, key: str, value: str):
    try:
        set_key(env_path, key, value, quote_mode="never")
    except Exception as e:
        try:
            if os.path.exists(env_path):
                with open(env_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
            else:
                lines = []

            key_pattern = rf'^{re.escape(key)}\s*='
            updated = False
            
            for i, line in enumerate(lines):
                if re.match(key_pattern, line.strip()):
                    lines[i] = f"{key}={value}\n"
                    updated = True
                    break
            
            if not updated:
                lines.append(f"{key}={value}\n")

            with open(env_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
                
        except Exception as manual_error:
            print(f"手动写入也失败: {manual_error}")
            raise manual_error

class ConfigRequest(BaseModel):
    apiUrl: str
    apiKey: str
    modelName: str
    confidence: float
    topN: int

class ConfigResponse(BaseModel):
    message: str
    updated_env: dict
    stored_params: dict

class CurrentConfigResponse(BaseModel):
    env_config: dict
    params: dict

@router.post("/update", response_model=ConfigResponse)
async def update_config(config: ConfigRequest):
    """
    接受前端发送的配置参数
    更新.env文件中的apiUrl、apiKey、modelName
    存储confidence和topN供后续调用
    """
    try:
        # 获取.env文件路径
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
        
        # 解密API密钥
        decrypted_api_key = decrypt_api_key(config.apiKey)
        
        # 更新.env文件中的前三个参数，确保不带引号
        set_env_value_without_quotes(env_path, 'OPENAI_API_BASE', config.apiUrl)
        set_env_value_without_quotes(env_path, 'OPENAI_API_KEY', decrypted_api_key)
        set_env_value_without_quotes(env_path, 'LLM_MODEL', config.modelName)
        
        # 存储后两个参数到全局变量
        config_params['confidence'] = config.confidence
        config_params['topN'] = config.topN
        
        return ConfigResponse(
            message="配置更新成功",
            updated_env={
                'apiUrl': config.apiUrl,
                'apiKey': config.apiKey,  # 返回加密的API Key用于日志
                'modelName': config.modelName
            },
            stored_params={
                'confidence': config.confidence,
                'topN': config.topN
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配置更新失败: {str(e)}")

@router.get("/current", response_model=CurrentConfigResponse)
async def get_current_config():
    """
    获取当前所有配置信息
    """
    try:
        env_config = get_env_config()
        stored_params = get_config_params()
        
        return CurrentConfigResponse(
            env_config=env_config,
            params=stored_params
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取配置失败: {str(e)}")

def get_config_params() -> dict:
    """
    获取存储的confidence和topN参数
    返回: dict包含confidence和topN
    """
    return config_params.copy()

def get_env_config() -> dict:
    """
    从.env文件获取配置信息
    返回: dict包含apiUrl、apiKey（加密）、modelName
    """
    api_key = os.getenv('OPENAI_API_KEY') or os.getenv('API_KEY', '')
    return {
        'apiUrl': os.getenv('OPENAI_API_BASE') or os.getenv('API_URL', ''),
        'apiKey': encrypt_api_key(api_key),  # 返回加密的API Key
        'modelName': os.getenv('LLM_MODEL') or os.getenv('MODEL_NAME', '')
    }

@router.get("/health")
async def config_health_check():
    """
    配置模块健康检查
    """
    return {
        "status": "healthy",
        "module": "config_api",
        "message": "配置管理模块运行正常"
    }