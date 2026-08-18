// MesseAuto motorisierter Fahrregler
//
// Prinzip:
// - AS5600 misst die Knopfposition.
// - 180 Grad ist Stop.
// - Rechts von der Mitte = vorwaerts, links von der Mitte = rueckwaerts.
// - Ein kleiner Schrittmotor kann den Knopf automatisch auf einen Sollwert drehen.
// - PWM + IN1/IN2 steuern einen DC-Motortreiber wie TB6612FNG oder L298N.

#include <Wire.h>
#include <Adafruit_NeoPixel.h>

static const uint32_t BAUDRATE = 115200;

// === AS5600 Setup ===
static const uint8_t AS5600_ADDR = 0x36;

// === Motorisierter Knopf: 28BYJ-48 + ULN2003 ===
static const int DIAL_MOTOR_PINS[4] = {18, 19, 20, 21};
static const int DIAL_STEPS_PER_REVOLUTION = 2048;
static const int DIAL_HALF_STEPS_PER_REVOLUTION = DIAL_STEPS_PER_REVOLUTION * 2;
static const float DIAL_MAX_SPEED_STEPS_PER_SECOND = 650.0f;
static const float DIAL_TARGET_TOLERANCE_DEG = 2.0f;

unsigned long dialStepIntervalMicros = 0;
unsigned long lastDialStepMicros = 0;
int dialStepIndex = 0;
bool dialMoveActive = false;
float dialTargetAngle = 180.0f;

static const int DIAL_STEP_SEQUENCE[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1}
};

// === LED-Ring, optional ===
static const bool USE_NEOPIXEL_RING = true;
static const int NEOPIXEL_PIN = 28;
static const int NUM_PIXELS = 12;
Adafruit_NeoPixel pixels(NUM_PIXELS, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// === Fahrmotor-Ausgang ===
// PWM + zwei Richtungspins fuer H-Bruecke/Motortreiber.
static const int PIN_DRIVE_PWM = 27;
static const int PIN_DRIVE_IN1 = 25;
static const int PIN_DRIVE_IN2 = 26;
static const int DRIVE_PWM_FREQUENCY = 1000;
static const int DRIVE_PWM_RESOLUTION_BITS = 8;

// === Fahrregler-Kalibrierung ===
static const float STOP_ANGLE_DEG = 180.0f;
static const float STOP_DEADBAND_DEG = 8.0f;
static const float REVERSE_MAX_ANGLE_DEG = 20.0f;
static const float FORWARD_MAX_ANGLE_DEG = 340.0f;
static const int DRIVE_RAMP_STEP_PERCENT = 2;
static const uint32_t DRIVE_RAMP_INTERVAL_MS = 20;

int targetDrivePercent = 0;  // -100 rueckwaerts bis +100 vorwaerts
int actualDrivePercent = 0;
uint32_t lastRampMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastHelloMs = 0;
String inputLine;

void setup() {
  Serial.begin(BAUDRATE);

  Wire.begin();

  if (USE_NEOPIXEL_RING) {
    pixels.begin();
    pixels.clear();
    pixels.show();
  }

  for (int index = 0; index < 4; index += 1) {
    pinMode(DIAL_MOTOR_PINS[index], OUTPUT);
    digitalWrite(DIAL_MOTOR_PINS[index], LOW);
  }

  pinMode(PIN_DRIVE_IN1, OUTPUT);
  pinMode(PIN_DRIVE_IN2, OUTPUT);
  pinMode(PIN_DRIVE_PWM, OUTPUT);
  ledcAttach(PIN_DRIVE_PWM, DRIVE_PWM_FREQUENCY, DRIVE_PWM_RESOLUTION_BITS);

  dialStepIntervalMicros = 1000000.0f / DIAL_MAX_SPEED_STEPS_PER_SECOND;
  applyDriveOutput(0);
  sendHello();
}

void loop() {
  readSerialCommands();

  const float angle = readAS5600Degrees();
  if (dialMoveActive) {
    updateDialMotor(angle);
  } else {
    targetDrivePercent = drivePercentFromAngle(angle);
  }

  updateDriveRamp();
  showDriveColor(actualDrivePercent);

  const uint32_t now = millis();
  if (now - lastHelloMs > 5000) {
    sendHello();
  }
  if (now - lastStatusMs > 150) {
    sendStatus(angle);
  }
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      handleCommand(inputLine);
      inputLine = "";
    } else if (c != '\r') {
      inputLine += c;
    }
  }
}

