# MicroPython 固件编译仓库

个人 MicroPython 固件编译仓库：通过 GitHub Actions 编译各开发板的 mpy 固件，
产物统一打包成 bin（bootloader / partition-table / firmware / micropython OTA 载荷）。

> 本仓库 fork 自 [cnadler86/micropython-camera-API](https://github.com/cnadler86/micropython-camera-API)，
> 在其基础上扩展了多板固件工作流与自定义板。camera 模块相关文档见上游 README（[英文原版备份](docs_camera_README_en.md) 待补）。

## 固件清单

| 工作流 | 目标板 | 要点 |
|---|---|---|
| build mpy modou ota | MODOU（魔豆小车，ESP32-D0WD 16MB） | mpy 1.29 + st7789 + ota（回滚保护）+ dsp（ZL38063）；WebREPL + 网页 OTA |
| build mpy with st7789 1.29 | ESP32_GENERIC_S3（8/16MB 矩阵） | mpy 1.29 + st7789 + ota + WebREPL |
| build mpy stamp-p4 ota | StampP4 | mpy 1.29 + ota（含差分升级）+ WebREPL |
| build mpy stamp-p4 c6wifi 1.28-1.29 | StampP4 / C6-WiFi | mpy 1.28 / 1.29 |
| build mpy with camera1.25 / 1.27 | ESP32_GENERIC_S3 | camera 模块固件 |
| build esp32 mpy1.25 / 1.27 | ESP32_GENERIC | 通用 mpy 固件 |
| build esp32c3 mpy1.25 | ESP32_GENERIC_C3 | 通用 mpy 固件 |

所有工作流手动触发（workflow_dispatch），在 Actions 页选择运行。

## 目录结构

```
modules/          # 跨板公共 C 模块
├── st7789/       # ST7789 屏驱动（vendor 自 russhughes/st7789_mpy，MIT）
└── ota/          # esp_ota_ops 封装（双 OTA 槽 + 回滚保护，无差分版）

modou/            # 魔豆小车板（板目录 + 分区表 + 设备端 py + dsp C 模块）
generic/          # 通用 S3 双 OTA 分区表（8MB / 16MB）
stamp-p4/         # StampP4 板相关（ota_mod 含差分升级完整版）

src/              # camera C 模块（上游遗留，camera 工作流使用中）
esp32-camera/     # camera 驱动子模块（上游遗留）
examples/ tests/ typings/ build.sh   # camera 相关示例/测试/类型标注/本地构建脚本
```

## 魔豆小车（modou）快速烧录

首烧（经典 ESP32 引导偏移 0x1000）：

```
esptool.py --chip esp32 --port COMx --baud 460800 write_flash -z 0x1000 mpy_1.29_MODOU_OTA_16MB_firmware.bin
```

OTA 升级用同目录 `micropython.bin`（纯 app image，不能首烧）。详见 `modou/README.md`。

## 致谢

- [cnadler86/micropython-camera-API](https://github.com/cnadler86/micropython-camera-API)（MIT）
- [russhughes/st7789_mpy](https://github.com/russhughes/st7789_mpy)（MIT）
- [FlowerCat-chen/Flower_modou](https://github.com/FlowerCat-chen/Flower_modou)（魔豆小车 IDF 原厂驱动参考）
