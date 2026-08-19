// Bring-up-Test fuer M10 (Drehregler): 2x AS5600 Magnet-Winkelsensor + 2x 28BYJ-48 Stepper ueber ULN2003.
// Dritter ESP32, aktuell nur per USB am Pi1 (nur zum Flashen), nur zum Ausprobieren/Loggen.
// Sensor 1 (Wire):  AS5600 3.3V/GND, DIR->GND, SDA->GPIO22, SCL->GPIO21.
// Sensor 2 (Wire1): AS5600 3.3V/GND, SDA->GPIO18, SCL->GPIO19. Eigener I2C-Bus,
//   da beide AS5600 dieselbe Adresse 0x36 haben (finale Version nutzt TCA9548A, siehe MA-10-003).
// Stepper 1: ULN2003 IN1->GPIO25, IN2->GPIO26, IN3->GPIO27, IN4->GPIO14.
// Stepper 2: ULN2003 IN1->GPIO32, IN2->GPIO4,  IN3->GPIO16, IN4->GPIO17.
// Beide Stepper eigene 5V-Versorgung (getrennt vom ESP32-USB-Rail, GND gemeinsam).
//
// Geschwindigkeitsregler (nur Sensor1+Stepper1, siehe M10 "Geschwindigkeit"):
// Kein mechanischer Anschlag am Regler vorhanden -> 0% = Position beim Boot,
// 100% = 175 Grad davon entfernt (Sollbereich, frei gewaehlt). Uebersetzung
// Motor->Zahnrad->Regler ist unbekannt und wird beim Boot einmalig real
// ausgemessen (kurze Testbewegung + Winkel-Differenz), nicht geraten.
// Sollwert 0-100 ueber Serial eingeben (Zahl + Enter).

#include <Wire.h>

constexpr uint8_t AS5600_ADDR = 0x36;
constexpr uint8_t AS5600_REG_RAW_ANGLE_H = 0x0C;
constexpr uint8_t AS5600_REG_STATUS = 0x0B;
constexpr uint8_t AS5600_REG_AGC = 0x1A;

constexpr int PIN1_SDA = 22;
constexpr int PIN1_SCL = 21;
constexpr int PIN2_SDA = 18;
constexpr int PIN2_SCL = 19;

constexpr uint8_t STEPPER1_IN1 = 25;
constexpr uint8_t STEPPER1_IN2 = 26;
constexpr uint8_t STEPPER1_IN3 = 27;
constexpr uint8_t STEPPER1_IN4 = 14;

constexpr uint8_t STEPPER2_IN1 = 32;
constexpr uint8_t STEPPER2_IN2 = 4;
constexpr uint8_t STEPPER2_IN3 = 16;
constexpr uint8_t STEPPER2_IN4 = 17;

TwoWire &busSensor1 = Wire;
TwoWire &busSensor2 = Wire1;

// Halbschritt-Sequenz (8 Schritte), ruhiger als Vollschritt.
const uint8_t HALF_STEP_SEQUENCE[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1},
};

struct Stepper {
  uint8_t in1, in2, in3, in4;
  int stepIndex = 0;
  uint32_t lastStepAt = 0;
};

Stepper stepper1{STEPPER1_IN1, STEPPER1_IN2, STEPPER1_IN3, STEPPER1_IN4};
Stepper stepper2{STEPPER2_IN1, STEPPER2_IN2, STEPPER2_IN3, STEPPER2_IN4};

constexpr uint32_t STEP_INTERVAL_MS = 3;

uint32_t lastPrintAt = 0;
constexpr uint32_t PRINT_INTERVAL_MS = 200;

void stepperPinMode(const Stepper &s) {
  pinMode(s.in1, OUTPUT);
  pinMode(s.in2, OUTPUT);
  pinMode(s.in3, OUTPUT);
  pinMode(s.in4, OUTPUT);
}

void writeStepperPins(const Stepper &s, int idx) {
  digitalWrite(s.in1, HALF_STEP_SEQUENCE[idx][0]);
  digitalWrite(s.in2, HALF_STEP_SEQUENCE[idx][1]);
  digitalWrite(s.in3, HALF_STEP_SEQUENCE[idx][2]);
  digitalWrite(s.in4, HALF_STEP_SEQUENCE[idx][3]);
}

