from flask import Flask, request, jsonify
import threading
import time
import json
import os
import requests
import hashlib
from datetime import datetime
import sqlite3
from refund import refund

app = Flask(__name__)
current_fats = 0
# IP限流字典 - 存储每个IP的最后一次请求时间
ip_last_request = {}

ORDERS_FILE = "orders.json"
#测试一下push webhook111222
# ===== 易支付系统配置 =====
# 易支付支付平台配置（https://69fk2.cn/）
MERCHANT_ID = "1199"  # 商户ID
MERCHANT_KEY = "Y3xLrlLRRldGZBf83bXw8ytgXRv88yfr"  # 商户密钥
API_URL = "https://69fk2.cn"  # API基础地址
CALLBACK_URL = "http://202.189.7.62:20112/api/payment/callback"  # 回调地址


PAY_TMP_LIST = {}
# ===== 原有订单系统 =====
# ===================== 初始化与存储函数 =====================
def load_orders():
    """加载本地 JSON 文件中的订单信息"""
    if not os.path.exists(ORDERS_FILE):
        return {"queue": [], "status": {}}
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"queue": [], "status": {}}

def save_orders():
    """保存当前内存订单状态到 JSON 文件"""
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump({"queue": order_queue, "status": order_status}, f, ensure_ascii=False, indent=2)

# 从文件加载订单数据
orders_data = load_orders()
order_queue = orders_data.get("queue", [])
order_status = orders_data.get("status", {})

order_lock = threading.Lock()  # 确保同一时间只执行一个任务
LOG_FILE = "logs.txt"

def log_sync(result):
    """记录 sync 参数和结果"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] RESULT: {result}\n")

# 使用SQLite作为轻量级数据库替代MySQL
def get_db_connection():
    conn = sqlite3.connect('orders.db')
    conn.row_factory = sqlite3.Row  # 使结果可以通过列名访问
    return conn

# 初始化数据库
def init_db():
    conn = get_db_connection()
    # 创建表（如果不存在）
    conn.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            amount REAL NOT NULL,
            payment_method TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            browser_fingerprint TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            updated_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            buy_type TEXT NOT NULL DEFAULT 'sub' CHECK (buy_type IN ('fat', 'sub')),
            fat_count INTEGER DEFAULT 10 CHECK (fat_count >= 10 OR fat_count IS NULL),
            pay_url TEXT  -- 支付链接字段
        )
    ''')
    
    # 创建settings表用于存储系统配置
    conn.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY,
            theme TEXT DEFAULT 'normal',
            fat_price REAL DEFAULT 0.75,
            sub_price REAL DEFAULT 198.0,
            admin_password_hash TEXT DEFAULT '5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8' -- 默认密码'password'的SHA256哈希
        )
    ''')
    
    # 检查并添加settings表的优惠相关字段
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(settings)")
    settings_columns = [col[1] for col in cursor.fetchall()]
    
    # 添加缺失的优惠相关字段
    if 'sale_enabled' not in settings_columns:
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN sale_enabled INTEGER DEFAULT 0")
            print("成功添加sale_enabled字段")
        except sqlite3.OperationalError:
            print("sale_enabled字段已存在")
    
    if 'sale_sub_price' not in settings_columns:
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN sale_sub_price REAL DEFAULT 0.0")
            print("成功添加sale_sub_price字段")
        except sqlite3.OperationalError:
            print("sale_sub_price字段已存在")
    
    if 'sale_fat_required' not in settings_columns:
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN sale_fat_required INTEGER DEFAULT 288")
            print("成功添加sale_fat_required字段")
        except sqlite3.OperationalError:
            print("sale_fat_required字段已存在")
    
    if 'sale_start_date' not in settings_columns:
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN sale_start_date TEXT")
            print("成功添加sale_start_date字段")
        except sqlite3.OperationalError:
            print("sale_start_date字段已存在")
    
    if 'sale_end_date' not in settings_columns:
        try:
            cursor.execute("ALTER TABLE settings ADD COLUMN sale_end_date TEXT")
            print("成功添加sale_end_date字段")
        except sqlite3.OperationalError:
            print("sale_end_date字段已存在")
    
    # 检查是否已存在browser_fingerprint列
    cursor.execute("PRAGMA table_info(orders)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # 如果browser_fingerprint列不存在，则添加它
    if 'browser_fingerprint' not in columns:
        try:
            cursor.execute('ALTER TABLE orders ADD COLUMN browser_fingerprint TEXT')
            print("成功添加browser_fingerprint列")
        except sqlite3.OperationalError:
            print("browser_fingerprint列已存在")
    
    # 检查是否已存在buy_type列
    if 'buy_type' not in columns:
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN buy_type TEXT NOT NULL DEFAULT 'sub' CHECK (buy_type IN ('fat', 'sub'))")
            print("成功添加buy_type列")
        except sqlite3.OperationalError:
            print("buy_type列已存在")
    
    # 检查是否已存在fat_count列
    if 'fat_count' not in columns:
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN fat_count INTEGER DEFAULT 10 CHECK (fat_count >= 10 OR fat_count IS NULL)")
            print("成功添加fat_count列")
        except sqlite3.OperationalError:
            print("fat_count列已存在")
    
    # 检查是否已存在pay_url列
    if 'pay_url' not in columns:
        try:
            cursor.execute("ALTER TABLE orders ADD COLUMN pay_url TEXT")
            print("成功添加pay_url列")
        except sqlite3.OperationalError:
            print("pay_url列已存在")
    
    # 检查是否已存在使用UTC时间的列定义，如果是，则更新为本地时间
    try:
        # 检查当前表结构
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='orders'")
        table_info = cursor.fetchone()
        if table_info:
            current_sql = table_info[0]
            # 如果发现使用了CURRENT_TIMESTAMP，提醒用户可能需要数据迁移
            if 'CURRENT_TIMESTAMP' in current_sql and 'localtime' not in current_sql:
                print("检测到旧的时间戳格式，建议重新创建表或手动更新时间字段")
    except:
        pass
    
    # 初始化settings表的默认值
    try:
        cursor.execute("SELECT COUNT(*) FROM settings")
        count = cursor.fetchone()[0]
        if count == 0:
            cursor.execute("INSERT INTO settings (theme, fat_price, sub_price, sale_enabled, sale_sub_price, sale_fat_required, sale_start_date, sale_end_date) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                          ('normal', 0.75, 198.0, 0, 0.0, 288, None, None))
            conn.commit()
            print("已初始化settings表默认值")
    except Exception as e:
        print(f"初始化settings表失败: {e}")
    
    conn.commit()
    conn.close()

def get_all_paid_fat_orders():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM orders WHERE status = 'paid' AND buy_type = 'fat'")
        orders = cursor.fetchall()
        total_fats = 0
        for i in orders:
            total_fats += i['fat_count']
        conn.close()
        return total_fats
    except Exception as e:
        print(f"获取已支付订单失败: {e}")
        return 0

def get_most_user():
    """获取所有的orders，然后查找在orders里面出现次数最多的用户"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM orders WHERE status = 'paid' GROUP BY username ORDER BY COUNT(*) DESC LIMIT 1")
        result = cursor.fetchone()
        return result[0] if result else ""
    except Exception as e:
        print(f"获取最常见用户失败: {e}")
        return ""

