import json
import os
import requests
import time
from datetime import datetime, timedelta


# 全局变量用于缓存token
_cached_token = None
_token_expire_time = None


def get_tenant_access_token(app_id, app_secret):
    """通过飞书API获取tenant_access_token"""
    global _cached_token, _token_expire_time
    
    print(f"🔍 [DEBUG] 开始获取token，当前时间: {datetime.now()}")
    print(f"🔍 [DEBUG] 缓存状态 - token存在: {_cached_token is not None}, 过期时间: {_token_expire_time}")
    
    # 检查缓存的token是否还有效（提前5分钟刷新）
    if _cached_token and _token_expire_time:
        time_until_refresh = _token_expire_time - timedelta(minutes=5) - datetime.now()
        print(f"🔍 [DEBUG] 距离刷新时间还有: {time_until_refresh}")
        
        if datetime.now() < _token_expire_time - timedelta(minutes=5):
            print("✅ 使用缓存的tenant_access_token")
            print(f"🔍 [DEBUG] 返回缓存token: {_cached_token[:20]}...")
            return _cached_token
        else:
            print("⏰ 缓存token即将过期，需要刷新")
    else:
        print("🔍 [DEBUG] 没有有效的缓存token")
    
    print("🔄 正在获取新的tenant_access_token...")
    print(f"🔍 [DEBUG] 使用app_id: {app_id}")
    print(f"🔍 [DEBUG] 使用app_secret: {app_secret[:10]}...")
    
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "app_id": app_id,
        "app_secret": app_secret
    }
    
    try:
        print(f"🔍 [DEBUG] 发送请求到: {url}")
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"🔍 [DEBUG] 响应状态码: {response.status_code}")
        
        response.raise_for_status()
        
        result = response.json()
        print(f"🔍 [DEBUG] API响应: {result}")
        
        if result.get("code") == 0:
            token = result.get("tenant_access_token")
            expire_seconds = result.get("expire", 7200)  # 默认2小时
            
            print(f"🔍 [DEBUG] 获取到新token: {token[:20]}...")
            print(f"🔍 [DEBUG] token有效期: {expire_seconds}秒")
            
            # 缓存token和过期时间
            _cached_token = token
            _token_expire_time = datetime.now() + timedelta(seconds=expire_seconds)
            
            print(f"🔍 [DEBUG] 缓存更新完成，过期时间: {_token_expire_time}")
            print(f"✅ 成功获取tenant_access_token，有效期: {expire_seconds}秒")
            return token
        else:
            error_msg = result.get("msg", "未知错误")
            print(f"❌ [DEBUG] 飞书API返回错误码: {result.get('code')}, 错误信息: {error_msg}")
            raise Exception(f"飞书API返回错误: {error_msg}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ [DEBUG] 网络请求异常: {str(e)}")
        raise Exception(f"请求飞书API失败: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"❌ [DEBUG] JSON解析错误: {str(e)}")
        print(f"❌ [DEBUG] 响应内容: {response.text if 'response' in locals() else 'N/A'}")
        raise Exception("飞书API返回的数据格式错误")
    except Exception as e:
        print(f"❌ [DEBUG] 其他异常: {str(e)}")
        raise Exception(f"获取tenant_access_token失败: {str(e)}")


def load_config(config_path=None):
    """加载配置文件"""
    if config_path is None:
        # 默认配置文件路径
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    
    print(f"🔍 [DEBUG] 加载配置文件: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        print(f"🔍 [DEBUG] 配置文件内容: {list(config.keys())}")
        
        # 验证必要的配置项
        required_keys = ['app_token', 'table_id', 'app_id', 'app_secret']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"配置文件缺少必要参数: {key}")
        
        print(f"✅ [DEBUG] 配置文件验证通过")
        return config
    except FileNotFoundError:
        print(f"❌ [DEBUG] 配置文件不存在: {config_path}")
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    except json.JSONDecodeError as e:
        print(f"❌ [DEBUG] 配置文件JSON格式错误: {str(e)}")
        raise ValueError(f"配置文件格式错误: {config_path}")


def get_feishu_config():
    """获取飞书相关配置，包括动态获取的tenant_access_token"""
    print("🔍 [DEBUG] ========== 开始获取飞书配置 ==========")
    
    config = load_config()
    original_token = config.get('tenant_access_token', '')
    
    print(f"🔍 [DEBUG] 配置文件中的tenant_access_token: {original_token[:20]}...")
    
    # 动态获取tenant_access_token
    try:
        print("🔍 [DEBUG] 尝试动态获取tenant_access_token")
        tenant_access_token = get_tenant_access_token(
            config['app_id'], 
            config['app_secret']
        )
        print(f"🔍 [DEBUG] 动态获取成功，token: {tenant_access_token[:20]}...")
        
        # 如果获取到的token与配置文件中的不同，更新配置文件
        if tenant_access_token != original_token:
            print("🔄 检测到新token，正在更新配置文件...")
            update_success = update_config({
                'tenant_access_token': tenant_access_token
            })
            if update_success:
                print("✅ 配置文件已更新为最新token")
            else:
                print("⚠️  配置文件更新失败，但将使用新token")
        else:
            print("ℹ️  token未发生变化，无需更新配置文件")
            
    except Exception as e:
        print(f"⚠️  获取tenant_access_token失败: {str(e)}")
        print(f"🔍 [DEBUG] 异常详情: {type(e).__name__}: {str(e)}")
        
        # 如果配置文件中有备用的tenant_access_token，使用它
        tenant_access_token = config.get('tenant_access_token', '')
        if tenant_access_token:
            print("🔄 使用配置文件中的备用tenant_access_token")
            print(f"🔍 [DEBUG] 备用token: {tenant_access_token[:20]}...")
        else:
            print("❌ [DEBUG] 没有备用token可用")
            raise Exception("无法获取有效的tenant_access_token")
    
    final_config = {
        'app_token': config['app_token'],
        'table_id': config['table_id'],
        'tenant_access_token': tenant_access_token,
        'app_id': config['app_id'],
        'app_secret': config['app_secret']
    }
    
    print(f"🔍 [DEBUG] 最终返回的token: {final_config['tenant_access_token'][:20]}...")
    print("🔍 [DEBUG] ========== 飞书配置获取完成 ==========\n")
    
    return final_config


def update_config(updates, config_path=None):
    """更新配置文件"""
    if config_path is None:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    
    try:
        # 读取现有配置
        config = load_config(config_path)
        
        # 更新配置
        config.update(updates)
        
        # 写回文件
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        
        print(f"✅ 配置已更新: {config_path}")
        return True
    except Exception as e:
        print(f"❌ 更新配置失败: {str(e)}")
        return False


def clear_token_cache():
    """清除token缓存，强制重新获取"""
    global _cached_token, _token_expire_time
    print(f"🔍 [DEBUG] 清除前 - token: {_cached_token[:20] if _cached_token else 'None'}..., 过期时间: {_token_expire_time}")
    _cached_token = None
    _token_expire_time = None
    print("🗑️  已清除token缓存")