void stepperOff(const Stepper &s) {
  digitalWrite(s.in1, LOW);
  digitalWrite(s.in2, LOW);
  digitalWrite(s.in3, LOW);
  digitalWrite(s.in4, LOW);
}

// dir=+1 vorwaerts (stepIndex steigt), dir=-1 rueckwaerts.
void stepOnce(Stepper &s, int dir) {
  s.stepIndex = (s.stepIndex + (dir > 0 ? 1 : 7)) % 8;
  writeStepperPins(s, s.stepIndex);
}

void updateStepper(Stepper &s, uint32_t now, bool run) {
  if (!run) {
    stepperOff(s);
    return;
  }
  if (now - s.lastStepAt >= STEP_INTERVAL_MS) {
    s.lastStepAt = now;
    stepOnce(s, 1);
  }
}

bool readAS5600(TwoWire &bus, uint16_t &rawAngle, uint8_t &status, uint8_t &agc) {
  bus.beginTransmission(AS5600_ADDR);
  bus.write(AS5600_REG_RAW_ANGLE_H);
  if (bus.endTransmission(false) != 0) {
    return false;
  }
  if (bus.requestFrom((int)AS5600_ADDR, 2) != 2) {
    return false;
  }
  uint8_t hi = bus.read();
  uint8_t lo = bus.read();
  rawAngle = ((uint16_t)(hi & 0x0F) << 8) | lo;

  bus.beginTransmission(AS5600_ADDR);
  bus.write(AS5600_REG_STATUS);
  if (bus.endTransmission(false) != 0) {
    return false;
  }
  if (bus.requestFrom((int)AS5600_ADDR, 1) != 1) {
    return false;
  }
  status = bus.read();

  bus.beginTransmission(AS5600_ADDR);
  bus.write(AS5600_REG_AGC);
  if (bus.endTransmission(false) != 0) {
    return false;
  }
  if (bus.requestFrom((int)AS5600_ADDR, 1) != 1) {
    return false;
  }
  agc = bus.read();
  return true;
}

bool readAngleDeg(TwoWire &bus, float &degOut) {
  uint16_t rawAngle;
  uint8_t status, agc;
  if (!readAS5600(bus, rawAngle, status, agc)) {
    return false;
  }
  degOut = (rawAngle * 360.0f) / 4096.0f;
  return true;
}

// Kuerzester vorzeichenbehafteter Winkelabstand von "from" nach "to" (-180..180).
float angleDiff(float from, float to) {
  float d = fmodf(to - from + 540.0f, 360.0f) - 180.0f;
  return d;
}

void scanBus(TwoWire &bus, const char *label) {
  Serial.print("I2C-Scan ");
  Serial.print(label);
  Serial.println(" (0x01-0x7F):");
  int foundCount = 0;
  for (uint8_t addr = 1; addr < 127; addr++) {
    bus.beginTransmission(addr);
    if (bus.endTransmission() == 0) {
      Serial.print("  Geraet gefunden an 0x");
      Serial.println(addr, HEX);
      foundCount++;
    }
  }
  if (foundCount == 0) {
    Serial.println("  KEIN Geraet gefunden - I2C-Bus tot (Verkabelung/Spannung pruefen)");
  }
}

void printAS5600(const char *label, TwoWire &bus) {
  uint16_t rawAngle = 0;
  uint8_t status = 0;
  uint8_t agc = 0;
  if (readAS5600(bus, rawAngle, status, agc)) {
    float degrees = (rawAngle * 360.0f) / 4096.0f;
    bool magnetDetected = status & 0x20;
    bool magnetTooStrong = status & 0x08;
    bool magnetTooWeak = status & 0x10;
    Serial.print(label);
    Serial.print(" raw=");
    Serial.print(rawAngle);
    Serial.print(" deg=");
    Serial.print(degrees, 1);
    Serial.print(" magnet=");
    Serial.print(magnetDetected ? "OK" : "FEHLT");
    if (magnetTooStrong) Serial.print(" (zu stark)");
    if (magnetTooWeak) Serial.print(" (zu schwach)");
    // AGC bei 3.3V: 0-128, 0=starkes Feld (wenig Verstaerkung noetig), 128=Feld am Limit
    Serial.print(" AGC=");
    Serial.print(agc);
    Serial.print("/128");
    Serial.println();
  } else {
    Serial.print(label);
    Serial.println(" read FEHLER (I2C keine Antwort)");
  }
}