def get_most_fat_user():
    """获取所有的orders，然后查找在orders里面用户名相同并且购买fat的数量最多的用户"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""SELECT username
FROM orders
WHERE buy_type = 'fat' AND status = 'paid'
GROUP BY username
ORDER BY SUM(fat_count) DESC
LIMIT 1""")
        result = cursor.fetchone()
        return result[0] if result else ""
    except Exception as e:
        print(f"获取fat多用户失败: {e}")
        return ""

def get_most_user_order_():
    """获取下单次数最多的用户的订单总量"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username, COUNT(*) as total_orders FROM orders WHERE status = 'paid' GROUP BY username ORDER BY total_orders DESC LIMIT 1")
        result = cursor.fetchone()
        return result[1] if result else ""
    except Exception as e:
        print(f"获取下单次数最多用户失败: {e}")
        return ""
def get_most_fat_total():
    """获取购买fat次数最多的用户 购买的fat总量"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""SELECT username, SUM(fat_count) as total_fat_count
FROM orders
WHERE buy_type = 'fat' AND status = 'paid'
GROUP BY username
ORDER BY total_fat_count DESC
LIMIT 1""")
        result = cursor.fetchone()
        return result[1] if result else ""
    except Exception as e:
        print(f"获取fat次数最多用户失败: {e}")
        return ""

def migrate_timestamps():
    """迁移现有订单的时间戳到本地时间格式"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 检查是否需要迁移（检查是否有使用UTC格式的旧时间戳）
        cursor.execute("SELECT created_at FROM orders LIMIT 1")
        result = cursor.fetchone()
        
        if result:
            # 这里可以添加特定的迁移逻辑，如果需要的话
            print("检查是否需要时间戳迁移...")
            # 目前我们已经修改了表结构，新数据将使用本地时间
            # 对于现有数据，可能需要特定的迁移逻辑
        conn.close()
    except Exception as e:
        print(f"时间戳迁移过程中出现错误: {e}")

# 初始化数据库
init_db()

# 执行时间戳迁移（如果需要）
migrate_timestamps()
from new_plugin import Plugin
import asyncio

