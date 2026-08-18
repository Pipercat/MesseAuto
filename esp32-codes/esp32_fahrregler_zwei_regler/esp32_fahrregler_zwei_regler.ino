// MesseAuto Fahrregler mit zwei Bedienelementen
//
// 1. Richtungsschalter: links = rueckwaerts, mitte = stop, rechts = vorwaerts
// 2. Geschwindigkeitspoti: 0 bis 100 Prozent
//
// Ausgang fuer den Fahrmotor: PWM + zwei Richtungspins an eine H-Bruecke
// wie TB6612FNG, DRV8833, BTS7960 oder L298N.

static const uint32_t BAUDRATE = 115200;

// === Eingaben ===
// 3-Stellungen-Schalter ON-OFF-ON:
// - linker Kontakt an GPIO 33 und GND
// - rechter Kontakt an GPIO 32 und GND
// - Mittelstellung laesst beide Eingaenge offen
static const int PIN_DIRECTION_FORWARD = 32;
static const int PIN_DIRECTION_REVERSE = 33;

// 10k-Potentiometer: 3V3 - Schleifer GPIO34 - GND
// Nie 5V auf den ESP32-ADC geben.
static const int PIN_SPEED_ADC = 34;

// === Fahrmotor-Ausgang ===
static const int PIN_DRIVE_PWM = 27;
static const int PIN_DRIVE_IN1 = 25;
static const int PIN_DRIVE_IN2 = 26;
static const int DRIVE_PWM_FREQUENCY = 1000;
static const int DRIVE_PWM_RESOLUTION_BITS = 8;

// === Verhalten ===
static const int SPEED_DEADBAND_PERCENT = 2;
static const int DRIVE_RAMP_STEP_PERCENT = 2;
static const uint32_t DRIVE_RAMP_INTERVAL_MS = 20;
static const uint32_t STATUS_INTERVAL_MS = 150;
static const uint32_t HELLO_INTERVAL_MS = 5000;

enum Direction {
  DIRECTION_STOP = 0,
  DIRECTION_FORWARD = 1,
  DIRECTION_REVERSE = -1,
};

int targetDrivePercent = 0;  // -100 bis +100
int actualDrivePercent = 0;  // -100 bis +100
uint32_t lastRampMs = 0;
uint32_t lastStatusMs = 0;
uint32_t lastHelloMs = 0;
String inputLine;

void setup() {
  Serial.begin(BAUDRATE);

  pinMode(PIN_DIRECTION_FORWARD, INPUT_PULLUP);
  pinMode(PIN_DIRECTION_REVERSE, INPUT_PULLUP);
  pinMode(PIN_SPEED_ADC, INPUT);

  pinMode(PIN_DRIVE_IN1, OUTPUT);
  pinMode(PIN_DRIVE_IN2, OUTPUT);
  pinMode(PIN_DRIVE_PWM, OUTPUT);

  analogReadResolution(12);
  ledcAttach(PIN_DRIVE_PWM, DRIVE_PWM_FREQUENCY, DRIVE_PWM_RESOLUTION_BITS);

  applyDriveOutput(0);
  sendHello();
}

void loop() {
  readSerialCommands();
  updateTargetFromControls();
  updateDriveRamp();

  const uint32_t now = millis();
  if (now - lastHelloMs > HELLO_INTERVAL_MS) {
    sendHello();
  }
  if (now - lastStatusMs > STATUS_INTERVAL_MS) {
    sendStatus();
  }
}

void updateTargetFromControls() {
  const Direction direction = readDirectionSwitch();
  const int speedPercent = readSpeedPercent();

  if (direction == DIRECTION_STOP || speedPercent <= SPEED_DEADBAND_PERCENT) {
    targetDrivePercent = 0;
    return;
  }

  targetDrivePercent = static_cast<int>(direction) * speedPercent;
}

Direction readDirectionSwitch() {
  const bool forwardActive = digitalRead(PIN_DIRECTION_FORWARD) == LOW;
  const bool reverseActive = digitalRead(PIN_DIRECTION_REVERSE) == LOW;

  if (forwardActive && !reverseActive) {
    return DIRECTION_FORWARD;
  }
  if (reverseActive && !forwardActive) {
    return DIRECTION_REVERSE;
  }

  // Mitte oder unplausibler Zustand: sicher stoppen.
  return DIRECTION_STOP;
}

int readSpeedPercent() {
  long total = 0;
  for (int index = 0; index < 8; index += 1) {
    total += analogRead(PIN_SPEED_ADC);
    delayMicroseconds(250);
  }

  const int raw = total / 8;
  return constrain(map(raw, 0, 4095, 0, 100), 0, 100);
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
  if (line.indexOf("\"stop\"") >= 0 || line.indexOf("\"reset\"") >= 0) {
    targetDrivePercent = 0;
    return;
  }
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
  Serial.printf("{\"device\":\"esp32_fahrregler\",\"type\":\"hello\",\"mode\":\"two_controls\",\"baudrate\":%lu}\n", BAUDRATE);
}

void sendStatus() {
  lastStatusMs = millis();
  const Direction selectedDirection = readDirectionSwitch();
  const int selectedSpeed = readSpeedPercent();

  Serial.printf(
    "{\"device\":\"esp32_fahrregler\",\"type\":\"drive_status\",\"mode\":\"two_controls\","
    "\"selected_direction\":\"%s\",\"selected_speed_percent\":%d,"
    "\"target_drive\":%d,\"actual_drive\":%d,"
    "\"direction\":\"%s\",\"speed_percent\":%d,\"errors\":[]}\n",
    selectedDirection == DIRECTION_FORWARD ? "forward" : selectedDirection == DIRECTION_REVERSE ? "reverse" : "stop",
    selectedSpeed,
    targetDrivePercent,
    actualDrivePercent,
    directionLabel(actualDrivePercent),
    abs(actualDrivePercent)
  );
}
