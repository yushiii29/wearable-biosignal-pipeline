/**
 * @file  DFRobot_Multi_DOF_IMU.cpp
 * @brief  Define the implementation of DFRobot_Multi_DOF_IMU class
 * @n      This is a multi-axis IMU sensor that can be controlled through I2C/UART ports.
 * @n      It supports 6DOF (accelerometer + gyroscope), 9DOF (+ magnetometer), and 10DOF (+ barometer) sensors.
 * @copyright   Copyright (c) 2026 DFRobot Co.Ltd (http://www.dfrobot.com)
 * @license     The MIT License (MIT)
 * @author      [Martin](Martin@dfrobot.com)
 * @version     V1.0.0
 * @date        2026-01-16
 * @url         https://github.com/DFRobot/DFRobot_Multi_DOF_IMU
 */

#include "DFRobot_Multi_DOF_IMU.h"

#include <math.h>

/* ==================== Base Class Implementation ==================== */

DFRobot_Multi_DOF_IMU::DFRobot_Multi_DOF_IMU(eSensorModel_t model)
{
  _accelRange       = 8.0f;       // ±8g
  _gyroRange        = 2000.0f;    // ±2000dps
  _sensorModel      = model;
  _calibrated       = false;
  _sealevelAltitude = 0.0f;
}

DFRobot_Multi_DOF_IMU::~DFRobot_Multi_DOF_IMU() {}

uint16_t DFRobot_Multi_DOF_IMU::getRegAddr(uint16_t uartReg, uint16_t i2cReg)
{
  if (getCommMode() == DFRobot_Multi_DOF_IMU::eCommModeI2C) {
    return i2cReg;
  } else {
    return uartReg;
  }
}

bool DFRobot_Multi_DOF_IMU::begin(void)
{
  uint16_t pid    = 0;
  uint16_t pidReg = getRegAddr(REG_I_PID, REG_I2C_PID);
  uint8_t  ret    = readReg(pidReg, &pid, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to read product ID");
    return false;
  }

  // Check compatibility: product ID >= configured model (backward compatible)
  if (pid < (uint16_t)_sensorModel) {
    DBG("Product ID incompatible. Required: 0x");
    DBG((uint16_t)_sensorModel, HEX);
    DBG(" or higher, Got: 0x");
    DBG(pid, HEX);
    return false;
  }

  DBG("Sensor initialized successfully, Product ID: 0x");
  DBG(pid, HEX);
  DBG(", Configured model: 0x");
  DBG((uint16_t)_sensorModel, HEX);
  return true;
}

bool DFRobot_Multi_DOF_IMU::setAccelRange(eAccelRange_t range)
{
  if (range > eAccelRange16G) {
    DBG("Invalid accel range");
    return false;
  }

  switch (range) {
    case eAccelRange2G:
      _accelRange = 2.0f;
      break;
    case eAccelRange4G:
      _accelRange = 4.0f;
      break;
    case eAccelRange8G:
      _accelRange = 8.0f;
      break;
    case eAccelRange16G:
      _accelRange = 16.0f;
      break;
    default:
      _accelRange = 2.0f;
      return false;
  }

  uint16_t rangeValue    = (uint16_t)range;
  uint16_t accelRangeReg = getRegAddr(REG_H_ACC_RANGE_CONF, REG_I2C_ACC_RANGE_CONF);
  uint8_t  ret           = writeReg(accelRangeReg, &rangeValue, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to set accel range");
    return false;
  }

  DBG("Accel range set successfully");
  return true;
}

bool DFRobot_Multi_DOF_IMU::setGyroRange(eGyroRange_t range)
{
  if (range > eGyroRange2000DPS) {
    DBG("Invalid gyro range");
    return false;
  }

  switch (range) {
    case eGyroRange125DPS:
      _gyroRange = 125.0f;
      break;
    case eGyroRange250DPS:
      _gyroRange = 250.0f;
      break;
    case eGyroRange500DPS:
      _gyroRange = 500.0f;
      break;
    case eGyroRange1000DPS:
      _gyroRange = 1000.0f;
      break;
    case eGyroRange2000DPS:
      _gyroRange = 2000.0f;
      break;
    default:
      _gyroRange = 250.0f;
      return false;
  }

  uint16_t rangeValue   = (uint16_t)range;
  uint16_t gyroRangeReg = getRegAddr(REG_H_GYR_RANGE_CONF, REG_I2C_GYR_RANGE_CONF);
  uint8_t  ret          = writeReg(gyroRangeReg, &rangeValue, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to set gyro range");
    return false;
  }

  DBG("Gyro range set successfully");
  return true;
}

