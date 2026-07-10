#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint16_t DEBOUNCE_MS = 40;
constexpr uint16_t STATUS_INTERVAL_MS = 500;
constexpr uint16_t ANIMATION_INTERVAL_MS = 35;

constexpr uint8_t BUTTON_PINS[10] = {33, 15, 25, 35, 14, 27, 34, 13, 26, 32};
constexpr uint8_t FAN_PIN = 22;
constexpr uint8_t NEOPIXEL_PIN = 0;
constexpr uint16_t NEOPIXEL_COUNT = 75;

Adafruit_NeoPixel pixels(NEOPIXEL_COUNT, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

struct ButtonState {
  bool stablePressed = false;
  bool lastRawPressed = false;
  uint32_t changedAt = 0;
};

struct VehicleState {
  bool highBeam = false;
  bool lowBeam = false;
  bool underbody = false;
  bool leftIndicator = false;
  bool rightIndicator = false;
  bool hazard = false;
  bool fan = false;
};

ButtonState buttons[10];
VehicleState state;
uint32_t lastStatusAt = 0;
uint32_t lastAnimationAt = 0;
uint32_t animationStep = 0;

void setAllPixels(uint32_t color) {
  for (uint16_t i = 0; i < NEOPIXEL_COUNT; i++) pixels.setPixelColor(i, color);
}

void updateOutputs() {
  digitalWrite(FAN_PIN, state.fan ? HIGH : LOW);
}

void updatePixels() {
  const uint32_t now = millis();
  if (now - lastAnimationAt < ANIMATION_INTERVAL_MS) return;
  lastAnimationAt = now;
  pixels.clear();

  if (state.hazard) {
    constexpr uint8_t trailLength = 10;
    const uint16_t head = animationStep % NEOPIXEL_COUNT;
    for (uint8_t offset = 0; offset < trailLength; offset++) {
      const uint16_t index = (head + NEOPIXEL_COUNT - offset) % NEOPIXEL_COUNT;
      const uint8_t brightness = 255 - (offset * 20);
      pixels.setPixelColor(index, pixels.Color(brightness, brightness / 3, 0));
    }
    animationStep++;
  } else if (state.underbody) {
    setAllPixels(pixels.Color(0, 120, 180));
  }

  pixels.show();
}

void sendStatus() {
  Serial.print("{\"device\":\"esp32_actor\",\"states\":{");
  Serial.print("\"highBeam\":"); Serial.print(state.highBeam ? "true" : "false");
  Serial.print(",\"lowBeam\":"); Serial.print(state.lowBeam ? "true" : "false");
  Serial.print(",\"underbody\":"); Serial.print(state.underbody ? "true" : "false");
  Serial.print(",\"leftIndicator\":"); Serial.print(state.leftIndicator ? "true" : "false");
  Serial.print(",\"rightIndicator\":"); Serial.print(state.rightIndicator ? "true" : "false");
  Serial.print(",\"hazard\":"); Serial.print(state.hazard ? "true" : "false");
  Serial.print(",\"fan\":"); Serial.print(state.fan ? "true" : "false");
  Serial.print("},\"buttons\":[");
  for (uint8_t i = 0; i < 10; i++) {
    if (i > 0) Serial.print(',');
    Serial.print(buttons[i].stablePressed ? "true" : "false");
  }
  Serial.println("]}");
}

void disableHazard() {
  state.hazard = false;
  state.leftIndicator = false;
  state.rightIndicator = false;
}

void handleButtonPress(uint8_t index) {
  switch (index) {
    case 0: state.highBeam = !state.highBeam; break;
    case 1: state.lowBeam = !state.lowBeam; break;
    case 2: state.underbody = !state.underbody; break;
    case 3:
      if (state.hazard) disableHazard();
      state.leftIndicator = !state.leftIndicator;
      break;
    case 4:
      if (state.hazard) disableHazard();
      state.rightIndicator = !state.rightIndicator;
      break;
    case 5:
      if (state.hazard) {
        disableHazard();
      } else {
        state.hazard = true;
        state.leftIndicator = true;
        state.rightIndicator = true;
      }
      break;
    case 6: state.fan = !state.fan; break;
    case 7: case 8: case 9: break;
  }

  updateOutputs();
  sendStatus();
}

void readButtons() {
  const uint32_t now = millis();
  for (uint8_t i = 0; i < 10; i++) {
    const bool rawPressed = digitalRead(BUTTON_PINS[i]) == LOW;
    if (rawPressed != buttons[i].lastRawPressed) {
      buttons[i].lastRawPressed = rawPressed;
      buttons[i].changedAt = now;
    }
    if ((now - buttons[i].changedAt) >= DEBOUNCE_MS && rawPressed != buttons[i].stablePressed) {
      buttons[i].stablePressed = rawPressed;
      if (buttons[i].stablePressed) handleButtonPress(i);
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  for (uint8_t pin : BUTTON_PINS) pinMode(pin, INPUT);
  pinMode(FAN_PIN, OUTPUT);
  digitalWrite(FAN_PIN, LOW);

  pixels.begin();
  pixels.setBrightness(180);
  pixels.clear();
  pixels.show();

  delay(300);
  sendStatus();
}

void loop() {
  readButtons();
  updatePixels();
  const uint32_t now = millis();
  if (now - lastStatusAt >= STATUS_INTERVAL_MS) {
    lastStatusAt = now;
    sendStatus();
  }
  delay(5);
}
