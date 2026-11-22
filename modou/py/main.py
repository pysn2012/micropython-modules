# 魔豆 main.py（放设备根目录，boot.py 之后自动运行）
#
# UART0 顶针连接小车底座后被占用，REPL 只走无线通道（WebREPL / telnet 兜底）
# 本文件开机自动启动网页遥控服务器：
#   浏览器打开 http://<魔豆IP>/ 即可遥控（按住按钮行驶，松手 800ms 内自动停车）

import car_web
import car_ctrl

car_ctrl.wake()   # 开机唤醒底座供电域（不在底座上时发一帧也无副作用）
car_web.start()   # 端口 80 网页遥控，独立线程不阻塞 REPL
print("[main] car web started")
