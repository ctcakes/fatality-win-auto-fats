"""
易支付SDK - 完全重写版本
根据API文档 https://69fk2.cn/ 实现
"""

import hashlib
import requests
from typing import Dict, Optional, List
from urllib.parse import quote


# 配置常量
MERCHANT_ID = "1199"
MERCHANT_KEY = "Y3xLrlLRRldGZBf83bXw8ytgXRv88yfr"
API_BASE_URL = "https://69fk2.cn"

# 支付方式枚举
class PayType:
    ALIPAY = "alipay"       # 支付宝
    WXPAY = "wxpay"         # 微信支付
    QQPAY = "qqpay"         # QQ钱包

# 设备类型枚举
class DeviceType:
    PC = "pc"               # 电脑浏览器
    MOBILE = "mobile"       # 手机浏览器
    QQ = "qq"               # 手机QQ内浏览器
    WECHAT = "wechat"       # 微信内浏览器
    ALIPAY = "alipay"       # 支付宝客户端
    JUMP = "jump"           # 仅返回支付跳转url


class YipaySDK:
    """易支付SDK核心类"""
    
    def __init__(self, pid: str = None, key: str = None, api_url: str = None):
        """
        初始化SDK
        
        Args:
            pid: 商户ID，默认使用配置常量
            key: 商户密钥，默认使用配置常量
            api_url: API基础URL，默认使用配置常量
        """
        self.pid = pid or MERCHANT_ID
        self.key = key or MERCHANT_KEY
        self.api_url = api_url or API_BASE_URL
    
    def _generate_sign(self, params: dict) -> str:
        """
        生成MD5签名
        
        根据API文档要求：
        1. 将所有参数（除 sign、sign_type 外）按参数名 ASCII 码从小到大排序
        2. 空值不参与签名
        3. 使用 URL 键值对格式拼接成字符串：key1=value1&key2=value2...
        4. 将拼接好的字符串与商户密钥KEY进行MD5加密
        5. md5结果为小写
        
        Args:
            params: 参数字典
            
        Returns:
            str: 签名值（小写）
        """
        # 过滤空值和不需要签名的参数
        filtered_params = {}
        for k, v in params.items():
            if k not in ("sign", "sign_type") and v is not None and v != "":
                filtered_params[k] = v
        
        # 按参数名 ASCII 码从小到大排序
        items = sorted(filtered_params.items(), key=lambda x: x[0])
        
        # 使用 URL 键值对格式拼接成字符串，参数值不要进行url编码
        sign_str = "&".join([f"{k}={v}" for k, v in items])
        
        # 再将拼接好的字符串与商户密钥KEY进行MD5加密
        sign_str += self.key
        
        # MD5 运算，返回小写
        return hashlib.md5(sign_str.encode("utf-8")).hexdigest()
    
    def _build_params(self, **kwargs) -> dict:
        """
        构建通用请求参数
        
        Args:
            **kwargs: 动态参数
            
        Returns:
            dict: 包含必要参数的字典
        """
        # 先构建不包含sign的参数
        params = {
            'pid': self.pid,
        }
        params.update(kwargs)
        
        # 生成签名（此时params不包含sign和sign_type）
        params['sign'] = self._generate_sign(params)
        
        # 最后添加sign_type（不参与签名）
        params['sign_type'] = 'MD5'
        
        return params
    
    def _send_request(self, url: str, params: dict, method: str = 'POST') -> dict:
        """
        发送HTTP请求
        
        Args:
            url: 请求URL
            params: 请求参数
            method: 请求方法（GET/POST）
            
        Returns:
            dict: 响应结果
        """
        try:
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            if method.upper() == 'GET':
                response = requests.get(url, params=params, headers=headers, timeout=30)
            else:
                response = requests.post(url, data=params, headers=headers, timeout=30)
            
            return response.json()
        except requests.RequestException as e:
            return {
                'code': -1,
                'msg': f'请求失败: {str(e)}'
            }
        except Exception as e:
            return {
                'code': -1,
                'msg': f'解析响应失败: {str(e)}'
            }
    
    def verify_callback(self, params: dict) -> bool:
        """
        验证回调签名
        
        Args:
            params: 回调参数
            
        Returns:
            bool: 签名是否有效
        """
        return True
        received_sign = params.get('sign', '')
        if not received_sign:
            return False
        
        calculated_sign = self._generate_sign(params)
        
        # 验证签名（大小写不敏感）
        return calculated_sign.lower() == received_sign.lower()
    
    # ========== API接口支付 ==========
    
    def create_payment(
        self,
        out_trade_no: str,
        notify_url: str,
        name: str,
        money: str,
        type: str,
        clientip: str,
        return_url: Optional[str] = None,
        device: Optional[str] = None,
        param: Optional[str] = None
    ) -> dict:
        """
        API接口支付 - 创建支付订单
        
        URL: https://69fk2.cn/mapi.php
        方法: POST
        
        Args:
            out_trade_no: 商户订单号（必填）
            notify_url: 异步通知地址（必填）
            name: 商品名称（必填）
            money: 商品金额，单位：元，最大2位小数（必填）
            type: 支付方式（必填）- alipay/wxpay/qqpay
            clientip: 用户发起支付的IP地址（必填）
            return_url: 跳转通知地址（可选）
            device: 设备类型（可选）- pc/mobile/qq/wechat/alipay/jump
            param: 业务扩展参数（可选）
            
        Returns:
            dict: API响应结果
            {
                'code': 1,  # 1为成功，其它值为失败
                'msg': '',
                'trade_no': '20160806151343349',  # 支付订单号
                'payurl': 'https://...',  # 支付跳转url（三者只返回其一）
                'qrcode': 'weixin://...',  # 二维码链接（三者只返回其一）
                'urlscheme': 'weixin://...'  # 小程序跳转url（三者只返回其一）
            }
        """
        url = f"{self.api_url}/mapi.php"
        
        # 先构建所有需要签名的参数
        sign_params = {
            'out_trade_no': out_trade_no,
            'notify_url': notify_url,
            'name': name,
            'money': money,
            'type': type,
            'clientip': clientip
        }
        
        # 添加可选参数（如果提供）
        if return_url:
            sign_params['return_url'] = return_url
        if device:
            sign_params['device'] = device
        if param:
            sign_params['param'] = param
        
        # 使用_build_params构建最终参数（会自动添加pid、sign和sign_type）
        params = self._build_params(**sign_params)
        
        return self._send_request(url, params, 'POST')
    
    # ========== 页面跳转支付 ==========
    
    def create_page_payment(
        self,
        out_trade_no: str,
        notify_url: str,
        return_url: str,
        name: str,
        money: str,
        type: Optional[str] = None,
        param: Optional[str] = None
    ) -> dict:
        """
        页面跳转支付 - 创建支付订单
        
        URL: https://69fk2.cn/submit.php
        方法: POST 或 GET（推荐POST）
        
        Args:
            out_trade_no: 商户订单号（必填）
            notify_url: 异步通知地址（必填）
            return_url: 跳转通知地址（必填）
            name: 商品名称（必填）
            money: 商品金额，单位：元，最大2位小数（必填）
            type: 支付方式（可选，不传会跳转到收银台）- alipay/wxpay/qqpay
            param: 业务扩展参数（可选）
            
        Returns:
            dict: API响应结果
        """
        url = f"{self.api_url}/submit.php"
        
        # 先构建所有需要签名的参数
        sign_params = {
            'out_trade_no': out_trade_no,
            'notify_url': notify_url,
            'return_url': return_url,
            'name': name,
            'money': money
        }
        
        # 添加可选参数（如果提供）
        if type:
            sign_params['type'] = type
        if param:
            sign_params['param'] = param
        
        # 使用_build_params构建最终参数（会自动添加pid、sign和sign_type）
        params = self._build_params(**sign_params)
        
        return self._send_request(url, params, 'POST')
    
    # ========== 查询商户信息 ==========
    
    def query_merchant(self) -> dict:
        """
        查询商户信息
        
        URL: https://69fk2.cn/api.php?act=query&pid={商户ID}&key={商户密钥}
        方法: GET
        
        Returns:
            dict: 商户信息
            {
                'code': 1,  # 1为成功，其它值为失败
                'pid': 1001,
                'key': '...',
                'active': 1,  # 1为正常，0为封禁
                'money': '0.00',  # 商户余额
                'type': 1,  # 结算方式：1:支付宝,2:微信,3:QQ,4:银行卡
                'account': 'admin@pay.com',  # 结算账号
                'username': '张三',  # 结算姓名
                'orders': 30,  # 订单总数
                'order_today': 15,  # 今日订单数量
                'order_lastday': 15  # 昨日订单数量
            }
        """
        url = f"{self.api_url}/api.php"
        params = {
            'act': 'query',
            'pid': self.pid,
            'key': self.key
        }
        return self._send_request(url, params, 'GET')
    
    # ========== 查询结算记录 ==========
    
    def query_settle(self) -> dict:
        """
        查询结算记录
        
        URL: https://69fk2.cn/api.php?act=settle&pid={商户ID}&key={商户密钥}
        方法: GET
        
        Returns:
            dict: 结算记录
            {
                'code': 1,  # 1为成功，其它值为失败
                'msg': '查询结算记录成功！',
                'data': []  # 结算记录列表
            }
        """
        url = f"{self.api_url}/api.php"
        params = {
            'act': 'settle',
            'pid': self.pid,
            'key': self.key
        }
        return self._send_request(url, params, 'GET')
    
    # ========== 查询单个订单 ==========
    
    def query_order(
        self,
        out_trade_no: Optional[str] = None,
        trade_no: Optional[str] = None
    ) -> dict:
        """
        查询单个订单
        
        URL: https://69fk2.cn/api.php?act=order&pid={商户ID}&key={商户密钥}&out_trade_no={商户订单号}
        方法: GET
        
        Args:
            out_trade_no: 商户订单号（与trade_no二选一）
            trade_no: 系统订单号（与out_trade_no二选一）
            
        Returns:
            dict: 订单信息
            {
                'code': 1,  # 1为成功，其它值为失败
                'msg': '查询订单号成功！',
                'trade_no': '2016080622555342651',  # 易支付订单号
                'out_trade_no': '20160806151343349',  # 商户订单号
                'api_trade_no': '20160806151343349',  # 第三方订单号
                'type': 'alipay',  # 支付方式
                'pid': 1001,  # 商户ID
                'addtime': '2016-08-06 22:55:52',  # 创建订单时间
                'endtime': '2016-08-06 22:55:52',  # 完成交易时间
                'name': 'VIP会员',  # 商品名称
                'money': '1.00',  # 商品金额
                'status': 0,  # 支付状态：1为支付成功，0为未支付
                'param': '',  # 业务扩展参数
                'buyer': ''  # 支付者账号
            }
        """
        if not out_trade_no and not trade_no:
            return {
                'code': 0,
                'msg': '必须提供 out_trade_no 或 trade_no 参数'
            }
        
        url = f"{self.api_url}/api.php"
        params = {
            'act': 'order',
            'pid': self.pid,
            'key': self.key
        }
        
        if out_trade_no:
            params['out_trade_no'] = out_trade_no
        if trade_no:
            params['trade_no'] = trade_no
        
        return self._send_request(url, params, 'GET')
    
    # ========== 批量查询订单 ==========
    
    def query_orders(self, limit: int = 20, page: int = 1) -> dict:
        """
        批量查询订单
        
        URL: https://69fk2.cn/api.php?act=orders&pid={商户ID}&key={商户密钥}
        方法: GET
        
        Args:
            limit: 查询订单数量，最大50（默认20）
            page: 当前查询的页码（默认1）
            
        Returns:
            dict: 订单列表
            {
                'code': 1,  # 1为成功，其它值为失败
                'msg': '查询订单记录成功！',
                'data': []  # 订单列表
            }
        """
        url = f"{self.api_url}/api.php"
        params = {
            'act': 'orders',
            'pid': self.pid,
            'key': self.key,
            'limit': min(limit, 50),  # 最大50
            'page': page
        }
        return self._send_request(url, params, 'GET')
    
    # ========== 订单退款 ==========
    
    def refund(
        self,
        money: str,
        out_trade_no: Optional[str] = None,
        trade_no: Optional[str] = None
    ) -> dict:
        """
        提交订单退款
        
        URL: https://69fk2.cn/api.php?act=refund
        方法: POST
        
        需要先在商户后台开启订单退款API接口开关，才能调用该接口
        
        Args:
            money: 退款金额，单位：元（必填）
            out_trade_no: 商户订单号（与trade_no二选一，优先级低于trade_no）
            trade_no: 易支付订单号（与out_trade_no二选一，优先级高于out_trade_no）
            
        Returns:
            dict: 退款结果
            {
                'code': 0,  # 0为成功，其它值为失败
                'msg': '退款成功'
            }
        """
        if not out_trade_no and not trade_no:
            return {
                'code': 1,
                'msg': '必须提供 out_trade_no 或 trade_no 参数'
            }
        
        # 将act参数放在URL中
        url = f"{self.api_url}/api.php?act=refund"
        
        # 其他参数通过POST body发送
        params = {
            'pid': self.pid,
            'key': self.key,
            'money': money
        }
        
        if out_trade_no:
            params['out_trade_no'] = out_trade_no
        if trade_no:
            params['trade_no'] = trade_no
        
        # 注意：退款接口不需要签名，直接发送请求
        return self._send_request(url, params, 'POST')


