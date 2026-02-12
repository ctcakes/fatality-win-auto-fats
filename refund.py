"""
退款模块 - 使用新的易支付SDK
"""

from get_epay_sign import YipaySDK, refund_order

# 商户配置
PID = "1199"  # 商户ID
KEY = "Y3xLrlLRRldGZBf83bXw8ytgXRv88yfr"  # 商户密钥
API_URL = "https://69fk2.cn"  # API基础地址


def refund(order_id, amount, refund_reason=None, use_trade_no=False):
    """
    发起退款
    
    Args:
        order_id: 订单号（可以是商户订单号或平台订单号）
        amount: 退款金额，单位：元
        refund_reason: 退款原因（可选，已废弃）
        use_trade_no: 是否使用平台订单号进行退款（默认False，使用商户订单号）
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # 创建SDK实例
    sdk = YipaySDK(pid=PID, key=KEY, api_url=API_URL)
    
    # 根据新API文档，退款接口不需要签名
    # 根据use_trade_no参数决定使用哪个订单号
    if use_trade_no:
        # 使用trade_no（易支付订单号）作为退款订单号
        result = sdk.refund(
            money=amount,
            trade_no=order_id
        )
    else:
        # 使用out_trade_no（商户订单号）作为退款订单号
        result = sdk.refund(
            money=amount,
            out_trade_no=order_id
        )
    
    # 根据新API文档，code=0表示退款成功
    if result.get('code') == 0:
        print(f"退款成功: {result.get('msg', '')}")
        return True, result.get('msg', '退款成功')
    else:
        print(f"退款失败: {result.get('msg', '未知错误')}")
        return False, result.get('msg', '退款失败，未知错误')


# ========== 兼容旧接口的函数 ==========

def refund_old(order_id, amount, refund_reason=None):
    """
    发起退款（兼容旧接口）
    
    Args:
        order_id: 订单号（可以是商户订单号或平台订单号）
        amount: 退款金额
        refund_reason: 退款原因（可选）
    
    Returns:
        tuple: (success: bool, message: str)
    """
    # 判断订单号类型
    # 如果订单号包含HVH或ORDER，则认为是商户订单号，否则认为是平台订单号
    if 'HVH' in order_id or 'ORDER' in order_id:
        # 使用out_trade_no作为退款订单号
        result = refund_order(
            pid=PID,
            key=KEY,
            out_trade_no=order_id,
            refund_amount=amount,
            refund_reason=refund_reason,
            api_url=API_URL
        )
    else:
        # 使用trade_no作为退款订单号
        result = refund_order(
            pid=PID,
            key=KEY,
            trade_no=order_id,
            refund_amount=amount,
            refund_reason=refund_reason,
            api_url=API_URL
        )
    
    # 注意：旧接口和新接口的返回码含义不同
    # 旧接口：code=1表示成功
    # 新接口：code=0表示成功
    if result.get('code') == 1:
        refund_status = result.get('data', {}).get('refund_status', 'UNKNOWN')
        print(f"退款成功: {result.get('msg', '')}, 退款状态: {refund_status}")
        return True, f'退款成功，状态: {refund_status}。' + result.get('msg', '')
    else:
        print(f"退款失败: {result.get('msg', '未知错误')}")
        return False, result.get('msg', '退款失败，未知错误')


if __name__ == '__main__':
    # 测试退款功能
    print("===== 退款测试 =====")
    
    # 测试1：使用商户订单号退款
    print("\n测试1：使用商户订单号退款")
    order_no = 'HVHGOD_1234567890_0000'
    refund_amount = "0.01"
    success, message = refund(order_no, refund_amount, use_trade_no=False)
    print(f"退款结果: {'成功' if success else '失败'}, 消息: {message}")
    
    # 测试2：使用平台订单号退款
    print("\n测试2：使用平台订单号退款")
    trade_no = '2024021012345678901'
    success, message = refund(trade_no, refund_amount, use_trade_no=True)
    print(f"退款结果: {'成功' if success else '失败'}, 消息: {message}")
    
    # 测试3：使用旧接口退款
    print("\n测试3：使用旧接口退款")
    order_no = 'HVHGOD_1234567890_0000'
    success, message = refund_old(order_no, refund_amount, refund_reason='测试退款')
    print(f"退款结果: {'成功' if success else '失败'}, 消息: {message}")