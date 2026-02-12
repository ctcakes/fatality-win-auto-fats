from get_epay_sign import refund_order
PID = 1001 
KEY = ""#商户秘钥
def refund(order_id, amount):
    # 发起退款
    #收取手续费1元
    # if float(amount) < 5:
    #     return False, "金额不足5元，无法退款"
    if float(amount) < 1:
        amount = float(amount)
    amount = float(amount) - 1
    
    result = refund_order(
        pid=PID,
        key=KEY,
        out_trade_no=order_id,
        money=amount
    )
    if result['code'] != 0:
        print(f"退款失败: {result['msg']}")
        return False, result['msg']
    else:
        print(f"退款成功: {result['msg']}")
        return True, '手续费￥1。' + result['msg']
