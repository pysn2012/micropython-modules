# 魔豆网页遥控（放设备根目录）
#
#   import car_web
#   car_web.remote()
#
#   浏览器开 http://<IP>/：
#     方向按钮    按住连发（250ms 间隔），松手停发 -> 运动帧 800ms 超时自动停车
#     停止        急停 + 灯光复位
#     前灯/尾灯/闪烁   灯光效果帧
#     动力滑条    10-100，方向按钮共用
#     页面加载时自动发一次 wake（AT+Pon 唤醒底座）
#   Ctrl-C 退出、回到 REPL（退出时自动发急停帧）
#
# 实现说明：单任务轮询服务器（非阻塞 accept + 50ms 睡眠），
# 不用 _thread —— 之前线程版一启动 WebREPL 就断线（Thonny/浏览器均 EOF），
# 单任务版 REPL 与 HTTP 共存于主任务，睡眠间隙照常服务 WebREPL。

import socket
import time

import car_ctrl

OK_RESP = b"HTTP/1.0 200 OK\r\nConnection: close\r\n\r\nOK"
ERR_RESP = b"HTTP/1.0 500 ERR\r\n\r\nERR"

PAGE_BODY = (
    "<!DOCTYPE html><html><head><meta charset=utf-8>"
    "<meta name=viewport content='width=device-width,initial-scale=1,user-scalable=no'>"
    "<title>魔豆遥控</title><style>"
    "body{font-family:sans-serif;text-align:center;background:#1c2333;color:#eee;"
    "margin:0;padding:12px;-webkit-user-select:none;user-select:none}"
    "h2{margin:10px 0 14px}"
    "button{border:0;border-radius:14px;color:#fff;margin:6px;touch-action:none;"
    "font-size:20px;background:#4a76d0;box-shadow:0 4px 0 #2c4a8c;"
    "transition:background .05s,transform .05s,box-shadow .05s}"
    "button.pressed{background:#ffb300 !important;box-shadow:0 1px 0 #7a5500;"
    "transform:translateY(3px)}"
    ".pad{display:inline-block}"
    ".pad button{width:140px;height:62px}"
    ".row{display:flex;justify-content:center}"
    "button.stop{background:#c0392b;box-shadow:0 4px 0 #7d1f14;width:300px;height:52px}"
    ".lights button{background:#2e8b57;box-shadow:0 4px 0 #1a5233;"
    "width:100px;height:48px;font-size:18px}"
    "input[type=range]{width:280px;height:34px;margin:10px;vertical-align:middle}"
    "label{color:#9fb0d0}"
    "</style></head><body>"
    "<h2>魔豆小车遥控</h2>"
    "<div class=pad>"
    "<div class=row><button id=f>&#9650; 前进</button></div>"
    "<div class=row><button id=l>&#9664; 左转</button><button id=r>右转 &#9654;</button></div>"
    "<div class=row><button id=b>&#9660; 后退</button></div>"
    "</div><br>"
    "<button id=s class=stop>停 止</button><br>"
    "<div class=lights>"
    "<button id=front>前灯</button><button id=tail>尾灯</button><button id=flash>闪烁</button>"
    "</div><br>"
    "<label>动力 </label><input type=range id=p min=10 max=100 value=60>"
    "<script>"
    "function send(a){fetch('/cmd?a='+a+'&p='+document.getElementById('p').value);}"
    "function press(el,on){el.classList[on?'add':'remove']('pressed');}"
    "function hold(id,a){var el=document.getElementById(id);var t=null;"
    "el.addEventListener('pointerdown',function(e){e.preventDefault();"
    "press(el,true);clearInterval(t);send(a);"
    "t=setInterval(function(){send(a);},250);});"
    "['pointerup','pointercancel','pointerleave'].forEach(function(ev){"
    "el.addEventListener(ev,function(){press(el,false);clearInterval(t);});});}"
    "function tap(id,a){var el=document.getElementById(id);"
    "el.addEventListener('pointerdown',function(e){e.preventDefault();"
    "press(el,true);send(a);});"
    "['pointerup','pointercancel','pointerleave'].forEach(function(ev){"
    "el.addEventListener(ev,function(){press(el,false);});});}"
    "hold('f','fwd');hold('b','back');hold('l','left');hold('r','right');"
    "tap('s','stop');tap('front','front');tap('tail','tail');tap('flash','flash');"
    "window.addEventListener('load',function(){send('wake');});"
    "</script></body></html>"
)

PAGE = (
    b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    + PAGE_BODY.encode("utf-8")
)


def _exec_cmd(a, p):
    """一条控制指令映射到 car_ctrl 调用。p 为动力 10-100（灯光指令忽略）。"""
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
    elif a == "stop":
        car_ctrl.stop()
    elif a == "front":
        car_ctrl.front_light()
    elif a == "tail":
        car_ctrl.tail_light()
    elif a == "flash":
        car_ctrl.flash_light()


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
                    p = max(10, min(100, int(kv[2:])))
                except ValueError:
                    pass
        try:
            _exec_cmd(a, p)
            c.write(OK_RESP)
        except Exception as e:
            c.write(ERR_RESP)
            print("[carweb] cmd %s err: %r" % (a, e))
    else:
        c.write(PAGE)


def remote():
    """一键遥控模式（底座连接时用）。
    单任务轮询：非阻塞 accept + 50ms 睡眠，Ctrl-C 随时退出回 REPL。"""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 80))
    s.listen(2)
    s.setblocking(False)  # 非阻塞 accept：无连接时立刻返回，绝不卡住 REPL
    print("[carweb] remote mode: open http://<modou-ip>/ ; Ctrl-C to exit")
    try:
        while True:
            try:
                c, addr = s.accept()
            except OSError:
                time.sleep_ms(50)  # 睡眠间隙照常服务 WebREPL / 响应 Ctrl-C
                continue
            try:
                c.settimeout(1)
                _handle_conn(c)
            except Exception as e:
                print("[carweb] conn err: %r" % e)
            try:
                c.close()
            except Exception:
                pass
    except KeyboardInterrupt:
        print("\n[carweb] remote exited")
    finally:
        try:
            car_ctrl.stop()  # 退出兜底急停
        except Exception:
            pass
        s.close()


print("[car] car_web loaded: web remote = car_web.remote() (open http://<modou-ip>/)")
