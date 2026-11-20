# Modou 板专属 USER_C_MODULES 聚合入口（modou 工作流使用）
# 公共模块（st7789/ota）+ modou 专属模块（dsp）
include(${CMAKE_CURRENT_LIST_DIR}/../modules/st7789/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/../modules/ota/micropython.cmake)
include(${CMAKE_CURRENT_LIST_DIR}/modules/dsp/micropython.cmake)
