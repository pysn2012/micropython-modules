# 魔豆网页遥控小车（放设备根目录，main.py 自动启动）
#
# 端口 80 起 HTTP 服务（独立线程，不阻塞 REPL）：
#   GET /          -> 遥控页面（手机/电脑浏览器均可）
#   GET /cmd?a=..  -> 控制指令
#       a=wake   唤醒底座（AT+Pon）
#       a=fwd    前进    a=back 后退    a=left 左转    a=right 右转
#       p=动力(1-100) 可选，默认 60
# 页面按住按钮连续发帧（250ms 间隔），松手停发 -> 运动帧 800ms 超时自动停车
#
# 上传方式：car_ctrl.py / car_web.py / main.py 三个文件放设备根目录

import socket
import _thread
import time

import car_ctrl

PAGE = (
    b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    b"<!DOCTYPE html><html><head><meta charset=utf-8>"
    b"<meta name=viewport content='width=device-width,initial-scale=1,user-scalable=no'>"
    b"<title>魔豆遥控</title><style>"
    b"body{font-family:sans-serif;text-align:center;background:#222;color:#eee}"
    b"h2{margin:16px}button{width:130px;height:64px;font-size:22px;border:0;border-radius:12px;"
    b"background:#4a76d0;color:#fff;margin:8px;touch-action:none;user-select:none}"
    b"button.stop{background:#c0392b;width:280px}"
    b"input{width:260px;height:34px;margin:12px}"
    b".grid{display:inline-grid;grid-template-columns:auto auto}"
    b"</style></head><body>"
    b"<h2>魔豆小车遥控</h2>"
    b"<div class=grid>"
    b"<button id=f>前进</button><button id=b>后退</button>"
    b"<button id=l>左转</button><button id=r>右转</button>"
    b"</div><br>"
    b"<button id=s class=stop>停止（松手即停）</button><br>"
    b"<label>动力 </label><input type=range id=p min=10 max=100 value=60>"
    b"<script>"
    b"var t=null;"
    b"function send(a){fetch('/cmd?a='+a+'&p='+document.getElementById('p').value);}"
    b"function hold(id,a){var el=document.getElementById(id);"
    b"el.addEventListener('pointerdown',function(e){e.preventDefault();clearInterval(t);"
    b"send(a);t=setInterval(function(){send(a);},250);});"
    b"['pointerup','pointercancel','pointerleave'].forEach(function(ev){"
    b"el.addEventListener(ev,function(){clearInterval(t);});});}"
    b"hold('f','fwd');hold('b','back');hold('l','left');hold('r','right');"
    b"document.getElementById('s').addEventListener('pointerdown',function(){clearInterval(t);});"
    b"window.addEventListener('load',function(){send('wake');});"
    b"</script></body></html>"
)

OK_RESP = b"HTTP/1.0 200 OK\r\nConnection: close\r\n\r\nOK"


def _exec_cmd(a, p):
    """一条控制指令映射到 car_ctrl 调用。p 为动力 1-100。"""
    if a == "wake":
        car_ctrl.wake()
    elif a == "fwd":
        car_ctrl.forward(400, p)
    elif a == "back":
        car_ctrl.backward(400, p)
    elif a == "left":
        car_ctrl.spin_left(400, p)
    elif a == "right":
        car_ctrl.spin_right(400, p)


def _handle_conn(c):
    # 读请求行：GET /cmd?a=fwd&p=60 HTTP/1.1
    line = c.readline()
    if not line:
        return
    parts = line.decode().split(" ")
    path = parts[1] if len(parts) > 1 else "/"
    # 丢弃剩余请求头（直到空行）
    while True:
        h = c.readline()
        if not h or h == b"\r\n":
            break
    if path.startswith("/cmd"):
        a = "wake"
        p = 60
        for kv in path.split("?")[-1].split("&"):
            if kv.startswith("a="):
                a = kv[2:]
            elif kv.startswith("p="):
                try:
                    p = max(1, min(100, int(kv[2:])))
                except ValueError:
                    pass
        try:
            _exec_cmd(a, p)
            c.write(OK_RESP)
        except Exception as e:
            c.write(b"HTTP/1.0 500 ERR\r\n\r\nERR")
            print("[carweb] cmd %s err: %r" % (a, e))
    else:
        c.write(PAGE)


def _server():
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(3)
    print("[carweb] server ready")
    while True:
        c, a = s.accept()
        try:
            _handle_conn(c)
        except Exception as e:
            print("[carweb] conn err: %r" % e)
        try:
            time.sleep_ms(50)  # 让最后一帧 write 从缓冲完整发出
        except Exception:
            pass
        c.close()


def start():
    """启动网页遥控（独立线程，立即返回，REPL 不受影响）。"""
    _thread.start_new_thread(_server, ())


print("[car] car_web loaded: browser open http://<modou-ip>/")
