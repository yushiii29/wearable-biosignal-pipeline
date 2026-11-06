// 传感器原型采集程序：真实硬件尚未验证。经典 ESP32-WROOM 假设，接入前核对板型和引脚。
#include <Arduino.h>
const uint32_t BAUD = 460800;
uint32_t seq = 0;
uint32_t previous = 0;
#include <Wire.h>
#include <DFRobot_Multi_DOF_IMU.h>
// 仅针对确认是 SEN0696 的模块；若实物 SKU 不同，勿按此程序接线。
const uint8_t SDA_PIN = 21, SCL_PIN = 22, IMU_ADDR = 0x4A;
const uint32_t INTERVAL_US = 20000; // 目标 50Hz，有效频率由实际时间戳检查
DFRobot_Multi_DOF_IMU_I2C imu(DFRobot_Multi_DOF_IMU::eSensorModel10DOF, &Wire, IMU_ADDR);
void setup() {
 Serial.begin(BAUD); Wire.begin(SDA_PIN,SCL_PIN);
 while(!imu.begin()) { Serial.println("# IMU init failed: check SKU, I2C mode, address and wiring"); delay(1000); }
 if (!imu.setSensorMode(DFRobot_Multi_DOF_IMU::eNormalMode) ||
     !imu.setAccelRange(DFRobot_Multi_DOF_IMU::eAccelRange2G) ||
     !imu.setGyroRange(DFRobot_Multi_DOF_IMU::eGyroRange250DPS)) {
   while(true) {Serial.println("# IMU configuration failed");delay(1000);}
 }
 Serial.println("# ready imu");
}

void loop() {
  uint32_t now = micros();
  if ((uint32_t)(now - previous) < INTERVAL_US) return;
  previous = now; // 不追赶延迟产生伪造等间隔数据；时间戳反映实际采样时刻
  DFRobot_Multi_DOF_IMU::sSensorData_t a,g,m; float pressure;
  if(!imu.get10dofData(&a,&g,&m,&pressure,false)) {Serial.println("# IMU read failed");return;}
  Serial.printf("{\"v\":1,\"kind\":\"imu\",\"seq\":%lu,\"t_ms\":%lu,\"ax_g\":%.5f,\"ay_g\":%.5f,\"az_g\":%.5f,\"gx_dps\":%.5f,\"gy_dps\":%.5f,\"gz_dps\":%.5f,\"mx_ut\":%.5f,\"my_ut\":%.5f,\"mz_ut\":%.5f,\"air_pressure_pa\":%.3f}\n",
    (unsigned long)seq++, (unsigned long)millis(),a.x,a.y,a.z,g.x,g.y,g.z,m.x,m.y,m.z,pressure);
}
