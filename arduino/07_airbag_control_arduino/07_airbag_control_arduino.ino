// 独立 Arduino 气囊定时测试程序（适用于 Uno/Nano 等经典 AVR 开发板）。
// 上电即运行固定循环；这不是依据传感器结果触发的最终程序。
// 输出默认为高电平启动；三个负载必须经匹配的驱动模块供电，不能直接接到 IO 引脚。

const byte PIN_VALVE = 3;          // 电磁阀：只开/关，不使用 PWM
const byte PIN_INFLATE_PUMP = 4;   // 充气泵：按原示例，仅全速开/关（Uno 的 D4 不支持 PWM）
const byte PIN_DEFLATE_PUMP = 5;   // 抽气泵：PWM 引脚

const byte DEFLATE_SPEED = 255;    // 抽气泵占空比，0–255
const byte CYCLE_COUNT = 3;       // 循环次数
const unsigned long INFLATE_MS = 8000;
const unsigned long DEFLATE_MS = 8000;

void stopAll() {
  digitalWrite(PIN_INFLATE_PUMP, LOW);
  analogWrite(PIN_DEFLATE_PUMP, 0);
  digitalWrite(PIN_VALVE, LOW);
}

void setup() {
  // 先设为关闭电平，再切换成输出，减少上电时误动作。
  digitalWrite(PIN_VALVE, LOW);
  digitalWrite(PIN_INFLATE_PUMP, LOW);
  digitalWrite(PIN_DEFLATE_PUMP, LOW);
  pinMode(PIN_VALVE, OUTPUT);
  pinMode(PIN_INFLATE_PUMP, OUTPUT);
  pinMode(PIN_DEFLATE_PUMP, OUTPUT);
  stopAll();

  Serial.begin(9600);
  Serial.println(F("气囊控制系统已启动"));
  Serial.println(F("充气泵: 全速开/关（D4 无 PWM）"));
  Serial.print(F("抽气泵速度: "));
  Serial.print(DEFLATE_SPEED * 100.0 / 255.0);
  Serial.println(F("%"));

  for (byte cycle = 0; cycle < CYCLE_COUNT; ++cycle) {
    Serial.print(F("开始第 "));
    Serial.print(cycle + 1);
    Serial.println(F(" 次循环"));

    Serial.println(F("充气阶段开始"));
    stopAll();
    digitalWrite(PIN_VALVE, HIGH);
    digitalWrite(PIN_INFLATE_PUMP, HIGH);
    delay(INFLATE_MS);

    Serial.println(F("抽气阶段开始"));
    stopAll();
    analogWrite(PIN_DEFLATE_PUMP, DEFLATE_SPEED);
    delay(DEFLATE_MS);

    Serial.println(F("停止阶段开始"));
    stopAll();
  }

  Serial.println(F("所有循环完成"));
}

void loop() {
  // 上电或按复位键时执行一次 setup()，完成后保持停止。
}
