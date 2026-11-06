/**
 * @file  DFRobot_Multi_DOF_IMU.h
 * @brief  Define the infrastructure of DFRobot_Multi_DOF_IMU class
 * @n      This is a multi-axis IMU sensor that can be controlled through I2C/UART ports.
 * @n      It supports 6DOF (accelerometer + gyroscope), 9DOF (+ magnetometer), and 10DOF (+ barometer) sensors.
 * @copyright   Copyright (c) 2026 DFRobot Co.Ltd (http://www.dfrobot.com)
 * @license     The MIT License (MIT)
 * @author      [Martin](Martin@dfrobot.com)
 * @version     V1.0.0
 * @date        2026-01-16
 * @url         https://github.com/DFRobot/DFRobot_Multi_DOF_IMU
 */
#ifndef __DFROBOT_MULTI_DOF_IMU_H
#define __DFROBOT_MULTI_DOF_IMU_H

#include "Arduino.h"
#include "DFRobot_RTU.h"
#include "Wire.h"
#include "stdint.h"

// Debug macro definition
//#define ENABLE_DBG

#ifdef ENABLE_DBG
#define DBG(...)                 \
  {                              \
    Serial.print("[");           \
    Serial.print(__FUNCTION__);  \
    Serial.print("(): ");        \
    Serial.print(__LINE__);      \
    Serial.print(" ] ");         \
    Serial.println(__VA_ARGS__); \
  }
#else
#define DBG(...)
#endif

#if defined(ARDUINO_AVR_UNO) || defined(ESP8266)
#include "SoftwareSerial.h"
#else
#include "HardwareSerial.h"
#endif

/**
 * @class DFRobot_Multi_DOF_IMU
 * @brief DFRobot_Multi_DOF_IMU base class
 * @details Provides multi-axis IMU sensor data reading functionality, supporting 6DOF (accelerometer+gyroscope), 9DOF (+magnetometer), and 10DOF (+barometer) sensors
 */
class DFRobot_Multi_DOF_IMU {
private:
/** Sensor model (macro definitions reserved for backward compatibility) */
#define SENSOR_MODEL_6DOF  0x0006    ///< 6DOF IMU
#define SENSOR_MODEL_9DOF  0x0009    ///< 9DOF IMU
#define SENSOR_MODEL_10DOF 0x0010    ///< 10DOF IMU

public:
  /**
   * @enum eSensorModel_t
   * @brief Sensor model enumeration
   * @details Define supported sensor models
   */
  typedef enum {
    eSensorModel6DOF  = SENSOR_MODEL_6DOF,    ///< 6DOF IMU (accelerometer + gyroscope)
    eSensorModel9DOF  = SENSOR_MODEL_9DOF,    ///< 9DOF IMU (accelerometer + gyroscope + magnetometer)
    eSensorModel10DOF = SENSOR_MODEL_10DOF    ///< 10DOF IMU (accelerometer + gyroscope + magnetometer + barometer)
  } eSensorModel_t;

  /**
   * @enum eCommMode_t
   * @brief Communication mode enumeration
   * @details Define supported communication interface types
   */
  typedef enum {
    eCommModeUART = 0,    ///< UART communication mode (Modbus RTU)
    eCommModeI2C  = 1     ///< I2C communication mode
  } eCommMode_t;