bool DFRobot_Multi_DOF_IMU::setSensorMode(eSensorMode_t mode)
{
  if (mode > eHighPerformanceMode) {
    DBG("Invalid sensor mode");
    return false;
  }

  uint16_t modeValue      = (uint16_t)mode;
  uint16_t sensorsModeReg = getRegAddr(REG_H_SENSORS_MODE, REG_I2C_SENSORS_MODE);
  uint8_t  ret            = writeReg(sensorsModeReg, &modeValue, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to set sensor mode");
    return false;
  }

  DBG("Sensor mode set successfully");
  return true;
}

bool DFRobot_Multi_DOF_IMU::reset(void)
{
  uint16_t resetValue = 0x0001;
  uint16_t resetReg   = getRegAddr(REG_H_SENSORS_RESET, REG_I2C_SENSORS_RESET);
  uint8_t  ret        = writeReg(resetReg, &resetValue, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to reset sensor");
    return false;
  }

  _accelRange = 8.0f;
  _gyroRange  = 2000.0f;

  DBG("Sensor reset successfully");
  return true;
}

uint8_t DFRobot_Multi_DOF_IMU::read6AxisRawBytes(uint8_t *data)
{
  uint16_t accDataXReg = getRegAddr(REG_I_ACC_DATA_X, REG_I2C_ACC_DATA_X);
  uint8_t  ret         = readReg(accDataXReg, data, 12);
  if (ret != RET_CODE_OK) {
    DBG("Failed to read 6DOF data");
    return ret;
  }

  return RET_CODE_OK;
}

float DFRobot_Multi_DOF_IMU::lsbToG(int16_t val, float gRange)
{
  float halfScale = 32768.0f;    // 16-bit resolution, half scale
  return (val * gRange) / halfScale;
}

float DFRobot_Multi_DOF_IMU::lsbToDps(int16_t val, float dpsRange)
{
  float halfScale = 32768.0f;    // 16-bit resolution, half scale
  return (val * dpsRange) / halfScale;
}

bool DFRobot_Multi_DOF_IMU::get6AxisRawData(sImuRawData_t *data)
{
  if (data == nullptr) {
    return false;
  }

  uint8_t rawData[12];
  if (read6AxisRawBytes(rawData) != RET_CODE_OK) {
    return false;
  }

  // Parse little-endian 16-bit data: accel bytes 0-5, gyro bytes 6-11
  data->accelX = (int16_t)(rawData[0] | (rawData[1] << 8));
  data->accelY = (int16_t)(rawData[2] | (rawData[3] << 8));
  data->accelZ = (int16_t)(rawData[4] | (rawData[5] << 8));

  data->gyroX = (int16_t)(rawData[6] | (rawData[7] << 8));
  data->gyroY = (int16_t)(rawData[8] | (rawData[9] << 8));
  data->gyroZ = (int16_t)(rawData[10] | (rawData[11] << 8));

  return true;
}

bool DFRobot_Multi_DOF_IMU::get6dofData(sSensorData_t *accel, sSensorData_t *gyro)
{
  if (accel == nullptr || gyro == nullptr) {
    return false;
  }

  sImuRawData_t rawData;
  if (!get6AxisRawData(&rawData)) {
    return false;
  }

  gyro->x = lsbToDps(rawData.gyroX, _gyroRange);
  gyro->y = lsbToDps(rawData.gyroY, _gyroRange);
  gyro->z = lsbToDps(rawData.gyroZ, _gyroRange);

  accel->x = lsbToG(rawData.accelX, _accelRange);
  accel->y = lsbToG(rawData.accelY, _accelRange);
  accel->z = lsbToG(rawData.accelZ, _accelRange);

  return true;
}

