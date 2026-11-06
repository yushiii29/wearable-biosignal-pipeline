// One firmware for ESP32-D0WD-V3: select one module at a time over USB serial.
// Pressure -> GPIO34; ECG -> GPIO35; SEN0696 I2C -> SDA21/SCL22, address 0x4A.
// This firmware reads signals only. It does not control an air pump or diagnose symptoms.
#include <Arduino.h>
#include <Wire.h>
#include <DFRobot_Multi_DOF_IMU.h>

const uint32_t BAUD = 460800;
enum Module { LINK, PRESSURE, IMU, ECG };
Module active = LINK;
uint32_t seq = 0, previous = 0, lastError = 0;
bool imuReady = false;
char command[48];
size_t commandLength = 0;
DFRobot_Multi_DOF_IMU_I2C imu(DFRobot_Multi_DOF_IMU::eSensorModel10DOF, &Wire, 0x4A);

const char *moduleName(Module module) {
  switch (module) {
    case PRESSURE: return "pressure";
    case IMU: return "imu";
    case ECG: return "ecg";
    default: return "esp32";
  }
}

void selectModule(const char *name) {
  Module selected;
  if (!strcmp(name, "pressure")) selected = PRESSURE;
  else if (!strcmp(name, "imu")) selected = IMU;
  else if (!strcmp(name, "ecg")) selected = ECG;
  else if (!strcmp(name, "esp32")) selected = LINK;
  else { Serial.println("# error command unknown_module"); return; }

  if (selected != active) { seq = 0; previous = micros(); }
  active = selected;
  if (active == IMU && !imuReady) {
    Wire.begin(21, 22);
    Wire.setTimeOut(50);
    imuReady = imu.begin() &&
      imu.setSensorMode(DFRobot_Multi_DOF_IMU::eNormalMode) &&
      imu.setAccelRange(DFRobot_Multi_DOF_IMU::eAccelRange2G) &&
      imu.setGyroRange(DFRobot_Multi_DOF_IMU::eGyroRange250DPS);
    if (!imuReady) {
      Serial.println("# error imu init_failed: check power, SDA21, SCL22, I2C mode and address 0x4A");
      lastError = millis();
      return;
    }
  }
  Serial.printf("# selected %s firmware=sensor_switch_v1\n", moduleName(active));
}

void receiveCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      command[commandLength] = '\0';
      if (!strncmp(command, "SELECT ", 7)) selectModule(command + 7);
      commandLength = 0;
    } else if (c != '\r') {
      if (commandLength < sizeof(command)-1) command[commandLength++] = c;
      else commandLength = 0;
    }
  }
}

void setup() {
  Serial.begin(BAUD);
  analogReadResolution(12);
  pinMode(34, INPUT);
  pinMode(35, INPUT);
  Serial.println("# ready sensor_switch_v1: SELECT esp32|pressure|imu|ecg");
}

void loop() {
  receiveCommands();
  const uint32_t interval = active == ECG ? 4000 : active == PRESSURE ? 50000 : active == IMU ? 40000 : 100000;
  uint32_t now = micros();
  if ((uint32_t)(now-previous) < interval) return;
  previous = now;
  if (active == IMU) {
    if (!imuReady) {
      if ((uint32_t)(millis()-lastError) > 1000) {
        Serial.println("# error imu not_ready: reselect after checking I2C wiring");
        lastError = millis();
      }
      return;
    }
    DFRobot_Multi_DOF_IMU::sSensorData_t a, g, m;
    float pressure;
    if (!imu.get10dofData(&a, &g, &m, &pressure, false)) {
      if ((uint32_t)(millis()-lastError) > 1000) {
        Serial.println("# error imu read_failed"); lastError = millis();
      }
      return;
    }
    // I2C polling is blocking; timestamps reflect actual reads, not a claimed 50 Hz.
    Serial.printf("{\"v\":1,\"kind\":\"imu\",\"seq\":%lu,\"t_ms\":%lu,\"ax_g\":%.5f,\"ay_g\":%.5f,\"az_g\":%.5f,\"gx_dps\":%.5f,\"gy_dps\":%.5f,\"gz_dps\":%.5f,\"mx_ut\":%.5f,\"my_ut\":%.5f,\"mz_ut\":%.5f,\"air_pressure_pa\":%.3f}\n",
      (unsigned long)seq++, (unsigned long)millis(), a.x,a.y,a.z,g.x,g.y,g.z,m.x,m.y,m.z,pressure);
  } else if (active == PRESSURE || active == ECG) {
    int value = analogRead(active == PRESSURE ? 34 : 35);
    Serial.printf("{\"v\":1,\"kind\":\"%s\",\"seq\":%lu,\"t_ms\":%lu,\"%s\":%d}\n",
      moduleName(active), (unsigned long)seq++, (unsigned long)millis(),
      active == PRESSURE ? "pressure_adc" : "ecg_adc", value);
  } else {
    uint32_t value = seq;
    Serial.printf("{\"v\":1,\"kind\":\"esp32\",\"seq\":%lu,\"t_ms\":%lu,\"counter\":%lu}\n",
      (unsigned long)seq++, (unsigned long)millis(), (unsigned long)value);
  }
}
