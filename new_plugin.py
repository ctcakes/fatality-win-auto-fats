import asyncio
import websockets

class Plugin:
    def __init__(self):
        self.host = 'localhost'
        self.port = 5000
        self.websocket = None
        self.on_message_callback = None
        self.server = None
        self.loop = None

    def on_message(self, message):
        """默认的消息处理函数"""
        print("收到消息:", message)

    async def handle_client(self, websocket):
        """处理客户端连接"""
        self.websocket = websocket
        client_addr = websocket.remote_address
        print(f"连接成功，来自: {client_addr}")

        try:
            async for message in websocket:
                print(f"收到消息: {message}")
                if self.on_message_callback:
                    self.on_message_callback(message)
        except websockets.exceptions.ConnectionClosed:
            print("客户端断开连接")
        except Exception as e:
            print(f"连接异常: {e}")
        finally:
            self.websocket = None

    async def start_server(self, on_message=None):
        """启动 WebSocket 服务器"""
        if on_message:
            self.on_message_callback = on_message
        else:
            self.on_message_callback = self.on_message

        self.server = await websockets.serve(
            self.handle_client,
            self.host,
            self.port
        )
        print(f"WebSocket 服务器已启动，监听 ws://{self.host}:{self.port}，等待连接...")

    def send_message(self, message):
        if not self.websocket or not self.loop:
            print("没有客户端或事件循环")
            return False

        try:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send(message),
                self.loop
            )
            return True
        except Exception as e:
            print("发送消息异常:", e)
            return False


    async def send_message_async(self, message):
        """异步发送消息给客户端"""
        if self.websocket:
            try:
                await self.websocket.send(message)
                return True
            except Exception as e:
                print("发送消息异常:", e)
                return False
        else:
            print("没有客户端连接")
            return False

    def close(self):
        """关闭服务器"""
        if self.server:
            self.server.close()
        print("服务器已关闭")