uint8_t DFRobot_Multi_DOF_IMU::readMagRawBytes(uint8_t *data)
{
  uint16_t magDataXLowReg = getRegAddr(REG_I_MAG_DATA_X_LOW_WORD, REG_I2C_MAG_DATA_X_LOW_WORD);
  uint8_t  ret            = readReg(magDataXLowReg, data, 12);
  if (ret != RET_CODE_OK) {
    DBG("Failed to read magnetometer data");
    return ret;
  }

  return RET_CODE_OK;
}

bool DFRobot_Multi_DOF_IMU::get9dofData(sSensorData_t *accel, sSensorData_t *gyro, sSensorData_t *mag)
{
  if (accel == nullptr || gyro == nullptr || mag == nullptr) {
    return false;
  }

  if (!get6dofData(accel, gyro)) {
    return false;
  }

  uint8_t magRawData[12];
  if (readMagRawBytes(magRawData) != RET_CODE_OK) {
    return false;
  }

  // Parse little-endian int32 data (unit: 0.01uT)
  // Note: Must cast to uint32_t before shifting to avoid overflow on AVR (16-bit int)
  int32_t magX = (int32_t)((uint32_t)magRawData[0] | ((uint32_t)magRawData[1] << 8) | ((uint32_t)magRawData[2] << 16) | ((uint32_t)magRawData[3] << 24));
  int32_t magY = (int32_t)((uint32_t)magRawData[4] | ((uint32_t)magRawData[5] << 8) | ((uint32_t)magRawData[6] << 16) | ((uint32_t)magRawData[7] << 24));
  int32_t magZ = (int32_t)((uint32_t)magRawData[8] | ((uint32_t)magRawData[9] << 8) | ((uint32_t)magRawData[10] << 16) | ((uint32_t)magRawData[11] << 24));

  // Convert to physical units (uT)
  mag->x = (float)magX * 0.01f;
  mag->y = (float)magY * 0.01f;
  mag->z = (float)magZ * 0.01f;

  return true;
}

uint8_t DFRobot_Multi_DOF_IMU::readPressRawBytes(uint8_t *data)
{
  uint16_t pressDataLowReg = getRegAddr(REG_I_PRESS_DATA_LOW_WORD, REG_I2C_PRESS_DATA_LOW_WORD);
  uint8_t  ret             = readReg(pressDataLowReg, data, 4);
  if (ret != RET_CODE_OK) {
    DBG("Failed to read pressure data");
    return ret;
  }

  return RET_CODE_OK;
}

float DFRobot_Multi_DOF_IMU::calculateAltitude(float pressure)
{
  // Barometric formula (align with BMP58X): h = 44307.7 * (1 - (P/P0)^0.190284)
  const float seaLevelPressure = 101325.0f;    // Standard sea level pressure (Pa)
  return 44307.7f * (1.0f - pow(pressure / seaLevelPressure, 0.190284f));
}

bool DFRobot_Multi_DOF_IMU::get10dofData(sSensorData_t *accel, sSensorData_t *gyro, sSensorData_t *mag, float *pressure, bool calcAltitude)
{
  if (accel == nullptr || gyro == nullptr || mag == nullptr || pressure == nullptr) {
    return false;
  }

  if (!get9dofData(accel, gyro, mag)) {
    return false;
  }

  uint8_t pressRawData[4];
  if (readPressRawBytes(pressRawData) != RET_CODE_OK) {
    return false;
  }

  // Parse little-endian int32 data
  // Note: Must cast to uint32_t before shifting to avoid overflow on AVR (16-bit int)
  int32_t pressRaw      = (int32_t)((uint32_t)pressRawData[0] | ((uint32_t)pressRawData[1] << 8) | ((uint32_t)pressRawData[2] << 16) | ((uint32_t)pressRawData[3] << 24));
  float   pressureValue = (float)pressRaw;

  // Pressure: always return raw. Altitude: when calibrated, use sea-level adjusted pressure for formula (same as BMP58X).
  if (calcAltitude) {
    float pressureForAlt = pressureValue;
    if (_calibrated) {
      const float STANDARD_SEA_LEVEL_PRESSURE_PA = 101325.0f;
      float       seaLevelPressPa                = pressureValue / pow(1.0f - (_sealevelAltitude / 44307.7f), 5.255302f);
      pressureForAlt                             = pressureValue - seaLevelPressPa + STANDARD_SEA_LEVEL_PRESSURE_PA;
    }
    *pressure = calculateAltitude(pressureForAlt);
  } else {
    *pressure = pressureValue;
  }
  return true;
}