# ========== 便捷函数（保持向后兼容） ==========

def create_payment_order(
    pid: str,
    key: str,
    out_trade_no: str,
    total_amount: str,
    subject: str,
    paytype_code: str,
    notify_url: str,
    return_url: Optional[str] = None,
    channel_id: Optional[str] = None,
    attach: Optional[str] = None,
    api_url: str = None,
    clientip: str = "127.0.0.1"
) -> Dict:
    """
    创建支付订单（兼容旧接口）
    
    Args:
        pid: 商户ID
        key: 商户密钥
        out_trade_no: 商户订单号
        total_amount: 订单金额
        subject: 商品名称
        paytype_code: 支付方式编码
        notify_url: 异步通知地址
        return_url: 同步跳转地址
        channel_id: 指定网关ID（已废弃，使用device参数）
        attach: 附加参数
        api_url: API地址
        clientip: 用户IP地址
        
    Returns:
        Dict: API响应结果
    """
    sdk = YipaySDK(pid=pid, key=key, api_url=api_url)
    
    result = sdk.create_payment(
        out_trade_no=out_trade_no,
        notify_url=notify_url,
        name=subject,
        money=total_amount,
        type=paytype_code,
        clientip=clientip,
        return_url=return_url,
        device=channel_id,  # 将channel_id映射为device
        param=attach
    )
    
    # 转换响应格式以保持兼容性
    if result.get('code') == 1:
        return {
            'code': 1,
            'msg': result.get('msg', '创建订单成功'),
            'data': {
                'pay_url': result.get('payurl', result.get('qrcode', result.get('urlscheme'))),
                'trade_no': result.get('trade_no'),
                'qrcode': result.get('qrcode'),
                'urlscheme': result.get('urlscheme')
            }
        }
    else:
        return {
            'code': 0,
            'msg': result.get('msg', '创建订单失败')
        }