  /**
   * @enum eRegType_t
   * @brief Register type enumeration (for UART Modbus mode)
   * @details Define register types for Modbus RTU protocol
   * @n In UART mode, input registers (function code 0x04) and holding registers (function code 0x03)
   * @n have overlapping address ranges, so this enum is needed to distinguish them.
   * @n In I2C mode, this parameter is ignored as there's only one register space.
   */
  typedef enum {
    eInputReg   = 0,    ///< Input register (read-only, Modbus function code 0x04)
    eHoldingReg = 1     ///< Holding register (read-write, Modbus function code 0x03/0x06)
  } eRegType_t;

/** IMU tap type return values */
#define TAP_TYPE_SINGLE 0x0001    ///< Single tap interrupt
#define TAP_TYPE_DOUBLE 0x0002    ///< Double tap interrupt
#define TAP_TYPE_TRIPLE 0x0003    ///< Triple tap interrupt

/** IMU orientation type (high byte) */
#define ORIENT_TYPE_PORTRAIT_UP     0x01    ///< Portrait upright
#define ORIENT_TYPE_LANDSCAPE_LEFT  0x02    ///< Landscape left
#define ORIENT_TYPE_LANDSCAPE_RIGHT 0x03    ///< Landscape right
#define ORIENT_TYPE_PORTRAIT_DOWN   0x04    ///< Portrait upside down

/** IMU face direction type (low byte) */
#define ORIENT_FACE_UP   0x00    ///< Face forward
#define ORIENT_FACE_DOWN 0x01    ///< Face backward

private:
/** Input registers (read-only) - Modbus function code 0x04 */
#define REG_I_VID                     0x0000    ///< Vendor ID (0x3343 = DFRobot)
#define REG_I_PID                     0x0001    ///< Product ID
#define REG_I_DEVICE_ADDR             0x0002    ///< Modbus device address
#define REG_I_RESERVED                0x0003    ///< Reserved
#define REG_I_VERIFY_AND_STOP         0x0004    ///< Serial port parity and stop bits
#define REG_I_FW_VERSION              0x0005    ///< Firmware version
#define REG_I_ACC_DATA_X              0x0006    ///< Accelerometer data X
#define REG_I_ACC_DATA_Y              0x0007    ///< Accelerometer data Y
#define REG_I_ACC_DATA_Z              0x0008    ///< Accelerometer data Z
#define REG_I_GYR_DATA_X              0x0009    ///< Gyroscope data X
#define REG_I_GYR_DATA_Y              0x000A    ///< Gyroscope data Y
#define REG_I_GYR_DATA_Z              0x000B    ///< Gyroscope data Z
#define REG_I_MAG_DATA_X_LOW_WORD     0x000C    ///< Magnetometer data X low word
#define REG_I_MAG_DATA_X_HIGH_WORD    0x000D    ///< Magnetometer data X high word
#define REG_I_MAG_DATA_Y_LOW_WORD     0x000E    ///< Magnetometer data Y low word
#define REG_I_MAG_DATA_Y_HIGH_WORD    0x000F    ///< Magnetometer data Y high word
#define REG_I_MAG_DATA_Z_LOW_WORD     0x0010    ///< Magnetometer data Z low word
#define REG_I_MAG_DATA_Z_HIGH_WORD    0x0011    ///< Magnetometer data Z high word
#define REG_I_PRESS_DATA_LOW_WORD     0x0012    ///< Pressure data low word
#define REG_I_PRESS_DATA_HIGH_WORD    0x0013    ///< Pressure data high word
#define REG_I_INT_STEP_DATA_LOW_WORD  0x0014    ///< 6DOF step counter data low word
#define REG_I_INT_STEP_DATA_HIGH_WORD 0x0015    ///< 6DOF step counter data high word
#define REG_I_INT_TAP_DATA            0x0016    ///< 6DOF tap data
#define REG_I_INT_ORIENTATION_DATA    0x0017    ///< 6DOF orientation data

/** Holding registers (read-write) - Modbus function code 0x03/0x06 */
#define REG_H_RESERVED                     0x0000    ///< Reserved
#define REG_H_RESERVED1                    0x0001    ///< Reserved 1
#define REG_H_RESERVED2                    0x0002    ///< Reserved 2
#define REG_H_BAUDRATE                     0x0003    ///< Serial port baud rate
#define REG_H_RESERVED3                    0x0004    ///< Reserved 3
#define REG_H_RESERVED4                    0x0005    ///< Reserved 4
#define REG_H_SENSORS_MODE                 0x0006    ///< Sensor operating mode
#define REG_H_SENSORS_RESET                0x0007    ///< Sensor factory reset
#define REG_H_ACC_RANGE_CONF               0x0008    ///< Accelerometer range configuration
#define REG_H_GYR_RANGE_CONF               0x0009    ///< Gyroscope range configuration
#define REG_H_PRESS_OOR_THR_LOW_WORD_CONF  0x000A    ///< Pressure OOR threshold low word configuration
#define REG_H_PRESS_OOR_THR_HIGH_WORD_CONF 0x000B    ///< Pressure OOR threshold high word configuration
#define REG_H_PRESS_OOR_RANGE_CONF         0x000C    ///< Pressure OOR range configuration
#define REG_H_PRESS_OOR_CNT_LIM_CONF       0x000D    ///< Pressure OOR count limit configuration
#define REG_H_INT1_CONF                    0x000E    ///< 6DOF interrupt 1 configuration
#define REG_H_INT2_CONF                    0x000F    ///< 6DOF interrupt 2 configuration
#define REG_H_INT3_CONF                    0x0010    ///< 9DOF interrupt configuration
#define REG_H_INT4_CONF                    0x0011    ///< 10DOF interrupt configuration

// I2C mode register addresses
#define REG_I2C_VID                          0x0000    ///< Vendor ID (0x3343 = DFRobot)
#define REG_I2C_PID                          0x0001    ///< Product ID
#define REG_I2C_FW_VERSION                   0x0002    ///< Firmware version
#define REG_I2C_DEVICE_ADDR                  0x0003    ///< I2C slave device address
#define REG_I2C_SENSORS_RESET                0x0004    ///< Sensor factory reset
#define REG_I2C_SENSORS_MODE                 0x0005    ///< Sensor operating mode
#define REG_I2C_ACC_RANGE_CONF               0x0006    ///< Accelerometer range configuration
#define REG_I2C_GYR_RANGE_CONF               0x0007    ///< Gyroscope range configuration
#define REG_I2C_PRESS_OOR_THR_LOW_WORD_CONF  0x0008    ///< Pressure OOR threshold low word configuration
#define REG_I2C_PRESS_OOR_THR_HIGH_WORD_CONF 0x0009    ///< Pressure OOR threshold high word configuration
#define REG_I2C_PRESS_OOR_RANGE_CONF         0x000A    ///< Pressure OOR range configuration
#define REG_I2C_PRESS_OOR_CNT_LIM_CONF       0x000B    ///< Pressure OOR count limit configuration
#define REG_I2C_INT1_CONF                    0x000C    ///< 6DOF interrupt 1 configuration
#define REG_I2C_INT2_CONF                    0x000D    ///< 6DOF interrupt 2 configuration
#define REG_I2C_INT3_CONF                    0x000E    ///< 9DOF interrupt configuration
#define REG_I2C_INT4_CONF                    0x000F    ///< 10DOF interrupt configuration
#define REG_I2C_ACC_DATA_X                   0x0010    ///< Accelerometer data X
#define REG_I2C_ACC_DATA_Y                   0x0011    ///< Accelerometer data Y
#define REG_I2C_ACC_DATA_Z                   0x0012    ///< Accelerometer data Z
#define REG_I2C_GYR_DATA_X                   0x0013    ///< Gyroscope data X
#define REG_I2C_GYR_DATA_Y                   0x0014    ///< Gyroscope data Y
#define REG_I2C_GYR_DATA_Z                   0x0015    ///< Gyroscope data Z
#define REG_I2C_MAG_DATA_X_LOW_WORD          0x0016    ///< Magnetometer data X low word
#define REG_I2C_MAG_DATA_X_HIGH_WORD         0x0017    ///< Magnetometer data X high word
#define REG_I2C_MAG_DATA_Y_LOW_WORD          0x0018    ///< Magnetometer data Y low word
#define REG_I2C_MAG_DATA_Y_HIGH_WORD         0x0019    ///< Magnetometer data Y high word
#define REG_I2C_MAG_DATA_Z_LOW_WORD          0x001A    ///< Magnetometer data Z low word
#define REG_I2C_MAG_DATA_Z_HIGH_WORD         0x001B    ///< Magnetometer data Z high word
#define REG_I2C_PRESS_DATA_LOW_WORD          0x001C    ///< Pressure data low word
#define REG_I2C_PRESS_DATA_HIGH_WORD         0x001D    ///< Pressure data high word
#define REG_I2C_INT_STEP_DATA_LOW_WORD       0x001E    ///< 6DOF step counter data low word
#define REG_I2C_INT_STEP_DATA_HIGH_WORD      0x001F    ///< 6DOF step counter data high word
#define REG_I2C_INT_TAP_DATA                 0x0020    ///< 6DOF tap data
#define REG_I2C_INT_ORIENTATION_DATA         0x0021    ///< 6DOF orientation data

/** IMU interrupt pin selection (high byte) */
#define IMU_INT_PIN_NONE 0x00    ///< Not mapped to any pin
#define IMU_INT_PIN_INT1 0x01    ///< Mapped to INT1 pin
#define IMU_INT_PIN_INT2 0x02    ///< Mapped to INT2 pin
#define IMU_INT_PIN_INT3 0x03    ///< Mapped to INT3 pin
#define IMU_INT_PIN_INT4 0x04    ///< Mapped to INT4 pin

/** INT1_2 interrupt types (low byte) - 6DOF sensor */
#define INT1_2_INT_DISABLE             0x00    ///< INT1_2 interrupt disabled
#define INT1_2_DRDY_INT_ENABLE         0x01    ///< INT1_2 data ready interrupt enabled
#define INT1_2_ANY_MOTION_INT_ENABLE   0x02    ///< INT1_2 any motion interrupt enabled
#define INT1_2_NO_MOTION_INT_ENABLE    0x03    ///< INT1_2 no motion interrupt enabled
#define INT1_2_SIG_MOTION_INT_ENABLE   0x04    ///< INT1_2 significant motion interrupt enabled
#define INT1_2_STEP_COUNTER_INT_ENABLE 0x05    ///< INT1_2 step counter interrupt enabled
#define INT1_2_FLAT_INT_ENABLE         0x06    ///< INT1_2 flat interrupt enabled
#define INT1_2_ORIENTATION_INT_ENABLE  0x07    ///< INT1_2 orientation interrupt enabled
#define INT1_2_TAP_INT_ENABLE          0x08    ///< INT1_2 tap interrupt enabled
#define INT1_2_TILT_INT_ENABLE         0x09    ///< INT1_2 tilt interrupt enabled

/** INT3 interrupt types - 9DOF sensor (magnetometer) */
#define INT3_INT_DISABLE     0x00    ///< INT3 interrupt disabled
#define INT3_DRDY_INT_ENABLE 0x01    ///< INT3 data ready interrupt enabled

/** INT4 interrupt types - 10DOF sensor (barometer) */
#define INT4_INT_DISABLE     0x00    ///< INT4 interrupt disabled
#define INT4_DRDY_INT_ENABLE 0x01    ///< INT4 data ready interrupt enabled
#define INT4_OOR_INT_ENABLE  0x02    ///< INT4 pressure out-of-range interrupt enabled

/** PRESS OOR count limit */
#define PRESS_OOR_COUNT_LIMIT_1  0x00    ///< PRESS OOR count limit: 1 time
#define PRESS_OOR_COUNT_LIMIT_3  0x01    ///< PRESS OOR count limit: 3 times
#define PRESS_OOR_COUNT_LIMIT_7  0x02    ///< PRESS OOR count limit: 7 times
#define PRESS_OOR_COUNT_LIMIT_15 0x03    ///< PRESS OOR count limit: 15 times

public:
#define RET_CODE_OK    0    ///< Return code: success
#define RET_CODE_ERROR 1    ///< Return code: failure

