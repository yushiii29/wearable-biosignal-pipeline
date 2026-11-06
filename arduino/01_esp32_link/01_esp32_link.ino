// 传感器原型采集程序：真实硬件尚未验证。经典 ESP32-WROOM 假设，接入前核对板型和引脚。
#include <Arduino.h>
const uint32_t BAUD = 460800;
uint32_t seq = 0;
uint32_t previous = 0;
const uint32_t INTERVAL_US = 100000;
void setup() { Serial.begin(BAUD); Serial.println("# ready esp32"); }

void loop() {
  uint32_t now = micros();
  if ((uint32_t)(now - previous) < INTERVAL_US) return;
  previous = now; // 不追赶延迟产生伪造等间隔数据；时间戳反映实际采样时刻
  uint32_t value = seq;
  Serial.printf("{\"v\":1,\"kind\":\"esp32\",\"seq\":%lu,\"t_ms\":%lu,\"counter\":%lu}\n", (unsigned long)seq++, (unsigned long)millis(), (unsigned long)value);
}