bool DFRobot_Multi_DOF_IMU::intTypeToMacroValue(eImuIntPin_t pin, eIntType_t intType, uint8_t *macroValue)
{
  if (macroValue == nullptr) {
    return false;
  }

  // Validate pin and intType combination based on value ranges
  if (pin == eImuIntPin1 || pin == eImuIntPin2) {
    // INT1/INT2: only allow eInt1_2Disable (0x00) to eInt1_2Tilt (0x09)
    if (intType < eInt1_2Disable || intType > eInt1_2Tilt) {
      DBG("Invalid interrupt type for INT1/INT2");
      return false;
    }
    // Map unified enum to macro value (direct mapping for INT1/INT2)
    *macroValue = (uint8_t)intType;
  } else if (pin == eImuIntPin3) {
    // INT3: only allow eInt3Disable (0x10) to eInt3DataReady (0x11)
    if (intType < eInt3Disable || intType > eInt3DataReady) {
      DBG("Invalid interrupt type for INT3");
      return false;
    }
    // Map unified enum to macro value (subtract 0x10 to get 0x00-0x01)
    *macroValue = (uint8_t)(intType - 0x10);
  } else if (pin == eImuIntPin4) {
    // INT4: only allow eInt4Disable (0x20) to eInt4PressureOOR (0x22)
    if (intType < eInt4Disable || intType > eInt4PressureOOR) {
      DBG("Invalid interrupt type for INT4");
      return false;
    }
    // Map unified enum to macro value (subtract 0x20 to get 0x00-0x02)
    *macroValue = (uint8_t)(intType - 0x20);
  } else {
    DBG("Invalid interrupt pin");
    return false;
  }

  return true;
}

bool DFRobot_Multi_DOF_IMU::setInt(eImuIntPin_t pin, eIntType_t intType)
{
  if (pin == eImuIntPinNone || pin > eImuIntPin4) {
    DBG("Invalid interrupt pin");
    return false;
  }

  uint8_t macroValue;
  if (!intTypeToMacroValue(pin, intType, &macroValue)) {
    return false;
  }

  uint16_t intConfig = (uint16_t)macroValue;
  uint16_t confReg;

  switch (pin) {
    case eImuIntPin1:
      confReg = getRegAddr(REG_H_INT1_CONF, REG_I2C_INT1_CONF);
      break;
    case eImuIntPin2:
      confReg = getRegAddr(REG_H_INT2_CONF, REG_I2C_INT2_CONF);
      break;
    case eImuIntPin3:
      confReg = getRegAddr(REG_H_INT3_CONF, REG_I2C_INT3_CONF);
      break;
    case eImuIntPin4:
      confReg = getRegAddr(REG_H_INT4_CONF, REG_I2C_INT4_CONF);
      break;
    default:
      DBG("Invalid interrupt pin");
      return false;
  }

  uint8_t ret = writeReg(confReg, &intConfig, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to configure interrupt");
    return false;
  }

  DBG("Interrupt configured successfully");
  return true;
}

uint16_t DFRobot_Multi_DOF_IMU::getTap(void)
{
  uint16_t tapData    = 0;
  uint16_t tapDataReg = getRegAddr(REG_I_INT_TAP_DATA, REG_I2C_INT_TAP_DATA);
  uint8_t  ret        = readReg(tapDataReg, &tapData, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to read tap data");
    return 0;
  }

  return tapData;
}

uint16_t DFRobot_Multi_DOF_IMU::getOrientation(void)
{
  uint16_t orientData    = 0;
  uint16_t orientDataReg = getRegAddr(REG_I_INT_ORIENTATION_DATA, REG_I2C_INT_ORIENTATION_DATA);
  uint8_t  ret           = readReg(orientDataReg, &orientData, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to read orientation data");
    return 0;
  }

  return orientData;
}

