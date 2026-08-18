// MesseAuto ESP32 Fahrmotor per Serial
//
// Der Raspberry Pi liest Richtungsschalter + Speed-Poti ein und sendet:
//   {"drive": 60}   vorwaerts 60 %
//   {"drive": -40}  rueckwaerts 40 %
//   {"drive": 0}    stop
//
// Dieser ESP32 braucht keine lokalen Buttons oder Potis.

static const uint32_t BAUDRATE = 115200;

static const int PIN_DRIVE_PWM = 27;
static const int PIN_DRIVE_IN1 = 25;
static const int PIN_DRIVE_IN2 = 26;
static const int DRIVE_PWM_FREQUENCY = 1000;
static const int DRIVE_PWM_RESOLUTION_BITS = 8;

static const int DRIVE_RAMP_STEP_PERCENT = 2;
static const uint32_t DRIVE_RAMP_INTERVAL_MS = 20;
static const uint32_t STATUS_INTERVAL_MS = 150;
static const uint32_t HELLO_INTERVAL_MS = 5000;
static const uint32_t COMMAND_TIMEOUT_MS = 1200;

int targetDrivePercent = 0;  // -100 bis +100
int actualDrivePercent = 0;  // -100 bis +100
uint32_t lastRampMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastHelloMs = 0;
uint32_t lastCommandMs = 0;
String inputLine;

void setup() {
  Serial.begin(BAUDRATE);

  pinMode(PIN_DRIVE_IN1, OUTPUT);
  pinMode(PIN_DRIVE_IN2, OUTPUT);
  pinMode(PIN_DRIVE_PWM, OUTPUT);
  ledcAttach(PIN_DRIVE_PWM, DRIVE_PWM_FREQUENCY, DRIVE_PWM_RESOLUTION_BITS);

  applyDriveOutput(0);
  lastCommandMs = millis();
  sendHello();
}

void loop() {
  readSerialCommands();
  stopOnCommandTimeout();
  updateDriveRamp();

  const uint32_t now = millis();
  if (now - lastHelloMs > HELLO_INTERVAL_MS) {
    sendHello();
  }
  if (now - lastStatusMs > STATUS_INTERVAL_MS) {
    sendStatus();
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

  const int driveValue = readIntField(line, "drive", 1000);
  if (driveValue != 1000) {
    setDriveTarget(constrain(driveValue, -100, 100));
    return;
  }

  const int percent = readIntField(line, "percent", -1);
  if (percent >= 0) {
    int direction = 1;
    if (line.indexOf("reverse") >= 0 || line.indexOf("rueck") >= 0) {
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
  lastCommandMs = millis();
}

void stopOnCommandTimeout() {
  if (millis() - lastCommandMs > COMMAND_TIMEOUT_MS) {
    targetDrivePercent = 0;
  }
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

  // Bei Richtungswechseln erst auf 0 Prozent fahren, dann umpolen.
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
  Serial.printf("{\"device\":\"esp32_fahrregler\",\"type\":\"hello\",\"mode\":\"serial_drive\",\"baudrate\":%lu}\n", BAUDRATE);
}

void sendStatus() {
  lastStatusMs = millis();
  Serial.printf(
    "{\"device\":\"esp32_fahrregler\",\"type\":\"drive_status\",\"mode\":\"serial_drive\","
    "\"target_drive\":%d,\"actual_drive\":%d,\"direction\":\"%s\","
    "\"speed_percent\":%d,\"command_age_ms\":%lu,\"errors\":[]}\n",
    targetDrivePercent,
    actualDrivePercent,
    directionLabel(actualDrivePercent),
    abs(actualDrivePercent),
    millis() - lastCommandMs
  );
}