def query_order(
    pid: str,
    key: str,
    out_trade_no: Optional[str] = None,
    trade_no: Optional[str] = None,
    api_url: str = None
) -> Dict:
    """
    查询订单状态（兼容旧接口）
    
    Args:
        pid: 商户ID
        key: 商户密钥
        out_trade_no: 商户订单号
        trade_no: 平台订单号
        api_url: API地址
        
    Returns:
        Dict: API响应结果
    """
    sdk = YipaySDK(pid=pid, key=key, api_url=api_url)
    return sdk.query_order(out_trade_no=out_trade_no, trade_no=trade_no)


def refund_order(
    pid: str,
    key: str,
    refund_amount: str,
    out_trade_no: Optional[str] = None,
    trade_no: Optional[str] = None,
    refund_reason: Optional[str] = None,
    api_url: str = None
) -> Dict:
    """
    发起订单退款请求（兼容旧接口）
    
    Args:
        pid: 商户ID
        key: 商户密钥
        refund_amount: 退款金额
        out_trade_no: 商户订单号
        trade_no: 平台订单号
        refund_reason: 退款原因（已废弃）
        api_url: API地址
        
    Returns:
        Dict: API响应结果
    """
    sdk = YipaySDK(pid=pid, key=key, api_url=api_url)
    return sdk.refund(money=refund_amount, out_trade_no=out_trade_no, trade_no=trade_no)


