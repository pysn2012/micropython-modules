# telnet_repl.py —— 魔豆无线 REPL 兜底方案：裸 TCP 直连 REPL（无 WebREPL 协议、无密码、无单连接握手坑）
# ------------------------------------------------------------------
# 原理：把收到的 socket 通过 uos.dupterm 注册为第二个 REPL 终端，
#       PC 端用任何 TCP 客户端（PuTTY telnet / nc / 随附 pc_repl.py）连接即可交互。
#       与 WebREPL 互不冲突（端口不同），与串口 REPL 也共存（双终端同时有效）。
#
# 设备端：REPL 运行  import telnet_repl   （或加进 boot.py 开机自启）
# PC 端 ：python pc_repl.py 192.168.31.195 8267
#         （或 PuTTY -> Connection type 选 Raw/Telnet -> 192.168.31.195:8267）
# ------------------------------------------------------------------

import socket
import uos
import _thread
import time

PORT = 8267


def _serve(s):
    while True:
        conn, addr = s.accept()
        print("[telnet] client connected:", addr)
        uos.dupterm(conn, 1)  # 注册为 1 号终端（0 号是串口）
        conn.write(b"\r\n[telnet REPL connected]\r\n")
        # 探测断线：写空包触发 send 系统调用，对端死掉时抛 OSError
        dead = False
        while not dead:
            time.sleep(2)
            try:
                conn.write(b"")
            except OSError:
                dead = True
        uos.dupterm(None, 1)
        conn.close()
        print("[telnet] client disconnected")


def start(port=PORT):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", port))
    s.listen(1)
    _thread.start_new_thread(_serve, (s,))
    print("[telnet] REPL server ready on tcp://%s:%d" % (wifi_ip(), port))
    return s


def wifi_ip():
    import network
    wlan = network.WLAN(network.STA_IF)
    return wlan.ifconfig()[0] if wlan.isconnected() else "0.0.0.0"


print("[telnet] ready: telnet_repl.start()  —— PC 端用 pc_repl.py 或 PuTTY(Raw) 连 8267")