  /**
   * @enum eAccelRange_t
   * @brief Accelerometer range enumeration
   * @details Define the measurement range of accelerometer, unit: g (gravity acceleration)
   */
  typedef enum {
    eAccelRange2G  = 0,    ///< ±2g range
    eAccelRange4G  = 1,    ///< ±4g range
    eAccelRange8G  = 2,    ///< ±8g range
    eAccelRange16G = 3     ///< ±16g range
  } eAccelRange_t;

  /**
   * @enum eGyroRange_t
   * @brief Gyroscope range enumeration
   * @details Define the measurement range of gyroscope, unit: dps (degrees per second)
   */
  typedef enum {
    eGyroRange125DPS  = 0,    ///< ±125dps range
    eGyroRange250DPS  = 1,    ///< ±250dps range
    eGyroRange500DPS  = 2,    ///< ±500dps range
    eGyroRange1000DPS = 3,    ///< ±1000dps range
    eGyroRange2000DPS = 4     ///< ±2000dps range
  } eGyroRange_t;

  /**
   * @enum eSensorMode_t
   * @brief Sensor operating mode enumeration
   * @details Define the operating mode of sensor, affects power consumption and performance
   */
  typedef enum {
    eSleepMode           = 0x00,    ///< Sleep mode: lowest power consumption, sensor stops working
    eLowPowerMode        = 0x01,    ///< Low power mode: reduced sampling rate, saves power
    eNormalMode          = 0x02,    ///< Normal mode: balances power consumption and performance
    eHighPerformanceMode = 0x03     ///< High performance mode: highest sampling rate and accuracy, highest power consumption
  } eSensorMode_t;

