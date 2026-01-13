"""API Key 有效性检测模块"""

import httpx
from typing import Tuple, Optional


def validate_api_key(provider_type: str, api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """
    验证 API Key 是否有效
    返回: (是否有效, 消息/余额信息)
    """
    validators = {
        'anthropic': _validate_anthropic,
        'openai': _validate_openai,
        'deepseek': _validate_deepseek,
        'gemini': _validate_gemini,
        'glm': _validate_glm,
    }
    validator = validators.get(provider_type.lower(), _validate_generic)
    try:
        return validator(api_key, endpoint, model)
    except Exception as e:
        return False, str(e)


def _validate_anthropic(api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """验证 Anthropic API Key"""
    url = endpoint.rstrip('/') + '/v1/messages'
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    # 发送最小请求测试
    data = {
        'model': model or 'claude-3-haiku-20240307',
        'max_tokens': 1,
        'messages': [{'role': 'user', 'content': 'hi'}]
    }
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, headers=headers, json=data)
        if resp.status_code == 200:
            return True, "✓ 有效"
        elif resp.status_code == 401:
            return False, "✗ 无效的 API Key"
        elif resp.status_code == 403:
            return False, "✗ 权限不足"
        elif resp.status_code == 429:
            return True, "✓ 有效 (已达速率限制)"
        elif resp.status_code == 500:
            # 500 可能是模型负载问题，检查响应内容
            try:
                err = resp.json().get('error', {}).get('message', '')
                if '负载' in err or 'overload' in err.lower():
                    return True, "✓ 有效 (模型负载已满)"
            except:
                pass
            return False, f"✗ 服务器错误 500"
        else:
            return False, f"✗ 错误 {resp.status_code}"


def _validate_openai(api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """验证 OpenAI 兼容 API - 只测试连接"""
    url = endpoint.rstrip('/') + '/chat/completions'
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    data = {'model': 'test', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 1}
    with httpx.Client(timeout=15) as client:
        resp = client.post(url, headers=headers, json=data)
        if resp.status_code == 401:
            return False, "✗ 无效的 API Key"
        else:
            return True, "✓ 有效"


def fetch_models(provider_type: str, api_key: str, endpoint: str) -> list:
    """获取可用模型列表"""
    fetchers = {
        'openai': _fetch_openai_models,
        'anthropic': _fetch_anthropic_models,
        'gemini': _fetch_gemini_models,
    }
    fetcher = fetchers.get(provider_type.lower(), _fetch_openai_models)
    try:
        return fetcher(api_key, endpoint)
    except Exception:
        return []


def _fetch_openai_models(api_key: str, endpoint: str) -> list:
    """获取 OpenAI 兼容 API 的模型列表"""
    url = endpoint.rstrip('/') + '/models'
    headers = {'Authorization': f'Bearer {api_key}'}
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('data', [])
            return sorted([m.get('id', '') for m in models if m.get('id')])
    return []


def _fetch_anthropic_models(api_key: str, endpoint: str) -> list:
    """Anthropic 没有模型列表接口，返回预设"""
    return ['claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929', 'claude-opus-4-5-20251101']


def _fetch_gemini_models(api_key: str, endpoint: str) -> list:
    """获取 Gemini 模型列表"""
    url = f"{endpoint.rstrip('/')}/models?key={api_key}"
    with httpx.Client(timeout=15) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            data = resp.json()
            models = data.get('models', [])
            return sorted([m.get('name', '').replace('models/', '') for m in models if m.get('name')])
    return []


def _validate_deepseek(api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """验证 DeepSeek API Key - 查询余额"""
    # DeepSeek 使用 /user/balance 接口
    url = endpoint.replace('/v1', '').rstrip('/') + '/user/balance'
    headers = {'Authorization': f'Bearer {api_key}'}
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            # DeepSeek 返回 balance_infos 数组
            infos = data.get('balance_infos', [])
            if infos:
                total = sum(float(b.get('total_balance', 0)) for b in infos)
                return True, f"✓ 有效 | 余额: ¥{total:.2f}"
            return True, "✓ 有效"
        elif resp.status_code == 401:
            return False, "✗ 无效的 API Key"
        else:
            return False, f"✗ 错误 {resp.status_code}"


def _validate_gemini(api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """验证 Gemini API Key"""
    url = f"{endpoint.rstrip('/')}/models?key={api_key}"
    with httpx.Client(timeout=15) as client:
        resp = client.get(url)
        if resp.status_code == 200:
            return True, "✓ 有效"
        elif resp.status_code == 400:
            err = resp.json().get('error', {}).get('message', '')
            if 'API key' in err:
                return False, "✗ 无效的 API Key"
            return False, f"✗ {err[:50]}"
        elif resp.status_code == 403:
            return False, "✗ API Key 无权限"
        else:
            return False, f"✗ 错误 {resp.status_code}"


def _validate_glm(api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """验证智谱 GLM API Key"""
    # 智谱使用 JWT token，需要生成
    import time
    import hashlib
    import hmac
    import base64

    try:
        api_key_parts = api_key.split('.')
        if len(api_key_parts) != 2:
            return False, "✗ API Key 格式错误"

        key_id, secret = api_key_parts

        # 生成 JWT
        header = base64.urlsafe_b64encode(b'{"alg":"HS256","sign_type":"SIGN"}').rstrip(b'=').decode()
        now = int(time.time() * 1000)
        payload_data = f'{{"api_key":"{key_id}","exp":{now + 3600000},"timestamp":{now}}}'
        payload = base64.urlsafe_b64encode(payload_data.encode()).rstrip(b'=').decode()

        sign_content = f"{header}.{payload}"
        signature = hmac.new(secret.encode(), sign_content.encode(), hashlib.sha256).digest()
        sign = base64.urlsafe_b64encode(signature).rstrip(b'=').decode()

        token = f"{sign_content}.{sign}"

        # 测试请求
        url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
        headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
        data = {'model': 'glm-4-flash', 'messages': [{'role': 'user', 'content': 'hi'}], 'max_tokens': 1}

        with httpx.Client(timeout=15) as client:
            resp = client.post(url, headers=headers, json=data)
            if resp.status_code == 200:
                return True, "✓ 有效"
            elif resp.status_code == 401:
                return False, "✗ 无效的 API Key"
            else:
                return False, f"✗ 错误 {resp.status_code}"
    except Exception as e:
        return False, f"✗ {str(e)[:30]}"


def _validate_generic(api_key: str, endpoint: str, model: str = None) -> Tuple[bool, str]:
    """通用验证 - 尝试 OpenAI 兼容格式"""
    url = endpoint.rstrip('/') + '/models'
    headers = {'Authorization': f'Bearer {api_key}'}
    with httpx.Client(timeout=15) as client:
        try:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return True, "✓ 有效"
            elif resp.status_code == 401:
                return False, "✗ 无效的 API Key"
            else:
                return False, f"? 状态 {resp.status_code}"
        except Exception:
            return False, "? 无法连接"


def detect_api_protocol(api_key: str, endpoint: str) -> Optional[str]:
    """
    自动检测第三方API使用的协议类型
    返回: 'openai' | 'anthropic' | None
    """
    endpoint = endpoint.rstrip('/')

    # 先尝试 OpenAI 协议 (/models 接口)
    try:
        url = endpoint + '/models'
        headers = {'Authorization': f'Bearer {api_key}'}
        with httpx.Client(timeout=10) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                return 'openai'
    except Exception:
        pass

    # 再尝试 Claude 协议 (/v1/messages 接口)
    try:
        url = endpoint + '/v1/messages'
        headers = {
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json'
        }
        data = {
            'model': 'claude-3-haiku-20240307',
            'max_tokens': 1,
            'messages': [{'role': 'user', 'content': 'hi'}]
        }
        with httpx.Client(timeout=10) as client:
            resp = client.post(url, headers=headers, json=data)
            # 200/429/500 都说明协议正确
            if resp.status_code in (200, 429, 500):
                return 'anthropic'
    except Exception:
        pass

    return None
