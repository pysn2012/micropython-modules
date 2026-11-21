# 魔豆屏幕 RAW 复刻测试——不经过 st7789 模块，逐字节复刻 Flower_modou modou_lcd.c 序列
# 用途：test_screen.py（st7789 模块版）黑屏时，用本脚本隔离"模块用法问题 vs 驱动序列问题"
#
# 序列来源（modou_lcd.c 实测可用的 C 实现）：
#   1. AW9106 上电序列（aw9106.init，与 C 逐字节一致）
#   2. GPIO22 复位脉冲：低 100ms -> 高 100ms（lcd_factory_reset_pulse）
#   3. SPI2 mode0 10MHz（原厂时钟；C 驱动 40MHz 同样被硬件钳到 26.67）
#   4. 原厂 18 条初始化表（延时规则：flags&0x11!=0 才 20ms；0x11/0x29 原厂无延时）
#   5. MADCTL 0x36=0xA0（lcd_factory_startup_state）
#   6. 全屏填充

import time
from machine import Pin, SPI
import aw9106

CS = Pin(27, Pin.OUT, value=1)
DC = Pin(21, Pin.OUT, value=0)
RST = Pin(22, Pin.OUT, value=1)


def cmd(c, data=None):
    CS(0)
    DC(0)
    spi.write(bytes([c]))
    if data:
        DC(1)
        spi.write(bytes(data))
    CS(1)


print("[raw] 1. AW9106 init")
aw9106.init()
aw9106.rgb(0, 0, 0)

print("[raw] 2. SPI 10MHz init")
spi = SPI(2, baudrate=10_000_000, polarity=0, phase=0,
          sck=Pin(32, Pin.OUT), mosi=Pin(33, Pin.OUT))

print("[raw] 3. 复位脉冲 100ms/100ms")
RST(0)
time.sleep_ms(100)
RST(1)
time.sleep_ms(100)

print("[raw] 4. 原厂初始化表")
FACTORY = [
    (0xC0, [0x00], 20),
    (0xC2, [0x01, 0xFF], 0),
    (0xC3, [0x13], 20),
    (0xC4, [0x20], 20),
    (0xC6, [0x0F], 20),
    (0xCA, [0x0F], 20),
    (0xC8, [0x08], 20),
    (0x55, [0xB0], 20),
    (0x21, [0x00], 20),
    (0x36, [0x00], 20),
    (0x3A, [0x55], 20),
    (0xB1, [0x40, 0x02, 0x14], 0),
    (0x26, [0x01], 20),
    (0x2A, [0x00, 0x00, 0x00, 0xEF], 0),
    (0x2B, [0x00, 0x00, 0x01, 0x3F], 0),
    (0x2C, [0x00], 20),
    (0xE0, [0xD0, 0x00, 0x05, 0x0E, 0x15, 0x0D, 0x37, 0x43,
            0x47, 0x09, 0x15, 0x12, 0x16, 0x19], 0),
    (0xE1, [0xD0, 0x00, 0x05, 0x0D, 0x0C, 0x06, 0x2D, 0x44,
            0x40, 0x0E, 0x1C, 0x18, 0x16, 0x19], 0),
    (0x11, None, 0),    # SLPOUT，原厂 flags=0x80 无延时
    (0x29, None, 0),    # DISPON，同上
]
for c, d, delay in FACTORY:
    cmd(c, d)
    if delay:
        time.sleep_ms(delay)

print("[raw] 5. MADCTL=0xA0（原厂 startup state）")
cmd(0x36, [0xA0])
time.sleep_ms(50)

print("[raw] 6. 全屏白填充")
cmd(0x2A, [0x00, 0x00, 0x00, 0xEF])
cmd(0x2B, [0x00, 0x00, 0x01, 0x3F])
cmd(0x2C)
CS(0)
DC(1)
white = b"\xFF\xFF" * (160 * 128)
for i in range(0, len(white), 4092):
    spi.write(white[i:i + 4092])
CS(1)

print("[raw] done - 屏幕应为全白")