// ---------- Geschwindigkeitsregler (Sensor1 + Stepper1) ----------

constexpr float SPEED_RANGE_DEG = 175.0f;  // 0-100% Sollbereich, frei gewaehlt (kein Anschlag)
constexpr int CALIBRATION_TEST_STEPS = 300;
// AS5600 laeuft hier bei AGC=128/128 (Magnetfeld zu schwach, siehe HARDWARE.md) und
// rauscht dadurch mehrere Grad um den Ruhewert - Toleranz muss deutlich groesser als
// dieses Rauschen sein, sonst haelt der Regelkreis nie an (staendiges Nachkorrigieren).
constexpr float POSITION_TOLERANCE_DEG = 4.0f;
constexpr float MANUAL_DEADBAND_DEG = 7.0f;
constexpr uint32_t SPEED_STEP_INTERVAL_MS = 4;

bool speedControlCalibrated = false;
float speedZeroAngleDeg = 0.0f;
float speedDegPerStep = 0.0f;
int speedTargetPercent = 0;
uint32_t lastSpeedStepAt = 0;
bool speedHolding = false;
float speedHoldAngleDeg = 0.0f;

void calibrateSpeedControl() {
  Serial.println("--- Kalibrierung Geschwindigkeitsregler (Sensor1+Stepper1) ---");
  float startDeg;
  if (!readAngleDeg(busSensor1, startDeg)) {
    Serial.println("Kalibrierung FEHLGESCHLAGEN: Sensor1 nicht lesbar.");
    return;
  }

  for (int i = 0; i < CALIBRATION_TEST_STEPS; i++) {
    stepOnce(stepper1, 1);
    delay(STEP_INTERVAL_MS);
  }
  delay(50);

  float endDeg;
  if (!readAngleDeg(busSensor1, endDeg)) {
    Serial.println("Kalibrierung FEHLGESCHLAGEN: Sensor1 nach Testbewegung nicht lesbar.");
    return;
  }

  float delta = angleDiff(startDeg, endDeg);

  // Zurueck zur Startposition (Startpunkt bleibt 0%-Referenz).
  for (int i = 0; i < CALIBRATION_TEST_STEPS; i++) {
    stepOnce(stepper1, -1);
    delay(STEP_INTERVAL_MS);
  }
  stepperOff(stepper1);

  if (fabsf(delta) < 0.5f) {
    Serial.println("Kalibrierung FEHLGESCHLAGEN: keine messbare Winkelaenderung (Stepper dreht nicht durch/Sensor haengt fest?).");
    return;
  }

  speedDegPerStep = delta / CALIBRATION_TEST_STEPS;
  speedZeroAngleDeg = startDeg;
  speedControlCalibrated = true;

  float stepsFor175 = fabsf(SPEED_RANGE_DEG / speedDegPerStep);
  Serial.print("Kalibrierung OK: ");
  Serial.print(CALIBRATION_TEST_STEPS);
  Serial.print(" Schritte = ");
  Serial.print(delta, 2);
  Serial.print(" Grad -> ");
  Serial.print(speedDegPerStep, 4);
  Serial.print(" Grad/Schritt, 175 Grad = ");
  Serial.print(stepsFor175, 0);
  Serial.println(" Schritte.");
}

void handleSpeedControlSerial() {
  static String line;
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length() > 0) {
        int value = line.toInt();
        value = constrain(value, 0, 100);
        speedTargetPercent = value;
        speedHolding = false;
        Serial.print("Neuer Sollwert: ");
        Serial.print(speedTargetPercent);
        Serial.println("%");
        line = "";
      }
    } else if (isDigit(c)) {
      line += c;
    }
  }
}

