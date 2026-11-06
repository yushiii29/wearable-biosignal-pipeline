// 传感器原型采集程序：真实硬件尚未验证。经典 ESP32-WROOM 假设，接入前核对板型和引脚。
#include <Arduino.h>
const uint32_t BAUD = 460800;
uint32_t seq = 0;
uint32_t previous = 0;
const uint32_t INTERVAL_US = 4000;
const uint8_t SIGNAL_PIN = 35;
void setup() { Serial.begin(BAUD); analogReadResolution(12); pinMode(SIGNAL_PIN, INPUT); Serial.println("# ready ecg"); }

void loop() {
  uint32_t now = micros();
  if ((uint32_t)(now - previous) < INTERVAL_US) return;
  previous = now; // 不追赶延迟产生伪造等间隔数据；时间戳反映实际采样时刻
  int value = analogRead(SIGNAL_PIN);
  Serial.printf("{\"v\":1,\"kind\":\"ecg\",\"seq\":%lu,\"t_ms\":%lu,\"ecg_adc\":%lu}\n", (unsigned long)seq++, (unsigned long)millis(), (unsigned long)value);
}