void handleCommand(const String &line) {
  if (line.length() == 0) {
    return;
  }

  if (line.indexOf("\"stop\"") >= 0 || line.indexOf("\"reset\"") >= 0) {
    setDriveTarget(0);
    return;
  }

  const int signedDrive = readIntField(line, "drive", 1000);
  if (signedDrive != 1000) {
    setDriveTarget(constrain(signedDrive, -100, 100));
    return;
  }

  const int percent = readIntField(line, "percent", -1);
  if (percent >= 0) {
    int direction = 1;
    if (line.indexOf("reverse") >= 0 || line.indexOf("rueckwaerts") >= 0 || line.indexOf("rueck") >= 0) {
      direction = -1;
    }
    if (line.indexOf("stop") >= 0) {
      direction = 0;
    }
    setDriveTarget(direction * constrain(percent, 0, 100));
  }
}

int readIntField(const String &line, const char *key, int fallback) {
  const String quotedKey = String("\"") + key + "\"";
  const int keyIndex = line.indexOf(quotedKey);
  if (keyIndex < 0) {
    return fallback;
  }
  const int colon = line.indexOf(':', keyIndex);
  if (colon < 0) {
    return fallback;
  }
  return line.substring(colon + 1).toInt();
}

void setDriveTarget(int signedPercent) {
  targetDrivePercent = constrain(signedPercent, -100, 100);
  dialTargetAngle = angleFromDrivePercent(targetDrivePercent);
  dialMoveActive = true;
}

int drivePercentFromAngle(float angle) {
  if (angle >= STOP_ANGLE_DEG - STOP_DEADBAND_DEG && angle <= STOP_ANGLE_DEG + STOP_DEADBAND_DEG) {
    return 0;
  }

  if (angle > STOP_ANGLE_DEG + STOP_DEADBAND_DEG) {
    const float ratio = (angle - (STOP_ANGLE_DEG + STOP_DEADBAND_DEG)) / (FORWARD_MAX_ANGLE_DEG - (STOP_ANGLE_DEG + STOP_DEADBAND_DEG));
    return constrain(static_cast<int>(round(ratio * 100.0f)), 0, 100);
  }

  const float ratio = ((STOP_ANGLE_DEG - STOP_DEADBAND_DEG) - angle) / ((STOP_ANGLE_DEG - STOP_DEADBAND_DEG) - REVERSE_MAX_ANGLE_DEG);
  return -constrain(static_cast<int>(round(ratio * 100.0f)), 0, 100);
}

float angleFromDrivePercent(int signedPercent) {
  signedPercent = constrain(signedPercent, -100, 100);
  if (signedPercent == 0) {
    return STOP_ANGLE_DEG;
  }

  if (signedPercent > 0) {
    const float ratio = signedPercent / 100.0f;
    return (STOP_ANGLE_DEG + STOP_DEADBAND_DEG) + ratio * (FORWARD_MAX_ANGLE_DEG - (STOP_ANGLE_DEG + STOP_DEADBAND_DEG));
  }

  const float ratio = abs(signedPercent) / 100.0f;
  return (STOP_ANGLE_DEG - STOP_DEADBAND_DEG) - ratio * ((STOP_ANGLE_DEG - STOP_DEADBAND_DEG) - REVERSE_MAX_ANGLE_DEG);
}

void updateDriveRamp() {
  const uint32_t now = millis();
  if (now - lastRampMs < DRIVE_RAMP_INTERVAL_MS) {
    return;
  }
  lastRampMs = now;

  if (actualDrivePercent == targetDrivePercent) {
    return;
  }

  // Richtungswechsel immer erst ueber 0 %, damit die H-Bruecke nicht hart umpolt.
  if (actualDrivePercent != 0 && targetDrivePercent != 0 && signOf(actualDrivePercent) != signOf(targetDrivePercent)) {
    actualDrivePercent += actualDrivePercent > 0 ? -DRIVE_RAMP_STEP_PERCENT : DRIVE_RAMP_STEP_PERCENT;
  } else if (actualDrivePercent < targetDrivePercent) {
    actualDrivePercent = min(actualDrivePercent + DRIVE_RAMP_STEP_PERCENT, targetDrivePercent);
  } else {
    actualDrivePercent = max(actualDrivePercent - DRIVE_RAMP_STEP_PERCENT, targetDrivePercent);
  }

  applyDriveOutput(actualDrivePercent);
}