  /**
   * @enum eImuIntPin_t
   * @brief IMU interrupt pin enumeration
   * @details Define IMU interrupt output pins
   * @n INT1 and INT2 are used for 6DOF sensor
   * @n INT3 is used for 9DOF sensor (magnetometer)
   * @n INT4 is used for 10DOF sensor (barometer)
   */
  typedef enum {
    eImuIntPinNone = IMU_INT_PIN_NONE,    ///< Not mapped to any pin
    eImuIntPin1    = IMU_INT_PIN_INT1,    ///< INT1 pin (6DOF sensor)
    eImuIntPin2    = IMU_INT_PIN_INT2,    ///< INT2 pin (6DOF sensor)
    eImuIntPin3    = IMU_INT_PIN_INT3,    ///< INT3 pin (9DOF sensor-magnetometer)
    eImuIntPin4    = IMU_INT_PIN_INT4     ///< INT4 pin (10DOF sensor-barometer)
  } eImuIntPin_t;

  /**
   * @enum eIntType_t
   * @brief Unified interrupt type enumeration
   * @details Unified enumeration for all interrupt types across all INT pins
   * @n Values are assigned in ranges to enable type-safe validation:
   * @n - INT1/INT2: 0x00-0x09
   * @n - INT3: 0x10-0x11
   * @n - INT4: 0x20-0x22
   */
  typedef enum {
    // INT1/INT2 interrupt types (0x00-0x09)
    eInt1_2Disable     = 0x00,    ///< Interrupt disabled (INT1/INT2)
    eInt1_2DataReady   = 0x01,    ///< Data ready interrupt (INT1/INT2)
    eInt1_2AnyMotion   = 0x02,    ///< Any motion interrupt (INT1/INT2)
    eInt1_2NoMotion    = 0x03,    ///< No motion interrupt (INT1/INT2)
    eInt1_2SigMotion   = 0x04,    ///< Significant motion interrupt (INT1/INT2)
    eInt1_2StepCounter = 0x05,    ///< Step counter interrupt (INT1/INT2)
    eInt1_2Flat        = 0x06,    ///< Flat interrupt (INT1/INT2)
    eInt1_2Orientation = 0x07,    ///< Orientation interrupt (INT1/INT2)
    eInt1_2Tap         = 0x08,    ///< Tap interrupt (INT1/INT2)
    eInt1_2Tilt        = 0x09,    ///< Tilt interrupt (INT1/INT2)

    // INT3 interrupt types (0x10-0x11)
    eInt3Disable   = 0x10,    ///< Interrupt disabled (INT3)
    eInt3DataReady = 0x11,    ///< Data ready interrupt (INT3)

    // INT4 interrupt types (0x20-0x22)
    eInt4Disable     = 0x20,    ///< Interrupt disabled (INT4)
    eInt4DataReady   = 0x21,    ///< Data ready interrupt (INT4)
    eInt4PressureOOR = 0x22     ///< Pressure out-of-range interrupt (INT4)
  } eIntType_t;

  /**
   * @enum ePressOORCountLimit_t
   * @brief Pressure out-of-range count limit enumeration
   * @details Define count limit for pressure out-of-range, used for filtering
   * @n Interrupt is triggered only after N consecutive out-of-range occurrences, avoiding false triggers due to noise
   */
  typedef enum {
    ePressOORCountLimit1  = PRESS_OOR_COUNT_LIMIT_1,    ///< OOR count limit: 1 time
    ePressOORCountLimit3  = PRESS_OOR_COUNT_LIMIT_3,    ///< OOR count limit: 3 times
    ePressOORCountLimit7  = PRESS_OOR_COUNT_LIMIT_7,    ///< OOR count limit: 7 times
    ePressOORCountLimit15 = PRESS_OOR_COUNT_LIMIT_15    ///< OOR count limit: 15 times
  } ePressOORCountLimit_t;

  /**
   * @struct sImuRawData_t
   * @brief 6DOF IMU raw data structure
   * @details Store three-axis raw data of accelerometer and gyroscope (16-bit integer)
   */
  typedef struct {
    int16_t accelX;    ///< Accelerometer X-axis raw data
    int16_t accelY;    ///< Accelerometer Y-axis raw data
    int16_t accelZ;    ///< Accelerometer Z-axis raw data
    int16_t gyroX;     ///< Gyroscope X-axis raw data
    int16_t gyroY;     ///< Gyroscope Y-axis raw data
    int16_t gyroZ;     ///< Gyroscope Z-axis raw data
  } sImuRawData_t;