plugin = Plugin()
last_sync_time = "未同步过，请等待5分钟。"
loop = None
loop_thread = None
def on_message(message):
    print("收到消息:", message)
    if 'get_fats:' in message:
        global current_fats, last_sync_time
        current_fats = message.split(':')[1].replace(';','')
        last_sync_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

        print("fats已同步："+str(current_fats))
    elif 'buy_fat:' in message:
        # 新格式: buy_fat:success,order_id; 或 buy_fat:fail,order_id,[错误信息]
        content = message.split(':', 1)[1].rstrip(';')
        parts = content.split(',')
        
        if len(parts) < 2:
            print("buy_fat消息格式错误:", message)
            return
        
        result = parts[0].strip()
        order_id = parts[1].strip()
        
        # 判断是成功还是失败
        if result == 'success':
            print(f"充值成功返回，订单ID: {order_id}")
            
            # 修改订单状态
            if order_id in order_status:
                order_status[order_id]['status'] = 'done'
                order_status[order_id]['result'] = {
                    "code": 0,
                    "msg": "充值成功！欢迎下次光临。"
                }
                save_orders()
            else:
                print(f"订单 {order_id} 不存在于order_status中")
        elif result == 'fail':
            # 购买失败，提取错误信息（如果有）
            error_info = parts[2].strip() if len(parts) > 2 else "未知错误"
            print(f"充值失败返回，订单ID: {order_id}, 错误信息: {error_info}")
            
            # 修改订单状态
            if order_id in order_status:
                order_status[order_id]['status'] = 'error'
                order_status[order_id]['result'] = {
                    "code": 1,
                    "msg": f"充值失败：{error_info}"
                }
                
                # 获取订单金额，进行退款
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT amount FROM orders WHERE order_id = ?", (order_id,))
                order_data = cursor.fetchone()
                if order_data:
                    refund_amount = str(order_data['amount'])
                    conn.close()
                    
                    # 调用退款
                    try:
                        from refund import refund
                        success, msg = refund(order_id, refund_amount)
                        print(f"退款结果: {'成功' if success else '失败'}, {msg}")
                    except Exception as e:
                        print(f"退款异常: {e}")
                else:
                    conn.close()
                
                save_orders()
            else:
                print(f"订单 {order_id} 不存在于order_status中")
        else:
            print("未知的buy_fat结果:", result)

async def main():
    await plugin.start_server(on_message=on_message)

    # 等待连接
    print("等待浏览器插件连接...")
    while not plugin.websocket:
        await asyncio.sleep(1)

    print("浏览器插件已连接！")
    print("\n服务器保持运行中，等待命令...")
    # plugin.send_message("buy_fat:CTCAKEEEE,1;")
    # 保持服务器运行
    await asyncio.Future()  # 永久运行

def run_event_loop():
    """在独立线程中运行事件循环"""
    global loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_forever()


# ===================== 订单执行线程 =====================
def run_async(coro):
    """在事件循环中运行异步任务"""
    global loop
    # 等待事件循环可用
    max_retries = 5
    for _ in range(max_retries):
        if loop and not loop.is_closed() and loop.is_running():
            try:
                if asyncio.iscoroutine(coro):
                    future = asyncio.run_coroutine_threadsafe(coro, loop)
                    return future.result(timeout=10)  # 等待最多10秒
            except Exception as e:
                print(f"run_async 执行失败: {e}")
                return None
            break
        time.sleep(0.1)  # 等待100ms后重试
    else:
        print("警告: 事件循环不可用，无法执行异步任务")
    return None
def get_fat_ws():
    if loop and not loop.is_closed():
        # 使用 run_async 调用异步方法
        run_async(plugin.send_message_async("get_fats:"+str(current_fats)+";"))
    else:
        print("事件循环不可用")
    return True
def order_worker():
    while True:
        if not order_queue:
            time.sleep(0.5)
            continue

        order = order_queue[0]
        order_id = order.get("id")
        order_type = order.get("type")

        with order_lock:

            if order_type == "sync":
                try:
                    # 执行 sync 任务
                    #发送socket消息get_fats，等收到回复时会自动更新current_fats
                    get_fat_ws()
                    print("[SYNC] 发送同步请求...")
                    # 写 logs.txt
                    # with open("logs.txt", "a", encoding="utf-8") as f:
                    #     f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] result: {result}\n")
                    print(f"[SYNC DONE]")
                except Exception as e:
                    # with open("logs.txt", "a", encoding="utf-8") as f:
                    #     f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] sync ERROR: {e}\n")
                    print("[SYNC ERROR]", e)
                finally:
                    time.sleep(2)
                    order_queue.pop(0)
                    save_orders()
                continue  # 处理下一个订单

            # 下面是原有 sub/fat 订单处理逻辑
            if not order_id:
                # 没有 id 的订单跳过（或者给 sync 自动生成）
                order_queue.pop(0)
                save_orders()
                continue
            order_amount = order_status[order_id].get("order_amount", 0)
            order_status[order_id]["status"] = "running"
            save_orders()
            try:
                if order_type == "sub":
                    result = plugin.send_message('buy_sub:' + order["username"]+","+str(order_id)+","+str(order_amount)+";")
                    print("执行订阅购买 -> 用户名:", order["username"])
                elif order_type == "fat":
                    # 新格式：发送用户名、fat数量和订单ID
                    # 格式: buy_fat:username,fat_amount,order_id;
                    result = plugin.send_message('buy_fat:' + order["username"]+","+str(order["amount"])+","+str(order_id)+";")
                    print("执行 fat 充值 -> 用户名:", order["username"], "数量:", order["amount"], "订单ID:", order_id)
                else:
                    result = {"code": 1, "msg": "未知订单类型"}
                    order_status[order_id]["status"] = "error"

                # 消息已发送，但不设置result，让插件响应来设置实际结果
                # 可以设置一个中间状态，但保持等待插件响应
                print(f"订单 {order_id} 消息发送完成，等待插件响应。")

            except Exception as e:
                # 只有在插件没有设置错误时才设置默认错误信息
                if order_status[order_id].get("result") is None or order_status[order_id].get("status") != "error":
                    order_status[order_id]["result"] = {
                        "code": 1,
                        "msg": "请检查账户是否到账，如未到账联系客服。"+str(e)
                    }
                    order_status[order_id]["status"] = "error"
                print(f"订单 {order_id} 执行失败:", e)
            finally:
                order_queue.pop(0)
                save_orders()


