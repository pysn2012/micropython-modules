# M5Stack Stamp-P4 (ESP32-P4NRW32 rev1.3) + Stamp-AddOn C6 (SDIO WiFi)
# 自定义板：所有板级差异集中在 sdkconfig.stamp_p4 单文件中
set(IDF_TARGET esp32p4)

set(SDKCONFIG_DEFAULTS
    boards/sdkconfig.base
    boards/sdkconfig.p4
    ${CMAKE_CURRENT_LIST_DIR}/sdkconfig.stamp_p4
)

list(APPEND MICROPY_DEF_BOARD
    MICROPY_HW_BOARD_NAME="M5Stack Stamp-P4 with Stamp-AddOn C6 WiFi"
    MICROPY_PY_NETWORK_WLAN=1
    MICROPY_PY_BLUETOOTH=0
)