  /**
   * @struct sSensorData_t
   * @brief Sensor data structure (physical units)
   * @details Store physical quantities of three-axis sensor data (X, Y, Z axes)
   */
  typedef struct {
    float x;    ///< X-axis data
    float y;    ///< Y-axis data
    float z;    ///< Z-axis data
  } sSensorData_t;

  /**
   * @fn DFRobot_Multi_DOF_IMU
   * @brief Constructor
   * @param model Sensor model (see eSensorModel_t), default is 10DOF IMU
   */
  DFRobot_Multi_DOF_IMU(eSensorModel_t model = eSensorModel10DOF);
  ~DFRobot_Multi_DOF_IMU();

  /**
   * @fn begin
   * @brief Initialize sensor
   * @return bool
   * @retval true  Initialization successful
   * @retval false Initialization failed
   */
  bool begin(void);

  /**
   * @fn setSensorMode
   * @brief Set sensor operating mode
   * @param mode Sensor operating mode (see eSensorMode_t)
   * @n Available modes:
   * @n - eSleepMode:           Sleep mode (lowest power consumption, sensor stops working)
   * @n - eLowPowerMode:        Low power mode (reduced sampling rate, saves power)
   * @n - eNormalMode:          Normal mode (balances power consumption and performance)
   * @n - eHighPerformanceMode: High performance mode (highest sampling rate and accuracy, highest power consumption)
   * @return bool
   * @retval true  Setting successful
   * @retval false Setting failed
   */
  bool setSensorMode(eSensorMode_t mode);

  /**
   * @fn reset
   * @brief Restore factory settings
   * @details Restore sensor to factory default settings
   * @n When called in I2C mode, it will restore UART mode baud rate to 9600bps
   * @return bool
   * @retval true  Factory reset successful
   * @retval false Factory reset failed
   */
  bool reset(void);

  /**
   * @fn setAccelRange
   * @brief Set accelerometer range
   * @param range Accelerometer range (see eAccelRange_t)
   * @n Available ranges:
   * @n - eAccelRange2G:  ±2g range
   * @n - eAccelRange4G:  ±4g range
   * @n - eAccelRange8G:  ±8g range
   * @n - eAccelRange16G: ±16g range
   * @return bool
   * @retval true  Setting successful
   * @retval false Setting failed
   */
  bool setAccelRange(eAccelRange_t range);

  /**
   * @fn setGyroRange
   * @brief Set gyroscope range
   * @param range Gyroscope range (see eGyroRange_t)
   * @n Available ranges:
   * @n - eGyroRange125DPS:  ±125dps range
   * @n - eGyroRange250DPS:  ±250dps range
   * @n - eGyroRange500DPS:  ±500dps range
   * @n - eGyroRange1000DPS: ±1000dps range
   * @n - eGyroRange2000DPS: ±2000dps range
   * @return bool
   * @retval true  Setting successful
   * @retval false Setting failed
   */
  bool setGyroRange(eGyroRange_t range);

  /**
   * @fn calibrateAltitude
   * @brief Calibrate altitude data based on local altitude
   * @param altitude Local altitude (unit: m)
   * @n For example: 540.0 means altitude of 540 meters
   * @n After calling this function, the altitude in get10dofData (when calcAltitude is true) will be calibrated to eliminate absolute errors
   * @n If this function is not called, the altitude measurement will not eliminate absolute errors
   * @return bool
   * @retval true  Calibration successful (altitude > 0)
   * @retval false Calibration failed (altitude <= 0)
   * @note Calibration principle:
   * @n - Use local altitude as reference to correct sea-level pressure in barometric formula
   * @n - So that reported altitude is relative to the reference point
   */
  bool calibrateAltitude(float altitude);

  /**
   * @fn setPressOOR
   * @brief Configure pressure out-of-range (OOR) parameters
   * @param threshold Pressure threshold (unit: Pa)
   * @n For example: 100000 Pa (standard sea level pressure is approximately 101325 Pa)
   * @param range Allowed range (unit: Pa)
   * @n For example: 50 Pa, means allowed range is threshold ± range
   * @n Actual allowed range: threshold - range ~ threshold + range
   * @param countLimit Count limit (see ePressOORCountLimit_t)
   * @n Interrupt is triggered only after N consecutive out-of-range occurrences, used for filtering to avoid false triggers
   * @n Available values:
   * @n - ePressOORCountLimit1:  Trigger after 1 consecutive occurrence
   * @n - ePressOORCountLimit3:  Trigger after 3 consecutive occurrences
   * @n - ePressOORCountLimit7:  Trigger after 7 consecutive occurrences
   * @n - ePressOORCountLimit15: Trigger after 15 consecutive occurrences
   * @return bool
   * @retval true  Configuration successful
   * @retval false Configuration failed
   * @note OOR working principle:
   * @n - Allowed pressure range = threshold ± range
   * @n - For example: threshold=100000, range=50 → allowed range: 99950 ~ 100050 Pa
   * @n - When pressure value exceeds allowed range and consecutive out-of-range count reaches countLimit, OOR interrupt will be triggered
   */
  bool setPressOOR(uint32_t threshold, uint8_t range, ePressOORCountLimit_t countLimit);

