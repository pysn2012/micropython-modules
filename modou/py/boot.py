# Modou 设备端 boot.py（拷到设备根目录，开机自动运行）
# ------------------------------------------------------------------
# 流程：
#   1. WebREPL 密码初始化（webrepl_cfg.py 不存在时自动生成，密码见下方配置）
#   2. 连接 Wi-Fi（STA 模式，SSID/PASSWORD 见下方配置）
#   3. 启动 WebREPL（Thonny/浏览器 ws://<IP>:8266 在线编程）
#   4. 回滚保护自检：OTA 升级后的新固件处于 pending_verify，
#      能连上 Wi-Fi 说明固件基本可用，自动 ota.mark_valid() 固化；
#      若连不上 Wi-Fi 就不确认，手动复位会回退旧固件（回滚保护生效）
#
# 注意：
#   - boot.py 里 SSID/PASSWORD 改成你自己的
#   - WebREPL 密码建议修改（WebREPL_PASSWORD），长度 4~9 字符
# ------------------------------------------------------------------

import network
import time
import os
import webrepl

try:
    import ota
    _HAS_OTA = True
except ImportError:
    _HAS_OTA = False

# ====== 配置部分 ======
SSID = "REDACTED_SSID"
PASSWORD = "REDACTED"
WEBREPL_PASSWORD = "1234"


def _ensure_webrepl_cfg():
    """webrepl_cfg.py 不存在时自动生成（WebREPL 密码配置文件）。"""
    try:
        os.stat("webrepl_cfg.py")
        return
    except OSError:
        with open("webrepl_cfg.py", "w") as f:
            # MicroPython webrepl 模块只识别变量名 PASS（不是 PASSWD）
            f.write('PASS = "%s"\n' % WEBREPL_PASSWORD)
        print("[boot] webrepl_cfg.py created (password=%s)" % WEBREPL_PASSWORD)


def _connect_wifi(timeout_s=20):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    # 关闭 WiFi 省电（modem sleep），否则空闲后唤醒延迟会导致 WebREPL 握手超时
    wlan.config(pm=0xA11140)
    if not wlan.isconnected():
        print("[boot] connecting WiFi: %s ..." % SSID)
        wlan.connect(SSID, PASSWORD)
        t = timeout_s
        while not wlan.isconnected() and t > 0:
            print(".", end="")
            time.sleep(1)
            t -= 1
        print()
    if wlan.isconnected():
        print("[boot] WiFi OK, IP: %s" % wlan.ifconfig()[0])
    else:
        print("[boot] WiFi FAILED (WebREPL unavailable this boot)")
    return wlan


def _confirm_ota_if_pending():
    """OTA 新固件联网成功即确认固化（pending_verify -> valid）。"""
    if not _HAS_OTA:
        return
    try:
        info = ota.info()
        state = info[7] if len(info) > 7 else "undefined"
        print("[boot] ota: slot=%s version=%s state=%s" % (info[0], info[2], state))
        if state == "pending_verify":
            ota.mark_valid()
            print("[boot] OTA firmware confirmed (rollback protection released)")
    except Exception as e:
        # 首烧无 ota_0/ota_1 或模块异常时不阻塞启动
        print("[boot] ota check skipped: %s" % e)


_ensure_webrepl_cfg()
_wlan = _connect_wifi()
if _wlan.isconnected():
    _confirm_ota_if_pending()
webrepl.start()
print("[boot] WebREPL started on ws://%s:8266" % _wlan.ifconfig()[0])

# ==================== WebREPL 诊断块（定位问题后删除） ====================
# 三路对照实验，全部自动化，证据打印到串口日志：
#   8266: 给 webrepl 换上带打印的 accept 回调（stop 后重启，植入追踪）
#   8267: 复刻 webrepl 机制的独立监听（option 20 回调，最简实现）
#   8268: 线程版 accept 循环（对照：线程是否正常）
#   20 秒后设备自连 127.0.0.1 对三个端口做自检，结果打印到串口
import socket as _sock
import _thread as _thr
import time as _time

_orig_accept = webrepl.accept_conn

def _traced_accept(listen_s):
    print("[diag] webrepl callback FIRED")
    return _orig_accept(listen_s)

webrepl.stop()
webrepl.start(8266, None, _traced_accept)
print("[diag] webrepl restarted with traced callback")

def _diag_accept(listen_s):
    print("[diag] 8267 callback FIRED")
    cl, addr = listen_s.accept()
    try:
        cl.write(b"DIAG-OK\n")
        print("[diag] 8267 replied to %s" % (addr,))
    except Exception as e:
        print("[diag] 8267 reply err: %r" % e)
    cl.close()

_ls = _sock.socket()
_ls.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
_ls.bind(("0.0.0.0", 8267))
_ls.listen(1)
_ls.setsockopt(_sock.SOL_SOCKET, 20, _diag_accept)
print("[diag] 8267 listener ready")

def _thread_server():
    s = _sock.socket()
    s.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 8268))
    s.listen(2)
    while True:
        c, a = s.accept()
        try:
            c.write(b"THREAD-OK\n")
            print("[diag] 8268 served %s" % (a,))
        except Exception as e:
            print("[diag] 8268 err: %r" % e)
        c.close()

_thr.start_new_thread(_thread_server, ())
print("[diag] 8268 thread server started")

def _selftest():
    _time.sleep(20)
    for port, mark in ((8266, "webrepl"), (8267, "diag8267"), (8268, "thread")):
        try:
            c = _sock.socket()
            c.settimeout(5)
            c.connect(("127.0.0.1", port))
            c.write(b"GET / HTTP/1.0\r\n\r\n")
            try:
                r = c.read(64)
            except OSError as e:
                r = "READ-ERR:" + str(e)
            print("[diag] selftest %s(%d): recv=%r" % (mark, port, r))
            c.close()
        except Exception as e:
            print("[diag] selftest %s(%d): %s: %s" % (mark, port, type(e).__name__, e))
    print("[diag] selftest done")

_thr.start_new_thread(_selftest, ())
print("[diag] selftest scheduled (20s)")
# ==================== 诊断块结束 ====================
