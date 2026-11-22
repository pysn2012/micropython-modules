# 魔豆 BLE 遥控（微信小程序端，Nordic UART 透传协议）
#
# 使用（WebREPL 连上后手动运行）：
#   import ble_car
#   ble_car.remote()
#
#   小程序扫描并连接设备名 "MODOU"：
#     上键(B5) 按住=前进   下键(B6) 按住=后退
#     左键(B7) 按住=左转   右键(B8) 按住=右转
#     自定义键 1=前灯  2=尾灯  3=闪烁  4=重新唤醒底座
#     松开方向键 = 急停 + 灯光复位（与网页版 stop 帧一致）
#
# 小程序协议（经典蓝牙遥控器 5 字符格式，2026-11-22 从参考脚本全样例验算）：
#   "!B<键号><1按下/0松开><校验和>"，校验和字符使 5 字符 ASCII 总和 = 255
#   例：!B516=按住上键（33+66+53+49+54=255），!B507=松开上键
#   字面量 "stop" 同样处理为停车
#
# 说明：
#   - BLE 与 WiFi/WebREPL 共存（ESP32 coexist），互不影响
#   - 若小程序只在按住期间连发消息，运动帧 400ms + 800ms 有效期无缝衔接；
#     若只发一次按下，车动作约 1 秒后由底座超时自动停
#   - 松开发的是 car_ctrl.stop()（含灯光复位帧），灯效会被重置，属预期行为

import bluetooth
import time

import car_ctrl

BLE_MSG = ""

# Nordic UART Service UUID（与小程序一致）
UUID_SERVICE = "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"
UUID_RX = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"  # 小程序写 -> ESP32 收
UUID_TX = "6E400003-B5A3-F393-E0A9-E50E24DCCA9E"  # ESP32 notify -> 小程序


class BLECar:
    """蓝牙外设：注册 NUS 服务、广播设备名、收小程序指令。
    结构与已实机验证的参考实现（蓝牙小程序遥控.py）一致，仅去掉屏幕依赖。"""

    def __init__(self, name="MODOU"):
        self.name = name
        self.ble = bluetooth.BLE()
        self.ble.active(True)
        self.ble.config(gap_name=name)
        self.ble.irq(self.ble_irq)
        self.register()
        # 默认只收 20 字节，扩到 100
        self.ble.gatts_write(self.rx, bytes(100))
        self.advertise()

    def register(self):
        services = (
            (
                bluetooth.UUID(UUID_SERVICE),
                (
                    (bluetooth.UUID(UUID_TX), bluetooth.FLAG_NOTIFY),
                    (bluetooth.UUID(UUID_RX), bluetooth.FLAG_WRITE),
                ),
            ),
        )
        ((self.tx, self.rx),) = self.ble.gatts_register_services(services)

    def advertise(self):
        # MicroPython 编码名大小写敏感，"UTF-8" 会 LookupError；用默认 utf-8
        name = self.name.encode()
        adv = bytearray(b"\x02\x01\x02") + bytearray((len(name) + 1, 0x09)) + name
        self.ble.gap_advertise(100, adv)
        print("[ble] advertising: %s" % self.name)

    def ble_irq(self, event, data):
        global BLE_MSG
        if event == 1:  # 手机连上
            print("[ble] connected")
        elif event == 2:  # 手机断开 -> 重新广播
            print("[ble] disconnected, advertising again")
            self.advertise()
        elif event == 3:  # 收到写入
            BLE_MSG = self.ble.gatts_read(self.rx).decode().strip()


def handle(msg):
    """一条小程序消息 -> car_ctrl 调用。"""
    if msg == "stop":
        car_ctrl.stop()
        return
    if not (msg.startswith("!B") and len(msg) == 5):
        return
    # 校验和：5 个字符 ASCII 总和 = 255
    if sum(map(ord, msg)) != 255:
        print("[ble] bad checksum: %r" % msg)
        return
    btn, state = msg[2], msg[3]
    if state == "0":  # 松开任意键 -> 停车
        car_ctrl.stop()
        return
    if btn == "5":
        car_ctrl.forward(400, 60)
    elif btn == "6":
        car_ctrl.backward(400, 60)
    elif btn == "7":
        car_ctrl.spin_left(400, 50)
    elif btn == "8":
        car_ctrl.spin_right(400, 50)
    elif btn == "1":
        car_ctrl.front_light()
    elif btn == "2":
        car_ctrl.tail_light()
    elif btn == "3":
        car_ctrl.flash_light()
    elif btn == "4":
        car_ctrl.wake()


def remote(name="MODOU"):
    """一键 BLE 遥控：唤醒底座 -> 起广播 -> 循环处理小程序指令。
    Ctrl-C 退出（自动急停）。"""
    car_ctrl.wake()
    ble = BLECar(name)
    print("[ble] remote ready: open mini-program, connect '%s'" % name)
    try:
        while True:
            global BLE_MSG
            if BLE_MSG:
                msg = BLE_MSG
                BLE_MSG = ""
                print("[ble] >>%s<<" % msg)
                try:
                    handle(msg)
                except Exception as e:
                    print("[ble] handle err: %r" % e)
            time.sleep_ms(100)
    except KeyboardInterrupt:
        car_ctrl.stop()
        print("\n[ble] remote exited (car stopped)")


print("[car] ble_car loaded: BLE remote = ble_car.remote()")