#refund退款为出现错误就会立即退款，手动退款需联系客服

@app.route("/sync", methods=["GET"])
def api_sync_queue():
    """把 sync 任务加入队列"""
    order_queue.append({"type": "sync"})
    save_orders()
    return jsonify({"code": 0, "msg": "sync 已加入队列"})

@app.route("/status", methods=["GET"])
def api_status():
    # 获取客户端IP
    client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
    
    # 检查IP限流
    current_time = time.time()
    if client_ip in ip_last_request:
        elapsed = current_time - ip_last_request[client_ip]
        # if elapsed < 10:  # 10秒内不允许重复请求
        #     return jsonify({
        #         "code": 1,
        #         "msg": f"请求过于频繁，请等待{int(10 - elapsed)}秒后再试"
        #     })
    
    # 更新该IP的最后请求时间
    ip_last_request[client_ip] = current_time
    
    queue_count = len(order_queue)
    
    # 返回状态信息
    return jsonify({
        "code": 0,
        "queue_count": queue_count,
        "last_sync_time": last_sync_time,
        "current_fats": current_fats
    }) 


@app.route("/order_status", methods=["GET"])
def api_order_status():
    order_id = request.args.get("order_id")
    status = order_status.get(order_id)
    if not status:
        return jsonify({"code": 1, "msg": "订单不存在"})
    queued_count = sum(1 for o in order_queue if "id" in o or o.get("type") == "sync")

    
    
    # 如果订单还在队列中，动态计算前方数量
    if status["status"] == "queued":
        # 只统计有 'id' 的订单
        queued_orders = [o for o in order_queue if "id" in o]
        index = next((i for i, o in enumerate(queued_orders) if o["id"] == order_id), None)
        status["queued_count"] = str(index if index is not None else 0)
    print(status.get("queued_count"))
    return jsonify({
        "code": 0,
        "status": status["status"],
        "result": status["result"],
        "queued_count": str(queued_count)
    })


# ===== 支付系统API =====

