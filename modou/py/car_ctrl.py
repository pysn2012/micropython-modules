# 魔豆底座控车模块（UART0 与 REPL 共用，底座只认 {AT+...} 帧，REPL 输出它自动忽略）
#
# 协议来源：Flower_modou docs/MOTOR_REMOTE_PROTOCOL_2026-07-30.md（实机验证）
#   唤醒：AT+Pon（每次开机首次发送，之后不用重发）
#   运动：{AT+CMD=(9,1,0,1),(模式,时长ms,转向,动力,0),(0,0,0,0)x4}
#     模式：3=前进 2=后退 0/1=原地转；转向 0..180（90=直行）；动力 1..100
#     时长为 200ms 整数倍；运动帧有效期约 800ms，超时自动停
#
# 用法（串口 REPL 或 WebREPL 均可）：
#   import car_ctrl
#   car_ctrl.wake()                  # 唤醒底座（听见灯效/上电动作）
#   car_ctrl.forward(800, 60)        # 前进 800ms 动力 60
#   car_ctrl.backward(400, 50)       # 后退
#   car_ctrl.spin_left(400, 50)      # 原地左转
#   car_ctrl.spin_right(400, 50)     # 原地右转

import sys
import time

BAUD = 115200  # 控制台 UART0 默认波特率，无需重新初始化

Zeros = "(0,0,0,0),(0,0,0,0),(0,0,0,0),(0,0,0,0)"


def _send(cmd_text):
    """发送一帧 {AT+...}\r\n。底座 AT 解析器只认这种帧。

    注意：直接写系统控制台（stdout -> UART0 TX=GPIO1, 115200 8N1）。
    不要用 machine.UART(0) 重建串口——UART0 是 REPL 保留串口，
    重建会卡死主任务、kill 掉 socket 事件轮询链（WebREPL 全挂，板测实证）。
    """
    sys.stdout.write("{%s}\r\n" % cmd_text)


def wake():
    """唤醒底座供电域。首次发一次即可，运动帧不会重新锁电机。"""
    _send("AT+Pon")
    time.sleep_ms(300)


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


def demo():
    """完整演示：唤醒 -> 前进 -> 后退 -> 左转 -> 右转，帧间自然停止。"""
    print("[car] wake base...")
    wake()
    time.sleep(1)
    for name, fn in (("forward", forward), ("backward", backward),
                     ("spin_left", spin_left), ("spin_right", spin_right)):
        print("[car] %s" % name)
        fn()
        time.sleep(1.5)
    print("[car] demo done (最后一次运动帧 800ms 后自动停止)")


print("[car] ready: car_ctrl.wake() / forward() / backward() / spin_left() / spin_right() / demo()")
