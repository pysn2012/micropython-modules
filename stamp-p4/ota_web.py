# Stamp-P4 网页 OTA 升级器（设备端）
# ------------------------------------------------------------------
# 用法：
#   1. 把本脚本传到板子（Thonny 保存到设备），REPL 运行：
#        import ota_web; ota_web.run()
#   2. 串口会打印 http://<板子IP>/ —— 用局域网内任意电脑/手机浏览器打开
#   3. 页面显示当前分区和固件版本；点「选择固件」选新版 micropython.bin
#      （注意是 artifact 里的 micropython.bin，不是 firmware.bin）
#   4. 点「开始升级」→ 进度条走完 → 设备自动重启进新固件
#
# 原理：设备起 HTTP 服务；GET / 返回升级页面；POST /upload 收裸文件流，
#       边收边写入 OTA 更新槽（ota.begin/write/finish）；完成即切槽重启。
# ------------------------------------------------------------------

import usocket as socket
import network
import time
import ota
import machine

# ====== 配置部分 ======
SSID = "REDACTED_SSID"
PASSWORD = "REDACTED"
PORT = 80
# 更新槽 2.875MB，留余量
MAX_PAYLOAD = 2800000

_HTML = (
    b"HTTP/1.0 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n\r\n"
    b"<!DOCTYPE html><html><head><meta charset='utf-8'>"
    b"<meta name='viewport' content='width=device-width,initial-scale=1'>"
    b"<title>Stamp-P4 OTA</title><style>"
    b"body{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px}"
    b".bar{background:#eee;height:24px;border-radius:12px;overflow:hidden;margin:16px 0}"
    b".fill{background:#2b7de9;height:100%;width:0%;transition:width .3s}"
    b"button{padding:10px 24px;font-size:16px}"
    b"#st{margin-top:12px;color:#555;white-space:pre-wrap}"
    b"</style></head><body>"
    b"<h2>Stamp-P4 OTA \xe5\x8d\x87\xe7\xba\xa7</h2>"
    b"<div id='cur'>\xe8\xaf\xbb\xe5\x8f\x96\xe7\x89\x88\xe6\x9c\xac\xe4\xb8\xad...</div>"
    b"<p><input type='file' id='f' accept='.bin'></p>"
    b"<button onclick='up()'>\xe5\xbc\x80\xe5\xa7\x8b\xe5\x8d\x87\xe7\xba\xa7</button>"
    b"<div class='bar'><div class='fill' id='p'></div></div>"
    b"<div id='st'></div>"
    b"<script>"
    b"fetch('/info').then(r=>r.text()).then(t=>cur.textContent=t);"
    b"function up(){"
    b"var f=f_.files[0];"
    b"if(!f){st.textContent='\xe8\xaf\xb7\xe5\x85\x88\xe9\x80\x89\xe6\x8b\xa9\xe5\x9b\xba\xe4\xbb\xb6';return;}"
    b"var x=new XMLHttpRequest();"
    b"x.open('POST','/upload');"
    b"x.upload.onprogress=function(e){"
    b"var p=Math.round(e.loaded*100/e.total);"
    b"p_.style.width=p+'%';"
    b"st.textContent=p+'%  '+e.loaded+'/'+e.total+' bytes';};"
    b"x.onload=function(){st.textContent='OK: '+x.responseText;"
    b"st.textContent+='\\n\xe5\x8d\x87\xe7\xba\xa7\xe5\xae\x8c\xe6\x88\x90\xef\xbc\x8c\xe8\xae\xbe\xe5\xa4\x87\xe9\x87\x8d\xe5\x90\xaf\xe4\xb8\xad...'};"
    b"x.onerror=function(){st.textContent='\xe4\xb8\x8a\xe4\xbc\xa0\xe5\xa4\xb1\xe8\xb4\xa5';};"
    b"x.send(f);}"
    b"</script></body></html>"
)


def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to %s..." % SSID)
        wlan.connect(SSID, PASSWORD)
        t = 20
        while not wlan.isconnected() and t > 0:
            print(".", end="")
            time.sleep(1)
            t -= 1
        if not wlan.isconnected():
            raise RuntimeError("WiFi connect timeout")
    print()
    print("[web-ota] IP: http://%s/" % wlan.ifconfig()[0])
    return wlan


def _send(conn, status, ctype, body):
    conn.send("HTTP/1.0 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\n\r\n"
              % (status, ctype, len(body)))
    for i in range(0, len(body), 1024):
        conn.send(body[i:i + 1024])


def _read_head(conn):
    # 读请求头（\r\n\r\n 截断），返回 (head_bytes, 剩余的首段 body)
    head = b""
    while b"\r\n\r\n" not in head:
        d = conn.recv(512)
        if not d:
            raise OSError("peer closed before header")
        head += d
        if len(head) > 8192:
            raise OSError("header too large")
    h, body = head.split(b"\r\n\r\n", 1)
    return h, body


def handle_upload(conn, head, body):
    lines = head.split(b"\r\n")
    length = None
    for ln in lines:
        if ln.lower().startswith(b"content-length:"):
            length = int(ln.split(b":", 1)[1])
    if length is None or length < 64 or length > MAX_PAYLOAD:
        _send(conn, "400 Bad Request", "text/plain",
              b"bad payload size (need micropython.bin app image)")
        return
    print("[web-ota] payload %d bytes" % length)
    info = ota.info()
    print("[web-ota] running=%s next=%s" % (info[0], info[1]))

    ota.begin()
    n = 0
    try:
        while n < length:
            if body:
                d, body = body, b""
            else:
                d = conn.recv(4096)
            if not d:
                raise OSError("short read at %d/%d" % (n, length))
            take = min(len(d), length - n)
            ota.write(d[:take])
            n += take
            if (n // 65536) != ((n - len(d)) // 65536):
                print("[web-ota] %d/%d (%d%%)" % (n, length, n * 100 // length))
        ota.finish()
    except Exception as e:
        ota.abort()
        print("[web-ota] FAILED: %s" % e)
        _send(conn, "500 Internal Server Error", "text/plain",
              ("upgrade failed: %s\n(old firmware still running)" % e).encode())
        return
    print("[web-ota] OK %d bytes, boot slot switched, rebooting..." % n)
    _send(conn, "200 OK", "text/plain",
          b"upgrade done (%d bytes). rebooting to new firmware..." % n)
    time.sleep(1)
    machine.reset()


def run():
    connect_wifi()
    info = ota.info()
    print("[web-ota] running=%s version=%s build=%s %s" % (info[0], info[2], info[3], info[4]))

    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", PORT))
    s.listen(1)
    print("[web-ota] server ready on port %d (Ctrl+C to stop)" % PORT)

    while True:
        conn, addr = s.accept()
        conn.settimeout(8)
        try:
            head, body = _read_head(conn)
            line = head.split(b"\r\n")[0].decode(errors="ignore")
            path = line.split(" ")[1] if " " in line else "/"
            if path.startswith("/info"):
                i = ota.info()
                txt = "partition=%s  version=%s  build=%s %s  idf=%s" % (
                    i[0], i[2], i[3], i[4], i[5])
                _send(conn, "200 OK", "text/plain", txt.encode())
            elif path.startswith("/upload"):
                handle_upload(conn, head, body)
                continue  # 上传完成后设备已重启
            else:
                _send(conn, "200 OK", "text/html", _HTML)
        except Exception as e:
            print("[web-ota] request error: %s" % e)
            try:
                _send(conn, "400 Bad Request", "text/plain", str(e).encode())
            except Exception:
                pass
        conn.close()