int signOf(int value) {
  if (value > 0) {
    return 1;
  }
  if (value < 0) {
    return -1;
  }
  return 0;
}

void applyDriveOutput(int signedPercent) {
  const int pwm = map(abs(signedPercent), 0, 100, 0, 255);

  if (signedPercent > 0) {
    digitalWrite(PIN_DRIVE_IN1, HIGH);
    digitalWrite(PIN_DRIVE_IN2, LOW);
  } else if (signedPercent < 0) {
    digitalWrite(PIN_DRIVE_IN1, LOW);
    digitalWrite(PIN_DRIVE_IN2, HIGH);
  } else {
    digitalWrite(PIN_DRIVE_IN1, LOW);
    digitalWrite(PIN_DRIVE_IN2, LOW);
  }

  ledcWrite(PIN_DRIVE_PWM, pwm);
}

void updateDialMotor(float currentAngle) {
  const float error = shortestAngleDelta(dialTargetAngle, currentAngle);
  if (abs(error) <= DIAL_TARGET_TOLERANCE_DEG) {
    releaseDialMotor();
    dialMoveActive = false;
    return;
  }

  const uint32_t now = micros();
  if (now - lastDialStepMicros >= dialStepIntervalMicros) {
    stepDialMotor(error > 0 ? 1 : -1);
    lastDialStepMicros = now;
  }
}

float shortestAngleDelta(float target, float current) {
  float delta = target - current;
  while (delta > 180.0f) {
    delta -= 360.0f;
  }
  while (delta < -180.0f) {
    delta += 360.0f;
  }
  return delta;
}

void stepDialMotor(int direction) {
  dialStepIndex += direction;
  if (dialStepIndex > 7) {
    dialStepIndex = 0;
  }
  if (dialStepIndex < 0) {
    dialStepIndex = 7;
  }

  for (int index = 0; index < 4; index += 1) {
    digitalWrite(DIAL_MOTOR_PINS[index], DIAL_STEP_SEQUENCE[dialStepIndex][index]);
  }
}

void releaseDialMotor() {
  for (int index = 0; index < 4; index += 1) {
    digitalWrite(DIAL_MOTOR_PINS[index], LOW);
  }
}

uint16_t readAS5600Raw() {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(0x0E);
  Wire.endTransmission(false);
  Wire.requestFrom(AS5600_ADDR, static_cast<uint8_t>(2));
  if (Wire.available() == 2) {
    const uint8_t highByte = Wire.read();
    const uint8_t lowByte = Wire.read();
    return ((highByte & 0x0F) << 8) | lowByte;
  }
  return 0;
}

float readAS5600Degrees() {
  return (readAS5600Raw() * 360.0f) / 4096.0f;
}

void showDriveColor(int signedPercent) {
  if (!USE_NEOPIXEL_RING) {
    return;
  }

  uint8_t red = 255;
  uint8_t green = 255;
  uint8_t blue = 255;

  if (signedPercent > 0) {
    red = 0;
    green = map(signedPercent, 0, 100, 60, 255);
    blue = 80;
  } else if (signedPercent < 0) {
    red = map(abs(signedPercent), 0, 100, 80, 255);
    green = 30;
    blue = 0;
  }

  for (int index = 0; index < NUM_PIXELS; index += 1) {
    pixels.setPixelColor(index, pixels.Color(red, green, blue));
  }
  pixels.show();
}

const char *directionLabel(int signedPercent) {
  if (signedPercent > 0) {
    return "forward";
  }
  if (signedPercent < 0) {
    return "reverse";
  }
  return "stop";
}

void sendHello() {
  lastHelloMs = millis();
  Serial.printf("{\"device\":\"esp32_fahrregler\",\"type\":\"hello\",\"baudrate\":%lu}\n", BAUDRATE);
}

void sendStatus(float angle) {
  lastStatusMs = millis();
  Serial.printf(
    "{\"device\":\"esp32_fahrregler\",\"type\":\"drive_status\",\"timestamp_ms\":%lu,"
    "\"angle_deg\":%.1f,\"target_drive\":%d,\"actual_drive\":%d,"
    "\"direction\":\"%s\",\"speed_percent\":%d,\"dial_move_active\":%s,\"errors\":[]}\n",
    millis(),
    angle,
    targetDrivePercent,
    actualDrivePercent,
    directionLabel(actualDrivePercent),
    abs(actualDrivePercent),
    dialMoveActive ? "true" : "false"
  );
}
