// Local Wi-Fi hotspot + USB. Same wiring as 05_sensor_switch; one module at a time.
// Reads raw signals only: no air-pump control, diagnosis, or electrical safety certification.
#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <WebServer.h>
#include <esp_system.h>
#include <DFRobot_Multi_DOF_IMU.h>

const char *FIRMWARE = "sensor_wifi_v1";
const char *PROTOCOL = "wearable_wifi_v1";
const char *AP_PASSWORD = "Wearable2026";
const uint32_t BAUD = 460800, LEASE_MS = 8000;
const size_t CAPACITY = 1024, BATCH = 64;
enum Module { LINK, PRESSURE, IMU, ECG };
struct Sample {
  uint32_t seq, t_ms;
  int adc;
  float values[10];
};
Sample ringBuffer[CAPACITY];
Module active = LINK;
bool running = false, serialMode = false, imuReady = false;
uint32_t nextSeq = 0, oldestSeq = 0, streamId = 0, previous = 0, overruns = 0, lastPoll = 0;
char owner[33] = "", deviceId[24], bootId[12], ssid[32], errorMessage[128] = "";
SemaphoreHandle_t stateMutex;
WebServer server(80);
DFRobot_Multi_DOF_IMU_I2C imu(DFRobot_Multi_DOF_IMU::eSensorModel10DOF, &Wire, 0x4A);