  /**
   * @fn get6dofData
   * @brief Read 6DOF IMU data (physical units)
   * @param accel Pointer to sSensorData_t structure for storing accelerometer data (unit: g)
   * @param gyro Pointer to sSensorData_t structure for storing gyroscope data (unit: dps)
   * @return bool
   * @retval true  Read successful
   * @retval false Read failed
   */
  bool get6dofData(sSensorData_t *accel, sSensorData_t *gyro);

  /**
   * @fn get9dofData
   * @brief Read 9DOF IMU data (physical units)
   * @details Read 6DOF data (accelerometer+gyroscope) and 3-axis magnetometer data
   * @param accel Pointer to sSensorData_t structure for storing accelerometer data (unit: g)
   * @param gyro Pointer to sSensorData_t structure for storing gyroscope data (unit: dps)
   * @param mag Pointer to sSensorData_t structure for storing magnetometer data (unit: uT)
   * @return bool
   * @retval true  Read successful
   * @retval false Read failed
   */
  bool get9dofData(sSensorData_t *accel, sSensorData_t *gyro, sSensorData_t *mag);

  /**
   * @fn get10dofData
   * @brief Read 10DOF IMU data (physical units)
   * @details Read 6DOF data (accelerometer+gyroscope), 3-axis magnetometer data and pressure data
   * @param accel Pointer to sSensorData_t structure for storing accelerometer data (unit: g)
   * @param gyro Pointer to sSensorData_t structure for storing gyroscope data (unit: dps)
   * @param mag Pointer to sSensorData_t structure for storing magnetometer data (unit: uT)
   * @param pressure Pointer to float for storing pressure or altitude data
   * @n When calcAltitude is true, pressure stores altitude (unit: m)
   * @n When calcAltitude is false, pressure stores pressure data (unit: Pa)
   * @param calcAltitude Whether to calculate altitude, default is false
   * @n true: pressure stores altitude (unit: m)
   * @n false: pressure stores pressure data (unit: Pa)
   * @return bool
   * @retval true  Read successful
   * @retval false Read failed
   */
  bool get10dofData(sSensorData_t *accel, sSensorData_t *gyro, sSensorData_t *mag, float *pressure, bool calcAltitude = false);

  /**
   * @fn setInt
   * @brief Configure interrupt (unified API with type-safe enumeration)
   * @param pin Interrupt pin (see eImuIntPin_t)
   * @n Available pins:
   * @n - eImuIntPin1: INT1 pin (6DOF sensor, supports multiple interrupt types)
   * @n - eImuIntPin2: INT2 pin (6DOF sensor, supports multiple interrupt types)
   * @n - eImuIntPin3: INT3 pin (9DOF sensor-magnetometer, only supports data ready interrupt)
   * @n - eImuIntPin4: INT4 pin (10DOF sensor-barometer, supports data ready and pressure OOR interrupt)
   * @param intType Interrupt type (see eIntType_t)
   * @n INT1/INT2 supported interrupt types:
   * @n - eInt1_2Disable (0x00): Disable interrupt
   * @n - eInt1_2DataReady (0x01): Data ready interrupt
   * @n - eInt1_2AnyMotion (0x02): Any motion interrupt
   * @n - eInt1_2NoMotion (0x03): No motion interrupt
   * @n - eInt1_2SigMotion (0x04): Significant motion interrupt
   * @n - eInt1_2StepCounter (0x05): Step counter interrupt
   * @n - eInt1_2Flat (0x06): Flat interrupt
   * @n - eInt1_2Orientation (0x07): Orientation interrupt
   * @n - eInt1_2Tap (0x08): Tap interrupt
   * @n - eInt1_2Tilt (0x09): Tilt interrupt
   * @n INT3 supported interrupt types:
   * @n - eInt3Disable (0x10): Disable interrupt
   * @n - eInt3DataReady (0x11): Data ready interrupt
   * @n INT4 supported interrupt types:
   * @n - eInt4Disable (0x20): Disable interrupt
   * @n - eInt4DataReady (0x21): Data ready interrupt
   * @n - eInt4PressureOOR (0x22): Pressure out-of-range interrupt
   * @return bool
   * @retval true  Configuration successful
   * @retval false Configuration failed (invalid parameters or write failed)
   * @note Function internally validates whether the combination of pin and interrupt type is legal based on value ranges
   */
  bool setInt(eImuIntPin_t pin, eIntType_t intType);

  /**
   * @fn getStepCount
   * @brief Read step counter data
   * @details Read current cumulative step count
   * @n After detecting step interrupt, call this function to read cumulative step count
   * @return uint32_t Cumulative step count (32-bit)
   * @retval 0 No step data or read failed
   */
  uint32_t getStepCount(void);

  /**
   * @fn getTap
   * @brief Read tap data
   * @details When tap interrupt is detected, call this function to read the specific tap type
   * @return uint16_t Tap data
   * @n Return values:
   * @n - TAP_TYPE_SINGLE (0x0001): Single tap
   * @n - TAP_TYPE_DOUBLE (0x0002): Double tap
   * @n - TAP_TYPE_TRIPLE (0x0003): Triple tap
   * @retval 0 No tap data or read failed
   */
  uint16_t getTap(void);