# 创建支付订单接口
@app.route('/api/create-payment', methods=['POST'])
def create_payment():
    try:
        from get_epay_sign import create_payment_order
        
        data = request.json
        username = data.get('username')
        payment_method = data.get('payment_method')  # wechat 或 alipay
        browser_fingerprint = data.get('browser_fingerprint')  # 浏览器指纹
        test_mode = False  # 是否为测试模式data.get('test_mode', False)
        buy_type = data.get('buy_type', 'sub')  # 购买类型，默认为sub
        fat_count = data.get('fat_count', 10)  # 实际需要发货的fat数量
        if request.headers.getlist("X-Forwarded-For"):
            forwarded_for = request.headers.getlist("X-Forwarded-For")[0]
            # 取第一个IP地址并移除可能的前缀字符
            client_ip = forwarded_for.split(',')[0].strip()
        else:
            client_ip = request.remote_addr
        
        # 确保fat_count不小于10
        if fat_count < 10:
            return jsonify({'error': 'FAT数量不能少于10'}), 400
        
        # 从数据库获取价格设置
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT fat_price, sub_price, sale_enabled, sale_sub_price, sale_start_date, sale_end_date FROM settings LIMIT 1")
        price_result = cursor.fetchone()
        conn.close()
        
        # 检查是否在优惠期间
        is_active = False
        if price_result:
            sale_enabled = price_result['sale_enabled']
            start_date_str = price_result['sale_start_date']
            end_date_str = price_result['sale_end_date']
            
            if sale_enabled and start_date_str and end_date_str:
                try:
                    is_active = False
                except Exception as e:
                    print(f"检查优惠时间错误: {str(e)}")
        
        if price_result:
            fat_price = price_result['fat_price']
            sub_price = price_result['sub_price']
            sale_sub_price = price_result['sale_sub_price']
        else:
            # 如果没有设置价格，则使用默认值
            fat_price = 0.85
            sub_price = 198.0
            sale_sub_price = 0.0
        
        # 根据是否为测试模式确定金额
        if buy_type == 'fat':
            amount = fat_count * fat_price
        else:
            # 如果在优惠期间，使用优惠价格
            amount = fat_count * fat_price #sale_sub_price if is_active and sale_sub_price > 0 else sub_price

        if not username or not payment_method:
            return jsonify({'error': '用户名和支付方式不能为空'}), 400

        # 生成订单号 (时间戳 + 随机数)
        order_id = f"HVHGOD_{int(time.time())}_{hash(abs(hash(username))) % 10000}"

        # 保存订单到数据库
        conn = get_db_connection()
        cursor = conn.cursor()

        # 构建商品名称
        subject = '测试商品' if test_mode else (f'HVHGOD-{str(fat_count)}个FAT购买' if buy_type == 'fat' else 'HVHGOD-Fatality 30天')
        
        # 构建支付方式编码
        paytype_code = 'alipay' if payment_method == 'alipay' else 'wxpay'
        
        # 构建同步跳转地址
        return_url = f'https://hvhgod.onl/#/buy/result?order_id={order_id}'
        
        # 构建附加参数（可选）
        attach = f'username={username}&buy_type={buy_type}&fat_count={fat_count}'

        # 使用新的支付API创建订单
        response_data = create_payment_order(
            pid=MERCHANT_ID,
            key=MERCHANT_KEY,
            out_trade_no=order_id,
            total_amount=f'{amount:.2f}' if not test_mode else '0.01',
            subject=subject,
            paytype_code=paytype_code,
            notify_url=CALLBACK_URL,
            return_url=return_url,
            attach=attach,
            api_url=API_URL,
            clientip=client_ip  # 必填参数：用户发起支付的IP地址
        )

        print(f"支付 API响应: {response_data}")  # 添加调试信息

        if response_data.get('code') == 1:  # 根据API文档，1为成功状态码
            # 获取支付URL
            pay_url_value = response_data.get('data', {}).get('pay_url')
            trade_no = response_data.get('data', {}).get('trade_no')
            
            cursor.execute('''
                INSERT INTO orders (order_id, username, amount, payment_method, status, browser_fingerprint, buy_type, fat_count, pay_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (order_id, username, amount, payment_method, 'pending', browser_fingerprint, buy_type, fat_count, pay_url_value))
            conn.commit()
            conn.close()
            PAY_TMP_LIST[order_id] = {'username': username, 'amount': amount, 'created_at': datetime.now()}
            return jsonify({
                'success': True,
                'order_id': order_id,
                'payment_url': pay_url_value,  # 支付跳转url
                'trade_no': trade_no,  # 支付订单号
                'test_mode': test_mode,  # 标记是否为测试模式
                'browser_fingerprint': browser_fingerprint  # 返回浏览器指纹
            })            
        else:
            print(f"支付 API返回错误: {response_data.get('msg', '支付创建失败')}")
            return jsonify({
                'success': False,
                'error': response_data.get('msg', '支付创建失败') + ' - UIP:'+str(client_ip)
            }), 500

    except Exception as e:
        print(f"创建支付订单错误: {str(e)}")
        import traceback
        traceback.print_exc()  # 打印完整的错误堆栈
        return jsonify({'error': f'服务器内部错误: {str(e)}'}), 500

# 支付回调接口
@app.route('/api/payment/callback', methods=['POST', 'GET'])
def payment_callback():
    try:
        from get_epay_sign import verify_callback
        
        # 获取回调参数
        if request.method == 'POST':
            params = request.form.to_dict()
        else:
            params = request.args.to_dict()

        # 验证回调签名
        if not verify_callback(params, MERCHANT_KEY):
            print(f"回调签名验证失败: {params}")
            return 'FAIL'

        # 获取订单信息
        order_id = params.get('out_trade_no')
        trade_no = params.get('trade_no')  # 支付平台交易号
        trade_status = params.get('trade_status', 'TRADE_SUCCESS')  # 交易状态
        total_amount = params.get('total_amount')  # 订单金额

        if trade_status == 'TRADE_SUCCESS':
            # 更新订单状态为已支付
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE orders SET status = 'paid', updated_at = datetime('now', 'localtime')
                WHERE order_id = ?
            ''', (order_id,))            
            conn.commit()
            
            # 检查是否更新成功
            if cursor.rowcount > 0:
                print(f"订单 {order_id} 支付成功，交易号: {trade_no}, 金额: {total_amount}")
                PAY_TMP_LIST.pop(order_id, None) # 移除临时缓存
            else:
                print(f"订单 {order_id} 不存在，无法更新状态")
                

            #获取订单类型和用户名
            cursor.execute('SELECT amount, username,buy_type, fat_count FROM orders WHERE order_id = ?', (order_id,))
            result = cursor.fetchone()
            if result:
                amount = result["amount"]
                username = result["username"]
                buy_type = result["buy_type"]
                fat_count = result["fat_count"]
                # 根据订单类型和用户名进行其他操作
                if buy_type == 'sub':
                    # 更新用户续费时间
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    cursor.execute('''
                            UPDATE orders SET updated_at = datetime('now', 'localtime')
                            WHERE order_id = ?
                        ''', (order_id,))
                    conn.commit()
                    print(f"为用户 {username} 处理订阅续费，订单号: {order_id}")
                    order = {"id": order_id, "type": "sub", "username": username}
                    order_queue.append(order)
                    order_status[order_id] = {"status": "queued", "result": None, "queued_count": str(len(order_queue)), "order_amount": round(amount, 2)}
                    save_orders()
                    print(f"已创建 sub 订单 {order_id} 用户名:{username}")
                    # ! 接下来交给worker处理，由插件发送消息进行动态更新
                elif buy_type == 'fat':
                    cursor.execute('''
                            UPDATE orders SET updated_at = datetime('now', 'localtime')
                            WHERE order_id = ?
                    ''', (order_id,))
                    conn.commit()
                    #获取购买的fat数量
                    cursor.execute('SELECT fat_count FROM orders WHERE order_id = ?', (order_id,))
                    fat_result = cursor.fetchone()
                    if fat_result:
                        fat_count = fat_result["fat_count"]
                    print(f"为用户 {username} 处理 FAT 充值，数量: {fat_count}，订单号: {order_id}")
                    # 使用原始订单号而不是支付平台交易号，保持一致性
                    order = {"id": order_id, "type": "fat", "username": username, "amount": fat_count}
                    order_queue.append(order)
                    order_status[order_id] = {"status": "queued", "result": None, "queued_count": str(len(order_queue)), "order_amount": round(amount, 2)}
                    save_orders()
                    print(f"FAT 充值结果: {result}")
                    # ! 接下来交给worker处理，由插件发送消息进行动态更新
            return 'success'
        else:
            # 如果不是成功状态，也更新数据库（例如更新为已取消等状态）
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE orders SET status = ?, updated_at = datetime('now', 'localtime')
                WHERE order_id = ?
            ''', (trade_status.lower(), order_id))
            conn.commit()
            conn.close()
            
            print(f"订单 {order_id} 交易状态: {trade_status}")
            return 'success'  # 即使是失败状态，也返回成功以避免重复回调

    except Exception as e:
        print(f"回调处理错误: {str(e)}")
        return 'FAIL'

# 查询订单状态接口
@app.route('/api/order-status/<order_id>', methods=['GET'])
def get_order_status(order_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT status, created_at, pay_url, payment_method FROM orders WHERE order_id = ?', (order_id,))
        result = cursor.fetchone()
        if result:
            pay_status = result['status']
            created_at = result['created_at']
            pay_url = result['pay_url']
            payment_method = result['payment_method']
        else:
            pay_status = 'unknown'
            created_at = None
            pay_url = None
            payment_method = None
        conn.close()
        
        # 计算支付剩余时间（5分钟支付期限）
        remaining_time = None
        if created_at and pay_status == 'pending':
            
            # 解析创建时间 - 注意：根据日志显示，数据库中存储的时间可能是UTC时间
            # 无论数据库中存储的是UTC还是本地时间，我们都使用相同基准进行比较
            try:
                # 尝试标准的SQLite时间格式
                if ' ' in created_at and len(created_at) >= 19:
                    order_time = datetime.strptime(created_at[:19], '%Y-%m-%d %H:%M:%S')
                else:
                    # 如果格式不符合预期，不立即标记为过期
                    print(f"无法解析时间格式: {created_at}，订单ID: {order_id}")
                    order_time = datetime.now()
            except ValueError as e:
                print(f"时间解析错误: {e}，原始时间: {created_at}，订单ID: {order_id}")
                # 如果解析失败，不立即标记为过期
                order_time = datetime.now()
            
            #通过内存中的订单队列获取创建订单的时间
            if order_id in PAY_TMP_LIST:
                order_time = PAY_TMP_LIST[order_id]["created_at"]
            else:
                return jsonify({"status": "unknown", "msg": "订单不存在", "remaining_time": None, "pay_url": pay_url, "payment_method": payment_method})
            remaining_time = 300 - (datetime.now() - order_time).total_seconds()
            
            # 添加详细日志
            print(f"订单 {order_id} - 创建时间: {order_time}, 当前时间: {str(datetime.now())}, 剩余时间: {remaining_time}秒, 状态: {pay_status}，已过去: {str(remaining_time + 300)}秒")
            
            # 如果超过5分钟且仍为pending状态，则更新为已取消
            if remaining_time <= 0 and pay_status == 'pending':
                # 检查订单是否是刚创建的（时间差远超5分钟可能是时区问题）
                # 如果时间差超过5分钟很多（比如超过10分钟），可能表示时区配置问题
                
                print(f"订单 {order_id} 已超过5分钟未支付，状态更新为已取消")
                # 更新数据库状态为已取消
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE orders SET status = 'cancelled', updated_at = datetime('now', 'localtime')
                    WHERE order_id = ? AND status = 'pending'
                ''', (order_id,))
                conn.commit()
                conn.close()
                pay_status = 'cancelled'  # 更新本地状态
                remaining_time = 0

        status = order_status.get(order_id)
        if not status:
            # 如果在内存队列中没找到，从数据库获取订单状态
            # 这种情况通常是订单已经不在队列中（比如已支付），但仍需要返回其状态
            if pay_status == 'unknown':
                # 如果数据库中也没有该订单，才返回"订单不存在"
                return jsonify({
                    "code": 1, 
                    "msg": "订单不存在",
                    "remaining_time": remaining_time,
                    "pay_url": pay_url  # 添加支付链接
                })
            else:
                # 如果数据库中有该订单，则返回数据库中的状态
                queued_count = sum(1 for o in order_queue if "id" in o or o.get("type") == "sync")
                return jsonify({
                    "code": 0,
                    "status": pay_status,  # 使用数据库中的状态
                    "result": 'status is not found in memory queue',
                    "pay_status": pay_status,
                    "queued_count": str(queued_count),
                    "remaining_time": remaining_time,  # 添加剩余时间
                    "pay_url": pay_url,
                    "payment_method": payment_method
                })
        else:
            # 订单在内存队列中，使用原有逻辑
            queued_count = sum(1 for o in order_queue if "id" in o or o.get("type") == "sync")

            # 如果订单还在队列中，动态计算前方数量
            if status["status"] == "queued":
                # 只统计有 'id' 的订单
                queued_orders = [o for o in order_queue if "id" in o]
                index = next((i for i, o in enumerate(queued_orders) if o["id"] == order_id), None)
                status["queued_count"] = str(index if index is not None else 0)
            
            return jsonify({
                "code": 0,
                "status": status["status"],
                "result": status,
                "pay_status": pay_status,
                "queued_count": str(queued_count),
                "remaining_time": remaining_time,  # 添加剩余时间
                "pay_url": pay_url,  # 添加支付链接
                "debug":"status is found in memory queue ",
                "payment_method": payment_method
            })

    except Exception as e:
        print(f"查询订单状态错误: {str(e)}")
        return jsonify({'error': '服务器内部错误', 'remaining_time': None, 'pay_url': None}), 500