uint32_t DFRobot_Multi_DOF_IMU::getStepCount(void)
{
  uint32_t stepCount      = 0;
  uint16_t stepDataLowReg = getRegAddr(REG_I_INT_STEP_DATA_LOW_WORD, REG_I2C_INT_STEP_DATA_LOW_WORD);
  uint8_t  ret            = readReg(stepDataLowReg, &stepCount, 4);

  if (ret != RET_CODE_OK) {
    DBG("Failed to read step counter data");
    return 0;
  }

  return stepCount;
}

bool DFRobot_Multi_DOF_IMU::calibrateAltitude(float altitude)
{
  bool ret = false;
  if (altitude > 0) {
    ret               = true;
    _calibrated       = true;
    _sealevelAltitude = altitude;
  }
  return ret;
}

bool DFRobot_Multi_DOF_IMU::setPressOOR(uint32_t threshold, uint8_t range, ePressOORCountLimit_t countLimit)
{
  if (countLimit > ePressOORCountLimit15) {
    DBG("Invalid press OOR count limit");
    return false;
  }

  // Write threshold low word
  uint16_t thresholdLow = (uint16_t)(threshold & 0xFFFF);
  uint16_t thrLowReg    = getRegAddr(REG_H_PRESS_OOR_THR_LOW_WORD_CONF, REG_I2C_PRESS_OOR_THR_LOW_WORD_CONF);
  uint8_t  ret          = writeReg(thrLowReg, &thresholdLow, 2);
  if (ret != RET_CODE_OK) {
    DBG("Failed to write OOR threshold low word");
    return false;
  }
  delay(10);

  // Write threshold high word
  uint16_t thresholdHigh = (uint16_t)((threshold >> 16) & 0xFFFF);
  uint16_t thrHighReg    = getRegAddr(REG_H_PRESS_OOR_THR_HIGH_WORD_CONF, REG_I2C_PRESS_OOR_THR_HIGH_WORD_CONF);
  ret                    = writeReg(thrHighReg, &thresholdHigh, 2);
  if (ret != RET_CODE_OK) {
    DBG("Failed to write OOR threshold high word");
    return false;
  }
  delay(10);

  // Write range
  uint16_t rangeValue = (uint16_t)range;
  uint16_t rangeReg   = getRegAddr(REG_H_PRESS_OOR_RANGE_CONF, REG_I2C_PRESS_OOR_RANGE_CONF);
  ret                 = writeReg(rangeReg, &rangeValue, 2);
  if (ret != RET_CODE_OK) {
    DBG("Failed to write OOR range");
    return false;
  }
  delay(10);

  // Write count limit
  uint16_t countLimitValue = (uint16_t)countLimit;
  uint16_t cntLimReg       = getRegAddr(REG_H_PRESS_OOR_CNT_LIM_CONF, REG_I2C_PRESS_OOR_CNT_LIM_CONF);
  ret                      = writeReg(cntLimReg, &countLimitValue, 2);

  if (ret != RET_CODE_OK) {
    DBG("Failed to configure pressure OOR");
    return false;
  }

  delay(50);    // Allow firmware processing time

  DBG("Pressure OOR configured successfully");
  return true;
}

/* ==================== I2C Subclass Implementation ==================== */

DFRobot_Multi_DOF_IMU_I2C::DFRobot_Multi_DOF_IMU_I2C(eSensorModel_t model, TwoWire *pWire, uint8_t addr) : DFRobot_Multi_DOF_IMU(model)
{
  _pWire   = pWire;
  _i2cAddr = addr;
}

DFRobot_Multi_DOF_IMU_I2C::~DFRobot_Multi_DOF_IMU_I2C() {}

DFRobot_Multi_DOF_IMU::eCommMode_t DFRobot_Multi_DOF_IMU_I2C::getCommMode(void)
{
  return DFRobot_Multi_DOF_IMU::eCommModeI2C;
}

bool DFRobot_Multi_DOF_IMU_I2C::begin(void)
{
  _pWire->begin();
  _pWire->setClock(400000);    // 400kHz I2C clock

  return DFRobot_Multi_DOF_IMU::begin();
}