  /**
   * @fn getOrientation
   * @brief Read orientation data
   * @details When orientation interrupt is detected, call this function to read the specific orientation and face direction
   * @return uint16_t Orientation data
   * @n High byte: Orientation type
   * @n - ORIENT_TYPE_PORTRAIT_UP (0x01): Portrait upright
   * @n - ORIENT_TYPE_LANDSCAPE_LEFT (0x02): Landscape left
   * @n - ORIENT_TYPE_LANDSCAPE_RIGHT (0x03): Landscape right
   * @n - ORIENT_TYPE_PORTRAIT_DOWN (0x04): Portrait upside down
   * @n Low byte: Face direction type
   * @n - ORIENT_FACE_UP (0x00): Face forward
   * @n - ORIENT_FACE_DOWN (0x01): Face backward
   * @retval 0 No orientation data or read failed
   */
  uint16_t getOrientation(void);

protected:
  /**
   * @fn writeReg
   * @brief Write register (pure virtual function, implemented by subclasses)
   * @param reg Register address
   * @param data Data to write
   * @param len Data length
   * @return uint8_t Return code
   */
  virtual uint8_t writeReg(uint16_t reg, void *data, uint8_t len) = 0;

  /**
   * @fn readReg
   * @brief Read register (pure virtual function, implemented by subclasses)
   * @param reg Register address
   * @param data Buffer for storing read data
   * @param len Data length to read
   * @param regType Register type (see eRegType_t), default is eInputReg
   * @n In UART mode: eInputReg uses Modbus function code 0x04, eHoldingReg uses function code 0x03
   * @n In I2C mode: this parameter is ignored
   * @return uint8_t Return code
   */
  virtual uint8_t readReg(uint16_t reg, void *data, uint8_t len, eRegType_t regType = eInputReg) = 0;

  /**
   * @fn getCommMode
   * @brief Get communication mode (pure virtual function, implemented by subclasses)
   * @return eCommMode_t Communication mode
   */
  virtual eCommMode_t getCommMode(void) = 0;

private:
  /**
   * @fn getRegAddr
   * @brief Get correct register address based on communication mode
   * @param uartReg Register address for UART mode
   * @param i2cReg Register address for I2C mode
   * @return uint16_t Register address returned based on current communication mode
   */
  uint16_t getRegAddr(uint16_t uartReg, uint16_t i2cReg);

  /**
   * @fn intTypeToMacroValue
   * @brief Convert unified interrupt type enumeration to corresponding macro value
   * @param pin Interrupt pin
   * @param intType Unified interrupt type enumeration value
   * @param macroValue Output parameter for the corresponding macro value
   * @return bool
   * @retval true  Conversion successful
   * @retval false Invalid pin/intType combination
   */
  bool intTypeToMacroValue(eImuIntPin_t pin, eIntType_t intType, uint8_t *macroValue);

  /**
   * @fn read6AxisRawBytes
   * @brief Read raw 6DOF data byte stream
   * @param data Buffer for storing read data (12 bytes)
   * @return uint8_t Return code
   */
  uint8_t read6AxisRawBytes(uint8_t *data);

  /**
   * @fn readMagRawBytes
   * @brief Read raw magnetometer data byte stream
   * @param data Buffer for storing read data (12 bytes)
   * @return uint8_t Return code
   */
  uint8_t readMagRawBytes(uint8_t *data);

  /**
   * @fn readPressRawBytes
   * @brief Read raw pressure data byte stream
   * @param data Buffer for storing read data (4 bytes)
   * @return uint8_t Return code
   */
  uint8_t readPressRawBytes(uint8_t *data);

  /**
   * @fn get6AxisRawData
   * @brief Read 6DOF IMU raw data (16-bit integer)
   * @param data Pointer to sImuRawData_t structure for storing read raw data
   * @return bool
   * @retval true  Read successful
   * @retval false Read failed
   */
  bool get6AxisRawData(sImuRawData_t *data);

  /**
   * @fn calculateAltitude
   * @brief Calculate altitude based on pressure
   * @param pressure Pressure value, unit: Pa
   * @return float Altitude, unit: m
   */
  float calculateAltitude(float pressure);

  /**
   * @fn lsbToG
   * @brief Convert accelerometer raw data to physical quantity (g)
   * @param val Raw data (16-bit signed integer)
   * @param gRange Accelerometer range
   * @return float Accelerometer physical quantity, unit: g
   */
  float lsbToG(int16_t val, float gRange);

  /**
   * @fn lsbToDps
   * @brief Convert gyroscope raw data to physical quantity (dps)
   * @param val Raw data (16-bit signed integer)
   * @param dpsRange Gyroscope range
   * @return float Gyroscope physical quantity, unit: dps
   */
  float lsbToDps(int16_t val, float dpsRange);

  float          _accelRange;          ///< Accelerometer range, unit: g
  float          _gyroRange;           ///< Gyroscope range, unit: dps
  eSensorModel_t _sensorModel;         ///< Sensor model
  bool           _calibrated;          ///< Altitude calibration flag
  float          _sealevelAltitude;    ///< Sea level altitude (for calibration), unit: m
};

/**
 * @class DFRobot_Multi_DOF_IMU_I2C
 * @brief DFRobot_Multi_DOF_IMU I2C communication subclass
 * @details Communicate with IMU sensor through I2C interface
 */
class DFRobot_Multi_DOF_IMU_I2C : public DFRobot_Multi_DOF_IMU {
private:
  TwoWire *_pWire;      ///< I2C object pointer
  uint8_t  _i2cAddr;    ///< I2C device address

