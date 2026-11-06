// Independent Uno/Nano command receiver for an unoccupied bench demonstration.
// D3 valve, D4 inflate pump, D5 deflate pump follow the vendor's breathing example.

#include <Arduino.h>
#include <string.h>

const byte PIN_VALVE = 3;
const byte PIN_INFLATE_PUMP = 4;  // Uno D4 is digital on/off, not PWM
const byte PIN_DEFLATE_PUMP = 5;

// Keep the airbag off a person; this sketch has no pressure feedback or relief control.
const bool BENCH_OUTPUTS_ENABLED = true;
// 12 timed bench cycles. These are not a pressure limit or a detector for
// the wearer's actual breathing phase. Verify bag expansion off-body.
const unsigned long INFLATE_MS = 12000;
const unsigned long DEFLATE_MS = 12000;
const byte CYCLE_COUNT = 12;
const unsigned long ARM_TIMEOUT_MS = 10000;

char command[24] = {};
byte commandLength = 0;
bool discardCommand = false;
enum Phase { IDLE, INFLATING, DEFLATING };
Phase phase = IDLE;
unsigned long phaseStarted = 0;
bool armed = false;
unsigned long armedAt = 0;
byte completedCycles = 0;
bool stopping = false;

bool armActive() {
  return armed && (unsigned long)(millis() - armedAt) < ARM_TIMEOUT_MS;
}

void stopAll() {
  digitalWrite(PIN_INFLATE_PUMP, LOW);
  digitalWrite(PIN_DEFLATE_PUMP, LOW);
  digitalWrite(PIN_VALVE, LOW);
  phase = IDLE;
}

void startDeflate() {
  digitalWrite(PIN_VALVE, LOW);
  digitalWrite(PIN_INFLATE_PUMP, LOW);
  digitalWrite(PIN_DEFLATE_PUMP, HIGH);
  phaseStarted = millis();
  phase = DEFLATING;
  Serial.println(F("PHASE DEFLATE"));
}

void startInflate() {
  digitalWrite(PIN_DEFLATE_PUMP, LOW);
  digitalWrite(PIN_VALVE, HIGH);
  digitalWrite(PIN_INFLATE_PUMP, HIGH);
  phaseStarted = millis();
  phase = INFLATING;
  Serial.println(F("PHASE INFLATE"));
}

void replyStatus() {
  Serial.print(F("STATUS AIRBAG_BENCH_V5 OUTPUTS="));
  Serial.print(BENCH_OUTPUTS_ENABLED ? 1 : 0);
  Serial.print(F(" ARMED="));
  Serial.print(armActive() ? 1 : 0);
  Serial.print(F(" PULSING="));
  Serial.println(phase != IDLE ? 1 : 0);
}

void handleCommand(const char *text) {
  if (strcmp(text, "PING") == 0) {
    Serial.println(F("PONG AIRBAG_BENCH_V5"));
  } else if (strcmp(text, "STATUS") == 0) {
    replyStatus();
  } else if (strcmp(text, "STOP") == 0) {
    armed = false;
    if (phase == INFLATING) {
      stopping = true;
      startDeflate();
    } else if (phase == DEFLATING) {
      stopping = true;
    } else {
      stopAll();
    }
    Serial.println(F("OK STOP"));
  } else if (strcmp(text, "ARM") == 0) {
    if (!BENCH_OUTPUTS_ENABLED || phase != IDLE) {
      Serial.println(F("DENY NOT_READY"));
    } else {
      armed = true;
      armedAt = millis();
      Serial.println(F("OK ARM"));
    }
  } else if (strcmp(text, "FIRE") == 0) {
    if (!BENCH_OUTPUTS_ENABLED) {
      Serial.println(F("DENY OUTPUTS_DISABLED"));
    } else if (!armActive()) {
      Serial.println(F("DENY NOT_ARMED"));
    } else if (phase != IDLE) {
      Serial.println(F("DENY BUSY"));
    } else {
      armed = false;
      stopAll();
      completedCycles = 0;
      stopping = false;
      startInflate();
      Serial.println(F("OK FIRE"));
    }
  } else if (text[0] != '\0') {
    Serial.println(F("DENY UNKNOWN_COMMAND"));
  }
}

void setup() {
  digitalWrite(PIN_VALVE, LOW);
  digitalWrite(PIN_INFLATE_PUMP, LOW);
  digitalWrite(PIN_DEFLATE_PUMP, LOW);
  pinMode(PIN_VALVE, OUTPUT);
  pinMode(PIN_INFLATE_PUMP, OUTPUT);
  pinMode(PIN_DEFLATE_PUMP, OUTPUT);
  stopAll();
  Serial.begin(9600);
  Serial.println(F("READY AIRBAG_BENCH_V5"));
  replyStatus();
}

void loop() {
  if (phase == INFLATING && (unsigned long)(millis() - phaseStarted) >= INFLATE_MS) {
    startDeflate();
  } else if (phase == DEFLATING && (unsigned long)(millis() - phaseStarted) >= DEFLATE_MS) {
    completedCycles++;
    if (stopping) {
      stopAll();
      Serial.println(F("DONE STOP"));
    } else if (completedCycles >= CYCLE_COUNT) {
      stopAll();
      Serial.println(F("DONE FIRE"));
    } else {
      startInflate();
    }
  }
  if (armed && !armActive()) armed = false;
  while (Serial.available()) {
    const char c = Serial.read();
    if (c == '\n') {
      if (discardCommand) {
        Serial.println(F("DENY COMMAND_TOO_LONG"));
      } else {
        command[commandLength] = '\0';
        handleCommand(command);
      }
      commandLength = 0;
      discardCommand = false;
    } else if (c != '\r' && !discardCommand) {
      if (commandLength < sizeof(command) - 1) {
        command[commandLength++] = c;
      } else {
        commandLength = 0;
        discardCommand = true;
      }
    }
  }
}
