#include <Arduino.h>
#include <Adafruit_NeoPixel.h>

// -----------------------------
// Hardware
// -----------------------------
constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint16_t DEBOUNCE_MS = 40;
constexpr uint16_t STATUS_INTERVAL_MS = 500;

// Bekannte Tasterbelegung aus dem MesseAuto-Projekt.
constexpr uint8_t BUTTON_PINS[10] = {33, 15, 25, 35, 14, 27, 34, 13, 26, 32};

// Direkte Ausgänge am ESP32.
constexpr uint8_t FAN_PIN = 22;
constexpr uint8_t NEOPIXEL_PIN = 0;
constexpr uint16_t NEOPIXEL_COUNT = 75;

Adafruit_NeoPixel pixels(NEOPIXEL_COUNT, NEOPIXEL_PIN, NEO_GRB + NEO_KHZ800);

struct ButtonState {
  bool stablePressed = false;
  bool lastRawPressed = false;
  uint32_t changedAt = 0;
};

ButtonState buttons[10];

struct VehicleState {
  bool highBeam = false;
  bool lowBeam = false;
  bool underbody = false;
  bool leftIndicator = false;
  bool rightIndicator = false;
  bool hazard = false;
  bool fan = false;
};

VehicleState state;
uint32_t lastStatusAt = 0;
uint32_t animationStep = 0;


void setAllPixels(uint32_t color) {
  for (uint16_t i = 0; i < NEOPIXEL_COUNT; i++) {
    pixels.setPixelColor(i, color);
  }
}


void updateOutputs() {
  digitalWrite(FAN_PIN, state.fan ? HIGH : LOW);
}


void updatePixels() {
  pixels.clear();

  if (state.hazard) {
    // Schnelles oranges Lauflicht, ca. 10 Pixel lang.
    constexpr uint8_t trailLength = 10;
    uint16_t head = animationStep % NEOPIXEL_COUNT;
    for (uint8_t offset = 0; offset < trailLength; offset++) {
      uint16_t index = (head + NEOPIXEL_COUNT - offset) % NEOPIXEL_COUNT;
      uint8_t brightness = 255 - (offset * 20);
      pixels.setPixelColor(index, pixels.Color(brightness, brightness / 3, 0));
    }
    animationStep++;
  } else if (state.underbody) {
    // Ruhige cyanfarbene Unterbodenbeleuchtung.
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
  Serial.println("}}");
}


void handleButtonPress(uint8_t index) {
  switch (index) {
    case 0: state.highBeam = !state.highBeam; break;
    case 1: state.lowBeam = !state.lowBeam; break;
    case 2: state.underbody = !state.underbody; break;
    case 3:
      state.leftIndicator = !state.leftIndicator;
      if (state.leftIndicator) state.hazard = false;
      break;
    case 4:
      state.rightIndicator = !state.rightIndicator;
      if (state.rightIndicator) state.hazard = false;
      break;
    case 5:
      state.hazard = !state.hazard;
      if (state.hazard) {
        state.leftIndicator = true;
        state.rightIndicator = true;
      } else {
        state.leftIndicator = false;
        state.rightIndicator = false;
      }
      break;
    case 6: state.fan = !state.fan; break;
    case 7: break;  // Reserve
    case 8: break;  // Reserve
    case 9: break;  // Reserve
  }

  updateOutputs();
  sendStatus();
}


void readButtons() {
  const uint32_t now = millis();

  for (uint8_t i = 0; i < 10; i++) {
    // Externe Pull-ups: gedrückt = LOW.
    bool rawPressed = digitalRead(BUTTON_PINS[i]) == LOW;

    if (rawPressed != buttons[i].lastRawPressed) {
      buttons[i].lastRawPressed = rawPressed;
      buttons[i].changedAt = now;
    }

    if ((now - buttons[i].changedAt) >= DEBOUNCE_MS &&
        rawPressed != buttons[i].stablePressed) {
      buttons[i].stablePressed = rawPressed;
      if (buttons[i].stablePressed) {
        handleButtonPress(i);
      }
    }
  }
}


void setup() {
  Serial.begin(SERIAL_BAUDRATE);

  for (uint8_t pin : BUTTON_PINS) {
    pinMode(pin, INPUT);
  }

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

  delay(20);
}