const char *moduleName(Module module) {
  switch (module) {
    case PRESSURE: return "pressure";
    case IMU: return "imu";
    case ECG: return "ecg";
    default: return "esp32";
  }
}
bool parseModule(const String &name, Module &module) {
  if (name == "esp32") module = LINK;
  else if (name == "pressure") module = PRESSURE;
  else if (name == "imu") module = IMU;
  else if (name == "ecg") module = ECG;
  else return false;
  return true;
}
uint32_t intervalUs() {
  return active == ECG ? 4000 : active == PRESSURE ? 50000 : active == IMU ? 40000 : 100000;
}
bool validToken(const String &token) {
  if (token.length() != 32) return false;
  for (size_t i = 0; i < token.length(); ++i) if (!isxdigit(token[i])) return false;
  return true;
}
// Call with mutex held. I2C initialization and reads never run concurrently.
bool beginModule(Module selected) {
  running = false;
  active = selected;
  nextSeq = oldestSeq = overruns = 0;
  ++streamId;
  errorMessage[0] = '\0';
  if (active == IMU && !imuReady) {
    Wire.begin(21, 22);
    Wire.setTimeOut(50);
    imuReady = imu.begin() &&
      imu.setSensorMode(DFRobot_Multi_DOF_IMU::eNormalMode) &&
      imu.setAccelRange(DFRobot_Multi_DOF_IMU::eAccelRange2G) &&
      imu.setGyroRange(DFRobot_Multi_DOF_IMU::eGyroRange250DPS);
    if (!imuReady) {
      strlcpy(errorMessage, "imu init_failed: check SDA21/SCL22, power and address 0x4A", sizeof(errorMessage));
      return false;
    }
  }
  previous = micros();
  lastPoll = millis();
  running = true;
  return true;
}
String packetJson(const Sample &sample, Module kind) {
  char line[512];
  if (kind == IMU) {
    const float *v = sample.values;
    snprintf(line, sizeof(line),
      "{\"v\":1,\"kind\":\"imu\",\"seq\":%lu,\"t_ms\":%lu,\"ax_g\":%.5f,\"ay_g\":%.5f,\"az_g\":%.5f,\"gx_dps\":%.5f,\"gy_dps\":%.5f,\"gz_dps\":%.5f,\"mx_ut\":%.5f,\"my_ut\":%.5f,\"mz_ut\":%.5f,\"air_pressure_pa\":%.3f}",
      (unsigned long)sample.seq, (unsigned long)sample.t_ms,
      v[0],v[1],v[2],v[3],v[4],v[5],v[6],v[7],v[8],v[9]);
  } else {
    const char *field = kind == ECG ? "ecg_adc" : kind == PRESSURE ? "pressure_adc" : "counter";
    uint32_t value = kind == LINK ? sample.seq : (uint32_t)sample.adc;
    snprintf(line, sizeof(line), "{\"v\":1,\"kind\":\"%s\",\"seq\":%lu,\"t_ms\":%lu,\"%s\":%lu}",
      moduleName(kind), (unsigned long)sample.seq, (unsigned long)sample.t_ms, field, (unsigned long)value);
  }
  return String(line);
}
// Return a coherent state snapshot. Caller holds mutex.
String stateJson() {
  String state;
  state.reserve(512);
  state = "{\"protocol\":\""; state += PROTOCOL;
  state += "\",\"firmware\":\""; state += FIRMWARE;
  state += "\",\"device_id\":\""; state += deviceId;
  state += "\",\"boot_id\":\""; state += bootId;
  state += "\",\"ssid\":\""; state += ssid;
  state += "\",\"kind\":\""; state += moduleName(active);
  state += "\",\"stream_id\":"; state += streamId;
  state += ",\"oldest_seq\":"; state += oldestSeq;
  state += ",\"next_seq\":"; state += nextSeq;
  state += ",\"sampling_overruns\":"; state += overruns;
  state += ",\"running\":"; state += running ? "true" : "false";
  state += ",\"error\":\""; state += errorMessage; state += "\"}";
  return state;
}
void reply(int code, const String &body) {
  server.sendHeader("Cache-Control", "no-store");
  server.send(code, "application/json", body);
}
void fail(int code, const char *message) {
  reply(code, String("{\"protocol\":\"") + PROTOCOL + "\",\"error\":\"" + message + "\"}");
}
void setupHttp() {
  server.on("/status", HTTP_GET, []() {
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    String state = stateJson();
    xSemaphoreGive(stateMutex);
    reply(200, state);
  });
  server.on("/start", HTTP_POST, []() {
    Module selected;
    String token = server.arg("token");
    if (!parseModule(server.arg("kind"), selected) || !validToken(token)) { fail(400, "invalid_start"); return; }
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    if (running && (serialMode || token != owner || selected != active)) {
      xSemaphoreGive(stateMutex); fail(409, "device_busy"); return;
    }
    if (!running || token != owner) {
      strlcpy(owner, token.c_str(), sizeof(owner));
      serialMode = false;
      beginModule(selected);
    }
    lastPoll = millis();
    String state = stateJson();
    xSemaphoreGive(stateMutex);
    reply(200, state);
  });
  server.on("/samples", HTTP_GET, []() {
    String token = server.arg("token"), afterText = server.arg("after");
    char *end = nullptr;
    long long after = strtoll(afterText.c_str(), &end, 10);
    if (!validToken(token) || afterText.length() == 0 || *end != '\0' || after < -1 || after > UINT32_MAX) {
      fail(400, "invalid_cursor"); return;
    }
    Sample batch[BATCH];
    size_t count = 0;
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    if (serialMode || token != owner) { xSemaphoreGive(stateMutex); fail(409, "session_not_owned"); return; }
    lastPoll = millis();
    uint32_t cursor = (uint32_t)(after + 1);
    if (cursor < oldestSeq) cursor = oldestSeq;
    while (cursor < nextSeq && count < BATCH) batch[count++] = ringBuffer[cursor++ % CAPACITY];
    String state = stateJson();
    Module selected = active;
    xSemaphoreGive(stateMutex);
    state.remove(state.length()-1);
    state += ",\"samples\":[";
    for (size_t i = 0; i < count; ++i) { if (i) state += ','; state += packetJson(batch[i], selected); }
    state += "]}";
    reply(200, state);
  });
  server.on("/stop", HTTP_POST, []() {
    String token = server.arg("token");
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    if (!validToken(token) || serialMode || token != owner) {
      xSemaphoreGive(stateMutex); fail(409, "session_not_owned"); return;
    }
    running = false;
    String state = stateJson();
    xSemaphoreGive(stateMutex);
    reply(200, state);
  });
  server.onNotFound([]() { fail(404, "not_found"); });
  server.begin();
}
// Acquisition runs independently of HTTP response formatting/transmission.
void sampleTask(void *) {
  for (;;) {
    Sample sample = {};
    Module selected = LINK;
    bool printSerial = false;
    xSemaphoreTake(stateMutex, portMAX_DELAY);
    if (running && !serialMode && (uint32_t)(millis()-lastPoll) > LEASE_MS) {
      running = false;
      strlcpy(errorMessage, "receiver_timeout", sizeof(errorMessage));
    }
    uint32_t now = micros(), interval = intervalUs();
    if (running && (uint32_t)(now-previous) >= interval) {
      uint32_t late = (uint32_t)(now-previous)/interval;
      if (late > 1) overruns += late-1;
      previous = now;
      selected = active;
      bool ok = true;
      if (active == IMU) {
        DFRobot_Multi_DOF_IMU::sSensorData_t a, g, m;
        float pressure;
        ok = imu.get10dofData(&a, &g, &m, &pressure, false);
        if (ok) {
          float values[10] = {a.x,a.y,a.z,g.x,g.y,g.z,m.x,m.y,m.z,pressure};
          memcpy(sample.values, values, sizeof(values));
        }
      } else if (active == PRESSURE || active == ECG) sample.adc = analogRead(active == ECG ? 35 : 34);
      if (!ok) {
        running = false;
        strlcpy(errorMessage, "imu read_failed", sizeof(errorMessage));
      } else {
        sample.seq = nextSeq++;
        sample.t_ms = millis();
        ringBuffer[sample.seq % CAPACITY] = sample;
        if (nextSeq-oldestSeq > CAPACITY) oldestSeq = nextSeq-CAPACITY;
        printSerial = serialMode;
      }
    }
    xSemaphoreGive(stateMutex);
    if (printSerial) Serial.println(packetJson(sample, selected));
    vTaskDelay(1);
  }
}
void receiveSerial() {
  static char command[48];
  static size_t length = 0;
  while (Serial.available()) {
    char c = Serial.read();
    if (c == '\n') {
      command[length] = '\0'; length = 0;
      Module selected;
      if (!strcmp(command, "STOP")) {
        xSemaphoreTake(stateMutex, portMAX_DELAY);
        if (serialMode) running = false;
        xSemaphoreGive(stateMutex);
      } else if (!strncmp(command, "SELECT ", 7) && parseModule(command+7, selected)) {
        xSemaphoreTake(stateMutex, portMAX_DELAY);
        if (running && !serialMode) Serial.println("# error command wifi_busy");
        else {
          if (!running || selected != active) { serialMode = true; owner[0] = '\0'; beginModule(selected); }
          Serial.printf("# selected %s firmware=sensor_wifi_v1\n", moduleName(active));
          if (errorMessage[0]) Serial.printf("# error %s %s\n", moduleName(active), errorMessage);
        }
        xSemaphoreGive(stateMutex);
      }
    } else if (c != '\r' && length < sizeof(command)-1) command[length++] = c;
  }
}
void setup() {
  Serial.begin(BAUD);
  analogReadResolution(12);
  pinMode(34, INPUT); pinMode(35, INPUT);
  stateMutex = xSemaphoreCreateMutex();
  uint64_t mac = ESP.getEfuseMac();
  snprintf(deviceId, sizeof(deviceId), "%012llX", (unsigned long long)mac);
  snprintf(bootId, sizeof(bootId), "%08lX", (unsigned long)esp_random());
  snprintf(ssid, sizeof(ssid), "Wearable-%06lX", (unsigned long)(mac & 0xFFFFFF));
  WiFi.mode(WIFI_AP);
  WiFi.setSleep(false);
  if (!WiFi.softAP(ssid, AP_PASSWORD, 6, false, 1)) {
    Serial.println("# error wifi access_point_failed");
    return;
  }
  setupHttp();
  if (xTaskCreatePinnedToCore(sampleTask, "sensor_sample", 6144, nullptr, 2, nullptr, 1) != pdPASS) {
    strlcpy(errorMessage, "sampler_task_failed", sizeof(errorMessage));
    Serial.println("# error sampler_task_failed");
    return;
  }
  Serial.printf("# ready sensor_wifi_v1 ssid=%s address=http://192.168.4.1 device=%s\n", ssid, deviceId);
}
void loop() {
  server.handleClient();
  receiveSerial();
  delay(1);
}