// sign(speedDegPerStep) * SPEED_RANGE_DEG: Drehrichtung wie bei der Kalibrierung.
float speedSignedRangeDeg() {
  return speedDegPerStep * fabsf(SPEED_RANGE_DEG / speedDegPerStep);
}

int percentFromAngle(float deg) {
  float signedRange = speedSignedRangeDeg();
  float percent = (angleDiff(speedZeroAngleDeg, deg) / signedRange) * 100.0f;
  return constrain((int)roundf(percent), 0, 100);
}

// MA-10-015: manuelle Bewegung erkennen und uebernehmen, statt dagegenzuhalten.
// Der Motor haelt (aus) sobald Ziel erreicht ist; weicht der gemessene Winkel dann
// ohne eigenes Zutun (Stepper aus) ab, war das eine Handbewegung -> neuer Sollwert.
void updateSpeedControl(uint32_t now) {
  if (!speedControlCalibrated) {
    return;
  }
  if (now - lastSpeedStepAt < SPEED_STEP_INTERVAL_MS) {
    return;
  }

  float currentDeg;
  if (!readAngleDeg(busSensor1, currentDeg)) {
    return;
  }

  if (speedHolding) {
    float manualDrift = angleDiff(speedHoldAngleDeg, currentDeg);
    if (fabsf(manualDrift) > MANUAL_DEADBAND_DEG) {
      int newPercent = percentFromAngle(currentDeg);
      if (newPercent != speedTargetPercent) {
        speedTargetPercent = newPercent;
        Serial.print("Manuell gedreht -> neuer Sollwert: ");
        Serial.print(speedTargetPercent);
        Serial.println("%");
      }
      speedHoldAngleDeg = currentDeg;
    }
    return;
  }

  float targetDeg = speedZeroAngleDeg + speedSignedRangeDeg() * (speedTargetPercent / 100.0f);
  float error = angleDiff(currentDeg, targetDeg);

  if (fabsf(error) <= POSITION_TOLERANCE_DEG) {
    stepperOff(stepper1);
    speedHolding = true;
    speedHoldAngleDeg = currentDeg;
    return;
  }

  lastSpeedStepAt = now;
  // error>0 heisst: Zielwinkel liegt "vorwaerts" (in Richtung steigender Grad ueber
  // angleDiff) von der aktuellen Position aus gesehen. Vorwaerts-Schritt (dir=+1)
  // aendert den Winkel um speedDegPerStep; Vorzeichen von speedDegPerStep beruecksichtigen.
  bool wantIncrease = error > 0;
  bool forwardIncreases = speedDegPerStep >= 0;
  int dir = (wantIncrease == forwardIncreases) ? 1 : -1;
  stepOnce(stepper1, dir);
}

void setup() {
  Serial.begin(115200);
  delay(300);
  Serial.println("=== M10 Bring-up: 2x AS5600 + 2x 28BYJ-48/ULN2003 ===");

  stepperPinMode(stepper1);
  stepperPinMode(stepper2);
  writeStepperPins(stepper1, 0);
  writeStepperPins(stepper2, 0);

  busSensor1.begin(PIN1_SDA, PIN1_SCL);
  busSensor1.setClock(100000);
  busSensor2.begin(PIN2_SDA, PIN2_SCL);
  busSensor2.setClock(100000);

  scanBus(busSensor1, "Sensor1");
  scanBus(busSensor2, "Sensor2");

  calibrateSpeedControl();
  Serial.println("Sollwert 0-100 per Serial eingeben (Zahl + Enter) zum Testen.");
}

constexpr uint32_t STEPPER2_RUN_DURATION_MS = 4000;

void loop() {
  uint32_t now = millis();

  handleSpeedControlSerial();
  updateSpeedControl(now);
  updateStepper(stepper2, now, now < STEPPER2_RUN_DURATION_MS);

  if (now - lastPrintAt >= PRINT_INTERVAL_MS) {
    lastPrintAt = now;
    printAS5600("Sensor1", busSensor1);
    printAS5600("Sensor2", busSensor2);
  }
}
