# 08_sensor_sync：现有 ESP32 的三通道采集固件

已上传到**原来的 ESP32**，无需购买新开发板；Uno/Nano 的气囊草图是另一块板上的程序。该固件支持 USB `SELECT pressure`、`SELECT imu`、`SELECT ecg` 和 `SELECT all`，也支持本地热点 Wi-Fi 的相应模式。`all` 以同一设备时钟交错采三路，每条 JSON 保留自己的 `kind`、全局 `seq` 与 `t_ms`。单项模式仍供旧页面分开测试。

引脚沿用现有方案：压力 GPIO34、ECG GPIO35、IMU SDA21/SCL22（I2C 地址 0x4A）。目标间隔分别为压力 50 ms、心电 4 ms、IMU 40 ms；实际速度应从保存的时间戳和 `sampling_overruns` 检查，不能凭目标值声称三路采样已经验证。Wi-Fi 热点名称 `Wearable-...`，密码 `Wearable2026`，地址 `http://192.168.4.1`。

上传和 USB 台架排查前先断开人体心电导联。固件只采集信号，不计算候选界线，不连接气泵或气囊。电池供电时可经 Wi-Fi 向电脑提供三路原始数据，但仍需电脑发出开始采集请求、计算约20秒整段候选值，并通过独立串口向 Uno 发送可选非人体台架命令。仅给 ESP32 接电池，设备不会自行识别并触发气囊。