uint8_t DFRobot_Multi_DOF_IMU_I2C::writeReg(uint16_t reg, void *data, uint8_t len)
{
  uint8_t *pData = (uint8_t *)data;

  _pWire->beginTransmission(_i2cAddr);

  // Write register address (16-bit, little-endian)
  _pWire->write((uint8_t)(reg & 0xFF));
  _pWire->write((uint8_t)((reg >> 8) & 0xFF));

  for (uint8_t i = 0; i < len; i++) {
    _pWire->write(pData[i]);
  }

  if (_pWire->endTransmission() != 0) {
    DBG("I2C write failed");
    return RET_CODE_ERROR;
  }

  return RET_CODE_OK;
}

uint8_t DFRobot_Multi_DOF_IMU_I2C::readReg(uint16_t reg, void *data, uint8_t len, eRegType_t regType)
{
  (void)regType;    // Unused in I2C mode, all registers share the same address space

  uint8_t *pData = (uint8_t *)data;

  // Phase 1: Write register address
  _pWire->beginTransmission(_i2cAddr);
  _pWire->write((uint8_t)(reg & 0xFF));
  _pWire->write((uint8_t)((reg >> 8) & 0xFF));

  if (_pWire->endTransmission() != 0) {
    DBG("I2C write register address failed");
    return RET_CODE_ERROR;
  }

  delay(10);    // Allow firmware time to read sensor data

  // Phase 2: Read data
  _pWire->requestFrom(_i2cAddr, len);

  if (_pWire->available() < len) {
    DBG("I2C read failed, not enough data");
    return RET_CODE_ERROR;
  }

  for (uint8_t i = 0; i < len; i++) {
    pData[i] = _pWire->read();
  }

  return RET_CODE_OK;
}

/* ==================== UART Subclass Implementation ==================== */

#if defined(ARDUINO_AVR_UNO) || defined(ESP8266)
DFRobot_Multi_DOF_IMU_UART::DFRobot_Multi_DOF_IMU_UART(eSensorModel_t model, SoftwareSerial *sSerial, uint32_t baud, uint8_t addr) : DFRobot_Multi_DOF_IMU(model), DFRobot_RTU(sSerial)
{
  _serial     = sSerial;
  _baud       = baud;
  _deviceAddr = addr;
  _rxPin      = 0;
  _txPin      = 0;
}
#else
DFRobot_Multi_DOF_IMU_UART::DFRobot_Multi_DOF_IMU_UART(eSensorModel_t model, HardwareSerial *hSerial, uint32_t baud, uint8_t addr, uint8_t rxPin, uint8_t txPin) : DFRobot_Multi_DOF_IMU(model), DFRobot_RTU(hSerial)
{
  _serial     = hSerial;
  _baud       = baud;
  _deviceAddr = addr;
  _rxPin      = rxPin;
  _txPin      = txPin;
}
#endif

DFRobot_Multi_DOF_IMU_UART::~DFRobot_Multi_DOF_IMU_UART() {}

DFRobot_Multi_DOF_IMU::eCommMode_t DFRobot_Multi_DOF_IMU_UART::getCommMode(void)
{
  return DFRobot_Multi_DOF_IMU::eCommModeUART;
}

bool DFRobot_Multi_DOF_IMU_UART::begin(void)
{
#if defined(ARDUINO_AVR_UNO) || defined(ESP8266)
  ((SoftwareSerial *)_serial)->begin(_baud);
#elif defined(ESP32)
  if (_rxPin != 0 && _txPin != 0) {
    ((HardwareSerial *)_serial)->begin(_baud, SERIAL_8N1, _rxPin, _txPin);
  } else {
    ((HardwareSerial *)_serial)->begin(_baud);
  }
#else
  ((HardwareSerial *)_serial)->begin(_baud);
#endif

  setTimeoutTimeMs(500);    // Extended timeout for sensor initialization

  return DFRobot_Multi_DOF_IMU::begin();
}

