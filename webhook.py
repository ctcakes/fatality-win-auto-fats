from flask import Flask, request
import subprocess
import hmac
import hashlib

app = Flask(__name__)

SECRET = b"ctcake-shop!@#$%^&*()"   # 和 GitHub Webhook 里一致

@app.route("/webhook", methods=["POST"])
def webhook():
    event = request.headers.get("X-GitHub-Event")

    # 1️⃣ GitHub ping，直接放行
    if event == "ping":
        return "pong", 200

    # 2️⃣ 校验签名（只对 push 做）
    sig = request.headers.get("X-Hub-Signature-256")
    if not sig:
        return "no signature", 403

    mac = hmac.new(SECRET, request.data, hashlib.sha256)
    if sig != "sha256=" + mac.hexdigest():
        return "bad signature", 403

    #只处理 server 分支的 push
    if event == "push":
        data = request.json or {}
        if data.get("ref") == "refs/heads/server":
            subprocess.Popen(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", "C:\\Users\\Administrator\\Desktop\\Auto-Fatal-test\\ctcake-shop-back-end\\deploy.ps1"],
                creationflags=0x08000000
            )
            subprocess.run(["nssm", "restart", "ctcake-flask"])
        else:
            print("not server")
    else:
        print("not push")

    return "ok", 200


app.run(host="0.0.0.0", port=5007)
