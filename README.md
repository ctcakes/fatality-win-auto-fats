# fatality-win-auto-fats
fats 自动发货 for fatality.win
# Pilot1337 操你妈
# Pilot1337 操你妈
# Pilot1337 操你妈
# 用法
  ## 必须
   - Winserver 建议10+
   - FA账号
   - 梯子(如果你觉得服务器网络可以访问fatality.win可以不用)
   - 注意：FA账号必须有订阅 否则无法转账FAT
  ## 安装
   - 下载仓库源码，进入文件夹
   - 安装Python 推荐3.12.x，其他版本有可能出现不可预知的错误（亲身经历。。）
     - 安装PIP依赖 不会的可以问AI，你在目录执行python main.py 把出现的报错一行不落复制给AI，问他 \[\(报错\) 这个报错要装什么依赖，给出完整pip命令\]
     - 安装完一个再执行python main.py，然后重复上面步骤，直到跑起来为止
   - 安装Chrome插件(Chrome-管理扩展程序-右上角开发者模式打开-加载未打包的扩展程序-找到此目录里面的new_plugin_chrome文件夹-确定
  ## 启动
  ### 后端
   - 下载好Chrome，登录上你的FA账号
   - ⚠️然后修改main.py,refund.py,get_epay_sign.py里面设置好你的易支付商户ID和秘钥,本系统只支持易支付的V1接口。
   - 然后在后端文件夹执行
  ```bash
  python main.py
  ```
   - 然后启动/重启 Chrome插件，让他重新尝试连接
   - 如果连接成功，Python端会显示"x.x.x.x:xxxx 连接"
   - 然后将Winserver的Chrome点成焦点\[必须\]
   - 放那挂机 等订单即可
  ### 前端
   - ⚠️前端可以不和后端在同一台服务器搭建，前端建议使用Linux服务器
   - Winserver建站性能很差
   - 如果要用Winserver，建议安装宝塔面板操作。
   - 手动部署方法在下面
  ### 宝塔面板部署
   - 打开宝塔面板（Winserver/Linux都可）
   - 安装NGINX三件套（正常情况第一次安装就会弹出来）
   - 如果没弹出来就点击软件商店-运行环境，安装：NGINX任意版本
   - 左边侧边栏点击网站
   - Node项目
   - 添加项目
   - 如果你没安装Nodejs，会弹出一个框让你安装。
     - 点击右上角更新版本列表
     - 安装v22.22.0
     - 等一会让他安装完
   - 继续添加项目。
     - 项目目录，点击右边的文件夹图标选择你刚才放前端的路径
     - 名称，自己填
     - 启动选项 如果你选择对了目录就会有选项，我们选择最下面的preview
     - <img width="731" height="522" alt="image" src="https://github.com/user-attachments/assets/3eed7a17-1e77-4fc3-ae9b-1aee86e35d02" />
     - node版本自动选择
     - 包管理器，如果你不知道这是什么选npm就好
     - 点击确定，然后等一会就创建好了
   - 过一会项目创建好了，点击设置
      - 项目端口4173
      - 侧边栏点击域名管理，添加你解析到服务器的域名
      - 然后打开外网映射
      - 然后是SSL，一定要配置
         - 点击免费证书，点击申请
         - 验证方式 文件验证即可
         - 点击确定，自动申请，申请成功会自动配置好
       - 此时如果项目正常运行中，就可以访问测试了
      - <img width="818" height="735" alt="image" src="https://github.com/user-attachments/assets/e2ab2c02-5c65-48cd-95e9-35c2879e4209" />
  ### 手动部署
  打开bash/cmd到前端目录
  ```bash
  npm i
  ```
  等待执行完成
  \[建议在自己电脑上Build，打包完了把dist目录传服务器的前端文件夹里面就行\]
  ```bash
  npm run build
  ```
  打包完成后
  在vite.config.ts里面设置好你的后端IP和端口(文件第15行)
  上面的一个apihvh就不用管了，旧的用不到
  运行
  ```bash
  npm run preview
```
然后在Nginx设置好绑定域名,就可以访问了
# 一些话
 - Pilot1337 操你妈
 - Pilot1337 操你妈
 - Pilot1337 操你妈