uint8_t DFRobot_Multi_DOF_IMU_UART::writeReg(uint16_t reg, void *data, uint8_t len)
{
  if (data == nullptr) {
    DBG("UART writeReg: invalid parameters");
    return RET_CODE_ERROR;
  }

  uint8_t *pData = (uint8_t *)data;

  if (len == 2) {
    // Write single holding register (function code 0x06)
    uint16_t value = (uint16_t)(pData[0] | (pData[1] << 8));    // Little-endian
    uint8_t  ret   = writeHoldingRegister(_deviceAddr, reg, value);

    if (ret == 0) {
      return RET_CODE_OK;
    } else {
      DBG("UART writeReg failed, error code: 0x");
      DBG(ret, HEX);
      return RET_CODE_ERROR;
    }
  } else if (len > 2 && (len % 2 == 0)) {
    // Write multiple holding registers (function code 0x10)
    uint8_t   regCount = len / 2;
    uint16_t *values   = new uint16_t[regCount];

    for (uint8_t i = 0; i < regCount; i++) {
      values[i] = (uint16_t)(pData[i * 2] | (pData[i * 2 + 1] << 8));    // Little-endian
    }

    // Write registers sequentially
    uint8_t ret = RET_CODE_OK;
    for (uint8_t i = 0; i < regCount; i++) {
      uint8_t result = writeHoldingRegister(_deviceAddr, reg + i, values[i]);
      if (result != 0) {
        ret = RET_CODE_ERROR;
        break;
      }
      delay(10);
    }

    delete[] values;
    return ret;
  } else {
    DBG("UART writeReg: invalid data length");
    return RET_CODE_ERROR;
  }
}

uint8_t DFRobot_Multi_DOF_IMU_UART::readReg(uint16_t reg, void *data, uint8_t len, eRegType_t regType)
{
  if (data == nullptr) {
    DBG("UART readReg: invalid parameters");
    return RET_CODE_ERROR;
  }

  uint8_t *pData = (uint8_t *)data;

  // Use regType parameter to determine which Modbus function code to use
  // eInputReg: Modbus function code 0x04 (read input registers)
  // eHoldingReg: Modbus function code 0x03 (read holding registers)
  bool isInputRegister = (regType == eInputReg);

  if (len == 2) {
    uint16_t value = 0;

    if (isInputRegister) {
      value = readInputRegister(_deviceAddr, reg);
    } else {
      value = readHoldingRegister(_deviceAddr, reg);
    }

    // Convert to little-endian
    pData[0] = (uint8_t)(value & 0xFF);
    pData[1] = (uint8_t)((value >> 8) & 0xFF);

    return RET_CODE_OK;
  } else if (len > 2 && (len % 2 == 0)) {
    uint8_t regCount = len / 2;

    for (uint8_t i = 0; i < regCount; i++) {
      uint16_t value = 0;

      if (isInputRegister) {
        value = readInputRegister(_deviceAddr, reg + i);
      } else {
        value = readHoldingRegister(_deviceAddr, reg + i);
      }

      pData[i * 2]     = (uint8_t)(value & 0xFF);
      pData[i * 2 + 1] = (uint8_t)((value >> 8) & 0xFF);

      delay(5);
    }

    return RET_CODE_OK;
  } else {
    // Handle odd-length reads
    if (len == 1) {
      uint16_t value = 0;

      if (isInputRegister) {
        value = readInputRegister(_deviceAddr, reg);
      } else {
        value = readHoldingRegister(_deviceAddr, reg);
      }

      pData[0] = (uint8_t)(value & 0xFF);
      return RET_CODE_OK;
    } else {
      uint8_t regCount = (len + 1) / 2;

      for (uint8_t i = 0; i < regCount; i++) {
        uint16_t value = 0;

        if (isInputRegister) {
          value = readInputRegister(_deviceAddr, reg + i);
        } else {
          value = readHoldingRegister(_deviceAddr, reg + i);
        }

        uint8_t byteOffset = i * 2;
        if (byteOffset < len) {
          pData[byteOffset] = (uint8_t)(value & 0xFF);
        }
        if (byteOffset + 1 < len) {
          pData[byteOffset + 1] = (uint8_t)((value >> 8) & 0xFF);
        }

        delay(5);
      }

      return RET_CODE_OK;
    }
  }
}