# 根据浏览器指纹查询订单
@app.route('/api/orders-by-fingerprint', methods=['POST'])
def get_orders_by_fingerprint():
    try:
        data = request.json
        browser_fingerprint = data.get('browser_fingerprint')
        
        if not browser_fingerprint:
            return jsonify({'error': '缺少浏览器指纹参数'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT order_id, status, amount, pay_url,
                   datetime(created_at, 'localtime') as created_at
            FROM orders 
            WHERE browser_fingerprint = ? 
            ORDER BY created_at DESC
        ''', (browser_fingerprint,))
        results = cursor.fetchall()
        conn.close()
        
        orders = [dict(row) for row in results]
        
        if orders:
            # 返回最新的订单
            latest_order = orders[0]
            return jsonify({
                'has_orders': True,
                'order': latest_order,
                'all_orders': orders
            })
        else:
            return jsonify({
                'has_orders': False,
                'order': None,
                'all_orders': []
            })

    except Exception as e:
        print(f"查询浏览器指纹订单错误: {str(e)}")
        return jsonify({'error': '服务器内部错误'}), 500

# ===================== 管理面板功能 =====================

def hash_password(password):
    """对密码进行SHA256哈希"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_admin_password(provided_password):
    """验证管理员密码"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT admin_password_hash FROM settings LIMIT 1")
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        # 如果没有设置密码，则使用默认密码'password'
        default_hash = hash_password('password')
        return provided_password == default_hash
    
    stored_hash = result['admin_password_hash']
    provided_hash = hash_password(provided_password)
    return provided_hash == stored_hash

@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    """管理员登录接口"""
    try:
        data = request.json
        password = data.get('password')
        
        if not password:
            return jsonify({'success': False, 'message': '密码不能为空'}), 400
        
        if verify_admin_password(password):
            # 登录成功，返回一个简单的token（基于时间戳和密码哈希）
            import time
            token_data = f"{password}{int(time.time())}"
            token = hashlib.sha256(token_data.encode()).hexdigest()
            return jsonify({'success': True, 'token': token, 'message': '登录成功'})
        else:
            return jsonify({'success': False, 'message': '密码错误'}), 401
    
    except Exception as e:
        print(f"登录验证错误: {str(e)}")
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500

def require_admin_token(f):
    """装饰器：验证管理员token"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'success': False, 'message': '缺少认证token'}), 401
        
        # 这里可以添加更复杂的token验证逻辑
        # 为简单起见，我们只验证token格式
        if len(token) != 64:  # SHA256哈希长度
            return jsonify({'success': False, 'message': '无效的认证token'}), 401
        
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/admin/settings', methods=['GET'])
@require_admin_token
def get_settings():
    """获取系统设置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT theme, fat_price, sub_price, sale_enabled, sale_sub_price, sale_fat_required, sale_start_date, sale_end_date FROM settings LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return jsonify({
                'success': True,
                'settings': {
                    'theme': result['theme'],
                    'fat_price': result['fat_price'],
                    'sub_price': result['sub_price'],
                    'sale_enabled': result['sale_enabled'],
                    'sale_sub_price': result['sale_sub_price'],
                    'sale_fat_required': result['sale_fat_required'],
                    'sale_start_date': result['sale_start_date'],
                    'sale_end_date': result['sale_end_date']
                }
            })
        else:
            return jsonify({'success': False, 'message': '未找到设置'}), 404
    
    except Exception as e:
        print(f"获取设置错误: {str(e)}")
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500

@app.route('/api/admin/settings', methods=['POST'])
@require_admin_token
def update_settings():
    """更新系统设置"""
    try:
        data = request.json
        theme = data.get('theme')
        fat_price = data.get('fat_price')
        sub_price = data.get('sub_price')
        new_password = data.get('new_password')
        sale_enabled = data.get('sale_enabled')
        sale_sub_price = data.get('sale_sub_price')
        sale_fat_required = data.get('sale_fat_required')
        sale_start_date = data.get('sale_start_date')
        sale_end_date = data.get('sale_end_date')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if theme is not None:
            cursor.execute("UPDATE settings SET theme = ? WHERE id = 1", (theme,))
        if fat_price is not None:
            cursor.execute("UPDATE settings SET fat_price = ? WHERE id = 1", (float(fat_price),))
        if sub_price is not None:
            cursor.execute("UPDATE settings SET sub_price = ? WHERE id = 1", (float(sub_price),))
        
        # 如果提供了新密码，则更新密码
        if new_password:
            new_password_hash = hash_password(new_password)
            cursor.execute("UPDATE settings SET admin_password_hash = ? WHERE id = 1", (new_password_hash,))
        
        # 更新优惠设置
        if sale_enabled is not None:
            cursor.execute("UPDATE settings SET sale_enabled = ? WHERE id = 1", (int(sale_enabled),))
        if sale_sub_price is not None:
            cursor.execute("UPDATE settings SET sale_sub_price = ? WHERE id = 1", (float(sale_sub_price),))
        if sale_fat_required is not None:
            cursor.execute("UPDATE settings SET sale_fat_required = ? WHERE id = 1", (int(sale_fat_required),))
        if sale_start_date is not None:
            cursor.execute("UPDATE settings SET sale_start_date = ? WHERE id = 1", (sale_start_date,))
        if sale_end_date is not None:
            cursor.execute("UPDATE settings SET sale_end_date = ? WHERE id = 1", (sale_end_date,))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '设置更新成功'})
    
    except Exception as e:
        print(f"更新设置错误: {str(e)}")
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500

# 检查当前是否在优惠期间内
def is_sale_active():
    """检查当前是否在优惠期间内"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT sale_enabled, sale_start_date, sale_end_date FROM settings LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        if result:
            sale_enabled = result['sale_enabled']
            start_date_str = result['sale_start_date']
            end_date_str = result['sale_end_date']
            
            if not sale_enabled or not start_date_str or not end_date_str:
                return False
                
            import re
            
            # 处理ISO格式的日期时间字符串，移除可能的时区信息并转换为naive datetime
            def parse_iso_datetime(dt_str):
                # 移除时区标识符 'Z' 或 '+00:00' 等
                dt_str = re.sub(r'[Zz]|(?:\+|-)\d{2}:\d{2}$', '', dt_str)
                # 移除可能的微秒部分以避免解析错误
                if '.' in dt_str:
                    dt_str = dt_str.split('.')[0]
                # 将 'T' 替换为空格以符合 fromisoformat 格式
                dt_str = dt_str.replace('T', ' ')
                # 解析日期时间
                return datetime.fromisoformat(dt_str)
            
            start_date = parse_iso_datetime(start_date_str)
            end_date = parse_iso_datetime(end_date_str)
            now = datetime.now()
            
            return start_date <= now <= end_date
        else:
            return False
    except Exception as e:
        print(f"检查优惠状态错误: {str(e)}")
        return False

# 前端获取当前设置的API
@app.route('/api/theme-settings', methods=['GET'])
def get_theme_settings():
    """前端获取当前主题设置"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT theme, fat_price, sub_price, sale_enabled, sale_sub_price, sale_fat_required, sale_start_date, sale_end_date FROM settings LIMIT 1")
        result = cursor.fetchone()
        conn.close()
        
        is_active = is_sale_active()
        
        if result:
            return jsonify({
                'theme': result['theme'],
                'fat_price': result['fat_price'],
                'sub_price': result['sub_price'],
                'sale_enabled': result['sale_enabled'],
                'sale_sub_price': result['sale_sub_price'],
                'sale_fat_required': result['sale_fat_required'],
                'sale_start_date': result['sale_start_date'],
                'sale_end_date': result['sale_end_date'],
                'is_sale_active': is_active
            })
        else:
            # 如果没有设置，则返回默认值
            return jsonify({
                'theme': 'normal',
                'fat_price': 0.75,
                'sub_price': 198.0,
                'sale_enabled': 0,
                'sale_sub_price': 0.0,
                'sale_fat_required': 288,
                'sale_start_date': None,
                'sale_end_date': None,
                'is_sale_active': False
            })
    
    except Exception as e:
        print(f"获取主题设置错误: {str(e)}")
        return jsonify({
            'theme': 'normal',
            'fat_price': 0.75,
            'sub_price': 198.0,
            'sale_enabled': 0,
            'sale_sub_price': 0.0,
            'sale_fat_required': 288,
            'sale_start_date': None,
            'sale_end_date': None,
            'is_sale_active': False
        }), 500
def mask_string(s: str) -> str:
    if len(s) <= 2:
        return s[0] + '*' * (len(s) - 2)
    return s[0] + '*' * (len(s) - 2) + s[-1]

@app.route('/api/fats', methods=['GET'])
def get_fats():
    return jsonify({'fats': get_all_paid_fat_orders(), "most_user": mask_string(get_most_user()), "most_fat": mask_string(get_most_fat_user()), "most_fat_fats": get_most_fat_total(), "most_user_order_count": get_most_user_order_()})
@app.route('/api/get_fat', methods=['GET', 'POST'])
def get_fat():#
    return jsonify({'last_sync_balance': current_fats, "last_sync_time": last_sync_time})
# @app.route("/api/test", methods=["GET"])
# def test():#
#     return "Server is running.Pull by CTCAKE at 2026/1/26."
# ===================== 启动 =====================
if __name__ == '__main__':
    # 启动事件循环线程
    loop_thread = threading.Thread(target=run_event_loop, daemon=True)
    loop_thread.start()
    print("事件循环线程已启动")

    # 等待事件循环初始化完成
    import time
    time.sleep(0.5)  # 给事件循环一些时间初始化

    # 将全局事件循环传递给 plugin 实例
    plugin.loop = loop

    # 启动 WebSocket 服务器
    asyncio.run_coroutine_threadsafe(plugin.start_server(on_message=on_message), loop)
    print("WebSocket 服务器已启动")

    # 启动订单处理线程（在事件循环启动后）
    threading.Thread(target=order_worker, daemon=True).start()
    print("订单处理线程已启动")
#
    # 启动 Flask 服务器
    app.run(host='0.0.0.0', port=5001, debug=False)
