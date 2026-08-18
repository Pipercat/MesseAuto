#include <Wire.h>
#include <Adafruit_NeoPixel.h>

// === AS5600 Setup ===
#define AS5600_ADDR 0x36

// === Stepper Setup ===
const int motorPins[4] = {18, 19, 20, 21};
const int stepsPerRevolution = 2048;
const int halfStepsPerRevolution = stepsPerRevolution * 2;

float maxSpeed = 600.0;  // Steps per second
unsigned long stepIntervalMicros;
unsigned long lastStepTime = 0;
long currentStep = 0;
int stepIndex = 0;
bool motorEnabled = false;

// === Stepper Half-Step Sequence ===
const int stepSequence[8][4] = {
  {1, 0, 0, 0},
  {1, 1, 0, 0},
  {0, 1, 0, 0},
  {0, 1, 1, 0},
  {0, 0, 1, 0},
  {0, 0, 1, 1},
  {0, 0, 0, 1},
  {1, 0, 0, 1}
};

// === NeoPixel Setup ===
#define NEOPIXEL_PIN 28
#define NUM_PIXELS 12
Adafruit_NeoPixel pixels(NUM_PIXELS, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

// === Helper Functions ===
void stepMotor(int direction) {
  stepIndex += direction;
  if (stepIndex > 7) stepIndex = 0;
  if (stepIndex < 0) stepIndex = 7;

  for (int i = 0; i < 4; i++) {
    digitalWrite(motorPins[i], stepSequence[stepIndex][i]);
  }
}

void releaseMotor() {
  for (int i = 0; i < 4; i++) digitalWrite(motorPins[i], LOW);
}

uint16_t readAS5600Raw() {
  Wire.beginTransmission(AS5600_ADDR);
  Wire.write(0x0E);
  Wire.endTransmission(false);
  Wire.requestFrom(AS5600_ADDR, 2);
  if (Wire.available() == 2) {
    uint8_t highByte = Wire.read();
    uint8_t lowByte = Wire.read();
    return ((highByte & 0x0F) << 8) | lowByte;
  }
  return 0;
}

float readAS5600Degrees() {
  return (readAS5600Raw() * 360.0) / 4096.0;
}

void showAngleColor(float angle) {
  // Clamp to 0–180° for colour scaling
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;

  float ratio;
  uint8_t r, g, b;

  if (angle <= 90) {
    // Green → Orange
    ratio = angle / 90.0;
    r = 255 * ratio;
    g = 255;
    b = 0;
  } else {
    // Orange → Red
    ratio = (angle - 90) / 90.0;
    r = 255;
    g = 255 * (1.0 - ratio);
    b = 0;
  }

  for (int i = 0; i < NUM_PIXELS; i++) {
    pixels.setPixelColor(i, pixels.Color(r, g, b));
  }
  pixels.show();
}

// === Setup ===
void setup() {
  Serial.begin(115200);
  while (!Serial);
  Serial.println("AS5600 Stepper Controller Ready");
  Serial.println("Enter target angle (0–360):");

  Wire.begin();
  pixels.begin();
  pixels.clear();
  pixels.show();

  for (int i = 0; i < 4; i++) {
    pinMode(motorPins[i], OUTPUT);
    digitalWrite(motorPins[i], LOW);
  }

  stepIntervalMicros = 1000000.0 / maxSpeed;
}

// === Main Loop ===
void loop() {
  static String input = "";

  // --- Read user input ---
  while (Serial.available()) {
    char ch = Serial.read();
    if (ch == '\n' || ch == '\r') {
      if (input.length() > 0) {
        float targetAngle = input.toFloat();
        input = "";

        float currentAngle = readAS5600Degrees();
        long targetStep = (targetAngle / 360.0) * halfStepsPerRevolution;
        long currentStepFromSensor = (currentAngle / 360.0) * halfStepsPerRevolution;

        Serial.print("Moving from ");
        Serial.print(currentAngle, 2);
        Serial.print("° to ");
        Serial.print(targetAngle, 2);
        Serial.println("°");

        motorEnabled = true;

        while (abs(currentStepFromSensor - targetStep) > 5) {
          int direction = (targetStep > currentStepFromSensor) ? 1 : -1;
          unsigned long now = micros();
          if (now - lastStepTime >= stepIntervalMicros) {
            if (motorEnabled) stepMotor(direction);
            lastStepTime = now;
          }

          currentAngle = readAS5600Degrees();
          currentStepFromSensor = (currentAngle / 360.0) * halfStepsPerRevolution;
          showAngleColor(currentAngle);
        }

        releaseMotor();
        motorEnabled = false;
        Serial.println("Target angle reached.\nEnter next angle:");
      }
    } else {
      input += ch;
    }
  }

  // --- Live color update even when motor is free ---
  float liveAngle = readAS5600Degrees();
  showAngleColor(liveAngle);
  delay(100);
}