  /**
   * @fn writeReg
   * @brief Write register via I2C
   * @param reg Register address
   * @param data Data to write
   * @param len Data length
   * @return uint8_t Return code
   */
  virtual uint8_t writeReg(uint16_t reg, void *data, uint8_t len);

  /**
   * @fn readReg
   * @brief Read register via I2C
   * @param reg Register address
   * @param data Buffer for storing read data
   * @param len Data length to read
   * @param regType Register type (ignored in I2C mode, kept for API compatibility)
   * @return uint8_t Return code
   */
  virtual uint8_t readReg(uint16_t reg, void *data, uint8_t len, eRegType_t regType = eInputReg);

  /**
   * @fn getCommMode
   * @brief Get communication mode
   * @return eCommMode_t Returns I2C communication mode
   */
  virtual eCommMode_t getCommMode(void);

public:
  /**
   * @fn DFRobot_Multi_DOF_IMU_I2C
   * @brief Constructor
   * @param model Sensor model (see eSensorModel_t), default is 10DOF IMU
   * @param pWire I2C object pointer, default is &Wire
   * @param addr I2C device address, default is 0x4A
   */
  DFRobot_Multi_DOF_IMU_I2C(eSensorModel_t model = eSensorModel10DOF, TwoWire *pWire = &Wire, uint8_t addr = 0x4A);

  /**
   * @fn ~DFRobot_Multi_DOF_IMU_I2C
   * @brief Destructor
   */
  ~DFRobot_Multi_DOF_IMU_I2C();

  /**
   * @fn begin
   * @brief Initialize I2C communication and sensor
   * @return bool
   * @retval true  Initialization successful
   * @retval false Initialization failed
   */
  bool begin(void);
};

/**
 * @class DFRobot_Multi_DOF_IMU_UART
 * @brief DFRobot_Multi_DOF_IMU UART communication subclass
 * @details Communicate with IMU sensor through UART interface using Modbus RTU protocol
 */
class DFRobot_Multi_DOF_IMU_UART : public DFRobot_Multi_DOF_IMU, public DFRobot_RTU {
private:
#if defined(ARDUINO_AVR_UNO) || defined(ESP8266)
  SoftwareSerial *_serial;
#else
  HardwareSerial *_serial;
#endif
  uint32_t _baud;          ///< Baud rate
  uint8_t  _rxPin;         ///< RX pin
  uint8_t  _txPin;         ///< TX pin
  uint8_t  _deviceAddr;    ///< Device address

  /**
   * @fn writeReg
   * @brief Write register via UART (using Modbus RTU protocol)
   * @param reg Register address
   * @param data Data to write
   * @param len Data length
   * @return uint8_t Return code
   * @retval RET_CODE_OK Write successful
   * @retval RET_CODE_ERROR Write failed
   */
  virtual uint8_t writeReg(uint16_t reg, void *data, uint8_t len);

  /**
   * @fn readReg
   * @brief Read register via UART (using Modbus RTU protocol)
   * @param reg Register address
   * @param data Buffer for storing read data
   * @param len Data length to read
   * @param regType Register type (see eRegType_t)
   * @n eInputReg: Read from input registers (Modbus function code 0x04)
   * @n eHoldingReg: Read from holding registers (Modbus function code 0x03)
   * @return uint8_t Return code
   * @retval RET_CODE_OK Read successful
   * @retval RET_CODE_ERROR Read failed
   */
  virtual uint8_t readReg(uint16_t reg, void *data, uint8_t len, eRegType_t regType = eInputReg);

  /**
   * @fn getCommMode
   * @brief Get communication mode
   * @return eCommMode_t Returns UART communication mode
   */
  virtual eCommMode_t getCommMode(void);

public:
#if defined(ARDUINO_AVR_UNO) || defined(ESP8266)
  /**
   * @fn DFRobot_Multi_DOF_IMU_UART
   * @brief Constructor (AVR/ESP8266 uses SoftwareSerial)
   * @param model Sensor model (see eSensorModel_t)
   * @param sSerial SoftwareSerial object pointer
   * @param baud Baud rate
   * @param addr Device address
   */
  DFRobot_Multi_DOF_IMU_UART(eSensorModel_t model, SoftwareSerial *sSerial, uint32_t baud, uint8_t addr);
#else
  /**
   * @fn DFRobot_Multi_DOF_IMU_UART
   * @brief Constructor (uses HardwareSerial)
   * @param model Sensor model (see eSensorModel_t)
   * @param hSerial HardwareSerial object pointer
   * @param baud Baud rate
   * @param addr Device address
   * @param rxPin RX pin (optional)
   * @param txPin TX pin (optional)
   */
  DFRobot_Multi_DOF_IMU_UART(eSensorModel_t model, HardwareSerial *hSerial, uint32_t baud, uint8_t addr, uint8_t rxPin = 0, uint8_t txPin = 0);
#endif

  /**
   * @fn ~DFRobot_Multi_DOF_IMU_UART
   * @brief Destructor
   */
  ~DFRobot_Multi_DOF_IMU_UART();

  /**
   * @fn begin
   * @brief Initialize UART communication and sensor
   * @details Initialize serial port, set Modbus RTU timeout, and send sensor initialization command
   * @return bool
   * @retval true  Initialization successful
   * @retval false Initialization failed (may be DFRobot_RTU library not installed or communication failed)
   */
  bool begin(void);
};

#endif
