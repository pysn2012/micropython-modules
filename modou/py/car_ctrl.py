# 魔豆底座控车模块（UART0 与 REPL 共用，底座只认 {AT+...} 帧，REPL 输出它自动忽略）
#
# 协议来源：Flower_modou docs/MOTOR_REMOTE_PROTOCOL_2026-07-30.md（实机验证）
#   唤醒：AT+Pon（每次开机首次发送，之后不用重发）
#   运动：{AT+CMD=(9,1,0,1),(模式,时长ms,转向,动力,0),(0,0,0,0)x4}
#     模式：3=前进 2=后退 0/1=原地转；转向 0..180（90=直行）；动力 1..100
#     时长为 200ms 整数倍；运动帧有效期约 800ms，超时自动停
#
# 用法（WebREPL 或串口均可）：
#   import car_ctrl
#   car_ctrl.probe()                 # 探测：发 AT+Ver，打印底座应答（不动电机）
#   car_ctrl.wake()                  # 唤醒底座（听见灯效/上电动作）
#   car_ctrl.forward(800, 60)        # 前进 800ms 动力 60
#   car_ctrl.backward(400, 50)       # 后退
#   car_ctrl.spin_left(400, 50)      # 原地左转
#   car_ctrl.spin_right(400, 50)     # 原地右转
#   car_ctrl.stop()                  # 急停 + 灯光复位
#   car_ctrl.front_light() / tail_light() / flash_light()   # 灯光效果
#   car_ctrl.demo()                  # 全套演示

import time
from machine import UART

BAUD = 115200

# 固件已关闭 UART REPL（MICROPY_HW_ENABLE_UART_REPL=0）：
#   UART0 完全空闲、专供底座通信，这里独占初始化是安全的。
#   旧固件保留 REPL 时重建 UART0 会与 REPL IRQ 冲突卡死主任务——那正是
#   上午"WebREPL 全挂"的根因，关 REPL 后一并消失。
_uart = UART(0, baudrate=BAUD, tx=1, rx=3, timeout=0)

Zeros = "(0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0)"


def _send(cmd_text):
    """发送一帧 {AT+...}\r\n。底座 AT 解析器只认这种帧。"""
    _uart.write("{%s}\r\n" % cmd_text)


def wake():
    """唤醒底座供电域。首次发一次即可，运动帧不会重新锁电机。"""
    _send("AT+Pon")
    time.sleep_ms(300)


def probe(timeout_ms=1200):
    """链路探测（不动电机）：发 {AT+Ver} 询问帧，打印底座在 timeout 内
    回的一切字节。有回话 = TX/RX 双向都通；无回话 = 底座没上电或没收到。
    返回 bytes（空 = 无应答）。"""
    _uart.read()  # 清掉缓冲里的旧数据
    _send("AT+Ver")
    buf = b""
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < timeout_ms:
        r = _uart.read(128)
        if r:
            buf += r
        time.sleep_ms(20)
    if buf:
        print("[car] base reply %d bytes: %r" % (len(buf), buf))
    else:
        print("[car] no reply within %dms" % timeout_ms)
    return buf


def move(mode, duration_ms, steer, power):
    """单帧运动。duration_ms 自动取 200ms 整数倍。"""
    d = max(200, (int(duration_ms) // 200) * 200)
    _send("AT+CMD=(9,1,0,1),(%d,%d,%d,%d,0),%s" % (mode, d, steer, power, Zeros))


def forward(duration_ms=800, power=60):
    move(3, duration_ms, 90, power)


def backward(duration_ms=800, power=60):
    move(2, duration_ms, 90, power)


def spin_left(duration_ms=400, power=50):
    """原地左转（转向 <15）。"""
    move(0, duration_ms, 10, power)


def spin_right(duration_ms=400, power=50):
    """原地右转（转向 >165）。"""
    move(1, duration_ms, 170, power)


# ---- 灯光 / 急停帧（逐字取自 Flower_modou car_remote_server.cc，实机验证格式）----

_STOP_FRAMES = (
    "AT+CMD=(1,2,3,2),(255,0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0)",
    "AT+CMD=(1,3,3,3),(255,0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0)",
)


def stop():
    """急停 + 灯光复位：连发两帧停止帧（帧间 18ms，与 Flower_modou 一致）。"""
    for f in _STOP_FRAMES:
        _send(f)
        time.sleep_ms(18)


def front_light():
    """前灯效果（2s 循环）。"""
    _send("AT+CMD=(4,1,0,1),(0,0,0,0,0),(7,0,2000,2),(7,0,2000,2),(0,0,0,0),(0,0,0,0)")


def tail_light():
    """尾灯效果（2s 循环）。"""
    _send("AT+CMD=(4,1,0,1),(0,0,0,0,0),(0,0,0,0),(0,0,0,0),(7,1,2000,2),(7,1,2000,2)")


def flash_light():
    """前后灯交替闪烁（500ms）。"""
    _send("AT+CMD=(12,1,3,1),(0,0,0,0,0),(7,0,500,1),(7,0,500,1),(7,1,500,1),(7,1,500,1)")


def demo():
    """完整演示：唤醒 -> 前进 -> 后退 -> 左转 -> 右转 -> 灯光闪烁。"""
    print("[car] wake base...")
    wake()
    time.sleep(1)
    for name, fn in (("forward", forward), ("backward", backward),
                     ("spin_left", spin_left), ("spin_right", spin_right)):
        print("[car] %s" % name)
        fn()
        time.sleep(1.5)
    print("[car] lights flash")
    flash_light()
    time.sleep(1.5)
    print("[car] demo done (最后一次运动帧 800ms 后自动停止)")


print("[car] ready: car_ctrl.wake() / forward() / backward() / spin_left() / spin_right() / demo()")