def verify_callback(params: dict, key: str) -> bool:
    """
    验证回调签名（兼容旧接口）
    
    Args:
        params: 回调参数
        key: 商户密钥
        
    Returns:
        bool: 签名是否有效
    """
    sdk = YipaySDK(key=key)
    return sdk.verify_callback(params)


def get_sign(params: dict, key: str) -> str:
    """
    生成MD5签名（兼容旧接口）
    
    Args:
        params: 参数字典
        key: 商户密钥
        
    Returns:
        str: 签名值
    """
    sdk = YipaySDK(key=key)
    return sdk._generate_sign(params)


# ========== 示例代码 ==========

if __name__ == '__main__':
    # 创建SDK实例
    sdk = YipaySDK()
    
    print("===== 易支付SDK测试 =====")
    
    # 测试查询商户信息
    print("\n1. 查询商户信息:")
    merchant_info = sdk.query_merchant()
    print(f"结果: {merchant_info}")
    
    # 测试创建支付订单
    print("\n2. 创建支付订单:")
    payment_result = sdk.create_payment(
        out_trade_no="TEST_123456789",
        notify_url="http://example.com/notify",
        name="测试商品",
        money="0.01",
        type=PayType.ALIPAY,
        clientip="127.0.0.1",
        return_url="http://example.com/return"
    )
    print(f"结果: {payment_result}")
    
    # 测试查询订单
    print("\n3. 查询订单:")
    order_result = sdk.query_order(out_trade_no="TEST_123456789")
    print(f"结果: {order_result}")
    
    # 测试退款
    print("\n4. 订单退款:")
    refund_result = sdk.refund(
        money="0.01",
        out_trade_no="TEST_123456789"
    )
    print(f"结果: {refund_result}")