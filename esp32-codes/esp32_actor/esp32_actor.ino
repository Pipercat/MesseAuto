// MesseAuto ESP32 Standalone-Aktor
//
// Zielaufbau:
// - Der ESP32 wird einmal per PC/Mac geflasht.
// - Im Messebetrieb gibt es KEINE Serial-Verbindung zum Raspberry Pi.
// - Echte Buttons und Pi-Relaiskontakte liegen parallel auf denselben
//   ESP32-Eingaengen.
// - Ein Tastendruck oder ein kurzer Relaiskontakt zieht den Eingang auf LOW.
// - Der ESP32 behandelt beides gleich und schaltet intern die Funktion.

#include <Arduino.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "wifi_credentials.h"

constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint16_t DEBOUNCE_MS = 40;
constexpr uint16_t STATUS_INTERVAL_MS = 2000;
constexpr uint16_t BLINK_INTERVAL_MS = 420;
constexpr uint16_t PIXEL_ANIMATION_INTERVAL_MS = 35;

// Button-Reihenfolge:
// 1 Fernlicht, 2 Abblendlicht, 3 Unterboden, 4 Blinker links,
// 5 Blinker rechts, 6 Warnblinker, 7 Luefter, 8-10 Reserve.
constexpr uint8_t BUTTON_COUNT = 10;
constexpr uint8_t BUTTON_PINS[BUTTON_COUNT] = {33, 15, 25, 35, 14, 27, 34, 13, 26, 32};

// Ausgangsbelegung am Fahrzeug. Die Eingangsbelegung oben bleibt unveraendert.
constexpr uint8_t LOW_BEAM_PIN = 18;
constexpr uint8_t HIGH_BEAM_PIN = 19;
constexpr uint8_t INDICATOR_LEFT_PIN = 17;
constexpr uint8_t INDICATOR_RIGHT_PIN = 5;
constexpr uint8_t UNDERBODY_PIXEL_PIN = 0;
constexpr uint16_t UNDERBODY_PIXEL_COUNT = 75;
constexpr uint8_t FAN_PIN = 22;
constexpr uint8_t FREE_ONE_PIN = 25;
constexpr uint8_t FREE_TWO_PIN = 26;
constexpr uint8_t FREE_THREE_PIN = 27;

// GPIO25/26/27 sind laut aktueller Eingangsbelegung bereits Buttonpins.
// Solange die ESP-Eingaenge gleich bleiben, werden diese Ausgaenge nicht aktiv
// getrieben, damit Blinker-/Warnblinker-Eingaben nicht kaputtgehen.
constexpr bool PRESERVE_BUTTON_INPUTS = true;
constexpr bool OUTPUT_ACTIVE_HIGH = true;

// LOW bedeutet gedrueckt. Bei Pins 34/35 gibt es keine internen Pullups.
// Wenn diese Pins genutzt werden, braucht die Hardware externe Pullups.
constexpr bool USE_INTERNAL_PULLUPS_WHERE_POSSIBLE = true;

const char *BUTTON_FUNCTIONS[BUTTON_COUNT] = {
  "highBeam",
  "lowBeam",
  "underbody",
  "leftIndicator",
  "rightIndicator",
  "hazard",
  "fan",
  "freeOne",
  "freeTwo",
  "freeThree"
};

const char *BUTTON_OUTPUTS[BUTTON_COUNT] = {
  "GPIO19",
  "GPIO18",
  "NeoPixel GPIO0 rainbow",
  "GPIO17 blink",
  "GPIO5 blink",
  "GPIO17+GPIO5+NeoPixel GPIO0 orange_chase",
  "GPIO22",
  "GPIO25 input_preserved",
  "GPIO26 input_preserved",
  "GPIO27 input_preserved"
};

Adafruit_NeoPixel underbodyPixels(
  UNDERBODY_PIXEL_COUNT,
  UNDERBODY_PIXEL_PIN,
  NEO_GRB + NEO_KHZ800
);

// --- MesseCar WLAN/MQTT (MA-04-001/002/003/004) ---
//
// Der lokale MesseCar-AP hat keinen Internetzugang, also keine NTP-Zeit
// verfuegbar. `timestamp_ms` in ESP-Nachrichten ist deshalb bewusst
// `millis()` (Geraete-Uptime) statt echter Unix-Zeit wie bei Pi 1 - siehe
// MQTT.md. Fuer Reihenfolge/Aktualitaet innerhalb einer ESP-Session reicht
// das aus; ein Vergleich mit Pi-1-Zeitstempeln ist nicht sinnvoll.
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 5000;
constexpr uint32_t MQTT_RETRY_INTERVAL_MS = 3000;
constexpr const char *MQTT_CLIENT_ID = "esp_actor";
constexpr const char *TOPIC_STATUS = "messecar/actor/status";
constexpr const char *TOPIC_EVENT_BUTTON = "messecar/actor/event/button";
constexpr const char *TOPIC_STATE = "messecar/actor/state";
constexpr const char *TOPIC_COMMAND = "messecar/actor/command";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
uint32_t lastWifiAttemptAt = 0;
uint32_t lastMqttAttemptAt = 0;

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
  bool freeOne = false;
  bool freeTwo = false;
  bool freeThree = false;
};

ButtonState buttons[BUTTON_COUNT];
VehicleState state;
String serialCommand;
uint32_t lastStatusAt = 0;
uint32_t lastPixelAnimationAt = 0;
uint16_t pixelAnimationStep = 0;

bool pinSupportsInternalPullup(uint8_t pin) {
  return pin != 34 && pin != 35 && pin != 36 && pin != 39;
}

void configureButtonInput(uint8_t pin) {
  if (USE_INTERNAL_PULLUPS_WHERE_POSSIBLE && pinSupportsInternalPullup(pin)) {
    pinMode(pin, INPUT_PULLUP);
  } else {
    pinMode(pin, INPUT);
  }
}

bool pinIsButtonInput(uint8_t pin) {
  for (uint8_t buttonPin : BUTTON_PINS) {
    if (buttonPin == pin) {
      return true;
    }
  }
  return false;
}

bool outputCanDrive(uint8_t pin) {
  return !PRESERVE_BUTTON_INPUTS || !pinIsButtonInput(pin);
}

uint8_t outputLevel(bool enabled) {
  if (OUTPUT_ACTIVE_HIGH) {
    return enabled ? HIGH : LOW;
  }
  return enabled ? LOW : HIGH;
}

void configureOutputPin(uint8_t pin) {
  if (!outputCanDrive(pin)) {
    return;
  }
  pinMode(pin, OUTPUT);
  digitalWrite(pin, outputLevel(false));
}

void writeOutputPin(uint8_t pin, bool enabled) {
  if (!outputCanDrive(pin)) {
    return;
  }
  digitalWrite(pin, outputLevel(enabled));
}

uint32_t wheelColor(uint8_t wheelPosition) {
  wheelPosition = 255 - wheelPosition;
  if (wheelPosition < 85) {
    return underbodyPixels.Color(255 - wheelPosition * 3, 0, wheelPosition * 3);
  }
  if (wheelPosition < 170) {
    wheelPosition -= 85;
    return underbodyPixels.Color(0, wheelPosition * 3, 255 - wheelPosition * 3);
  }
  wheelPosition -= 170;
  return underbodyPixels.Color(wheelPosition * 3, 255 - wheelPosition * 3, 0);
}

void updateOutputs() {
  const bool blinkOn = (millis() / BLINK_INTERVAL_MS) % 2 == 0;
  const bool leftBlink = (state.leftIndicator || state.hazard) && blinkOn;
  const bool rightBlink = (state.rightIndicator || state.hazard) && blinkOn;

  writeOutputPin(HIGH_BEAM_PIN, state.highBeam);
  writeOutputPin(LOW_BEAM_PIN, state.lowBeam);
  writeOutputPin(INDICATOR_LEFT_PIN, leftBlink);
  writeOutputPin(INDICATOR_RIGHT_PIN, rightBlink);
  writeOutputPin(FAN_PIN, state.fan);
  writeOutputPin(FREE_ONE_PIN, state.freeOne);
  writeOutputPin(FREE_TWO_PIN, state.freeTwo);
  writeOutputPin(FREE_THREE_PIN, state.freeThree);
}

void updateUnderbodyPixels() {
  const uint32_t now = millis();
  if (now - lastPixelAnimationAt < PIXEL_ANIMATION_INTERVAL_MS) {
    return;
  }
  lastPixelAnimationAt = now;

  underbodyPixels.clear();

  if (state.hazard) {
    constexpr uint8_t trailLength = 14;
    const uint16_t head = pixelAnimationStep % UNDERBODY_PIXEL_COUNT;
    for (uint8_t offset = 0; offset < trailLength; offset++) {
      const uint16_t index = (head + UNDERBODY_PIXEL_COUNT - offset) % UNDERBODY_PIXEL_COUNT;
      const uint8_t brightness = 255 - (offset * 14);
      underbodyPixels.setPixelColor(index, underbodyPixels.Color(brightness, brightness / 3, 0));
    }
    pixelAnimationStep += 1;
  } else if (state.underbody) {
    for (uint16_t index = 0; index < UNDERBODY_PIXEL_COUNT; index++) {
      const uint8_t colorIndex = ((index * 256 / UNDERBODY_PIXEL_COUNT) + pixelAnimationStep) & 255;
      underbodyPixels.setPixelColor(index, wheelColor(colorIndex));
    }
    pixelAnimationStep += 2;
  }

  underbodyPixels.show();
}

void printBoolJson(bool value) {
  Serial.print(value ? "true" : "false");
}

void publishStatus(const char *status, bool retain) {
  if (!mqttClient.connected()) {
    return;
  }
  JsonDocument doc;
  doc["device"] = "esp_actor";
  doc["timestamp_ms"] = millis();
  doc["status"] = status;
  char buffer[128];
  serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(TOPIC_STATUS, buffer, retain);
}

void publishActorState() {
  if (!mqttClient.connected()) {
    return;
  }
  JsonDocument doc;
  doc["device"] = "esp_actor";
  doc["timestamp_ms"] = millis();
  JsonObject outputs = doc["outputs"].to<JsonObject>();
  outputs["highBeam"] = state.highBeam;
  outputs["lowBeam"] = state.lowBeam;
  outputs["underbody"] = state.underbody;
  outputs["leftIndicator"] = state.leftIndicator;
  outputs["rightIndicator"] = state.rightIndicator;
  outputs["hazard"] = state.hazard;
  outputs["fan"] = state.fan;
  char buffer[256];
  serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(TOPIC_STATE, buffer, false);
}

void publishButtonEvent(uint8_t index, bool pressed) {
  if (!mqttClient.connected()) {
    return;
  }
  JsonDocument doc;
  doc["device"] = "esp_actor";
  doc["timestamp_ms"] = millis();
  doc["button"] = index + 1;
  doc["edge"] = pressed ? "pressed" : "released";
  char buffer[128];
  serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(TOPIC_EVENT_BUTTON, buffer, false);
}

void setStateByName(const String &name, bool enabled);

void handleMqttMessage(char *topic, byte *payload, unsigned int length) {
  JsonDocument doc;
  DeserializationError parseError = deserializeJson(doc, payload, length);
  if (parseError) {
    return;
  }
  if (!doc["device"].is<const char *>() || !doc["timestamp_ms"].is<long>()) {
    return;
  }
  const char *function = doc["function"] | "";
  if (function[0] == '\0') {
    return;
  }
  const bool value = doc["value"] | false;
  setStateByName(String(function), value);
}

void ensureWifiConnected() {
  if (WiFi.status() == WL_CONNECTED) {
    return;
  }
  const uint32_t now = millis();
  if (now != 0 && now - lastWifiAttemptAt < WIFI_RETRY_INTERVAL_MS) {
    return;
  }
  lastWifiAttemptAt = now;
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
}

void ensureMqttConnected() {
  if (WiFi.status() != WL_CONNECTED) {
    return;
  }
  if (mqttClient.connected()) {
    mqttClient.loop();
    return;
  }
  const uint32_t now = millis();
  if (now != 0 && now - lastMqttAttemptAt < MQTT_RETRY_INTERVAL_MS) {
    return;
  }
  lastMqttAttemptAt = now;

  JsonDocument willDoc;
  willDoc["device"] = "esp_actor";
  willDoc["status"] = "offline";
  char willBuffer[128];
  serializeJson(willDoc, willBuffer, sizeof(willBuffer));

  const bool connected = mqttClient.connect(
    MQTT_CLIENT_ID, TOPIC_STATUS, 1, true, willBuffer
  );
  if (connected) {
    mqttClient.subscribe(TOPIC_COMMAND, 1);
    publishStatus("online", true);
    publishActorState();
  }
}

void sendStatus(int8_t eventButton = -1) {
  Serial.print("{\"device\":\"esp32_actor\",\"mode\":\"standalone_buttons\",\"states\":{");
  Serial.print("\"highBeam\":"); printBoolJson(state.highBeam);
  Serial.print(",\"lowBeam\":"); printBoolJson(state.lowBeam);
  Serial.print(",\"underbody\":"); printBoolJson(state.underbody);
  Serial.print(",\"leftIndicator\":"); printBoolJson(state.leftIndicator);
  Serial.print(",\"rightIndicator\":"); printBoolJson(state.rightIndicator);
  Serial.print(",\"hazard\":"); printBoolJson(state.hazard);
  Serial.print(",\"fan\":"); printBoolJson(state.fan);
  Serial.print(",\"freeOne\":"); printBoolJson(state.freeOne);
  Serial.print(",\"freeTwo\":"); printBoolJson(state.freeTwo);
  Serial.print(",\"freeThree\":"); printBoolJson(state.freeThree);
  Serial.print("},\"buttons\":[");
  for (uint8_t i = 0; i < BUTTON_COUNT; i++) {
    if (i > 0) {
      Serial.print(',');
    }
    printBoolJson(buttons[i].stablePressed);
  }
  Serial.print(']');
  if (eventButton > 0) {
    Serial.print(",\"event_button\":");
    Serial.print(eventButton);
  }
  Serial.println('}');
}

void sendButtonLog(uint8_t index, bool pressed) {
  Serial.print("LOG ms=");
  Serial.print(millis());
  Serial.print(" event=button_");
  Serial.print(pressed ? "pressed" : "released");
  Serial.print(" button=");
  Serial.print(index + 1);
  Serial.print(" pin=GPIO");
  Serial.print(BUTTON_PINS[index]);
  Serial.print(" function=");
  Serial.println(BUTTON_FUNCTIONS[index]);
}

bool stateForButton(uint8_t index) {
  switch (index) {
    case 0: return state.highBeam;
    case 1: return state.lowBeam;
    case 2: return state.underbody;
    case 3: return state.leftIndicator;
    case 4: return state.rightIndicator;
    case 5: return state.hazard;
    case 6: return state.fan;
    case 7: return state.freeOne;
    case 8: return state.freeTwo;
    case 9: return state.freeThree;
    default: return false;
  }
}

void sendSwitchLog(uint8_t index) {
  Serial.print("LOG ms=");
  Serial.print(millis());
  Serial.print(" event=switch function=");
  Serial.print(BUTTON_FUNCTIONS[index]);
  Serial.print(" state=");
  Serial.print(stateForButton(index) ? "ON" : "OFF");
  Serial.print(" output=");
  Serial.println(BUTTON_OUTPUTS[index]);
}

void disableHazard() {
  state.hazard = false;
  state.leftIndicator = false;
  state.rightIndicator = false;
}

void setStateByName(const String &name, bool enabled) {
  if (name == "highBeam") {
    state.highBeam = enabled;
  } else if (name == "lowBeam") {
    state.lowBeam = enabled;
  } else if (name == "underbody") {
    state.underbody = enabled;
  } else if (name == "leftIndicator") {
    state.leftIndicator = enabled;
  } else if (name == "rightIndicator") {
    state.rightIndicator = enabled;
  } else if (name == "fan") {
    state.fan = enabled;
  } else if (name == "freeOne") {
    state.freeOne = enabled;
  } else if (name == "freeTwo") {
    state.freeTwo = enabled;
  } else if (name == "freeThree") {
    state.freeThree = enabled;
  } else if (name == "hazard") {
    state.hazard = enabled;
    state.leftIndicator = enabled;
    state.rightIndicator = enabled;
  } else {
    return;
  }

  updateOutputs();
  sendStatus();
  publishActorState();
}

// Nur fuer Werkbankdiagnose am PC. Im Messebetrieb haengt der ESP nicht am Pi.
void handleSerialCommand(String command) {
  command.trim();
  if (!command.startsWith("SET ")) {
    return;
  }

  const int secondSpace = command.indexOf(' ', 4);
  if (secondSpace < 0) {
    return;
  }

  const String name = command.substring(4, secondSpace);
  const String value = command.substring(secondSpace + 1);
  if (value != "0" && value != "1") {
    return;
  }

  setStateByName(name, value == "1");
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    const char c = static_cast<char>(Serial.read());
    if (c == '\n') {
      handleSerialCommand(serialCommand);
      serialCommand = "";
    } else if (c != '\r') {
      if (serialCommand.length() < 96) {
        serialCommand += c;
      } else {
        serialCommand = "";
      }
    }
  }
}

void handleButtonPress(uint8_t index) {
  switch (index) {
    case 0:
      state.highBeam = !state.highBeam;
      break;
    case 1:
      state.lowBeam = !state.lowBeam;
      break;
    case 2:
      state.underbody = !state.underbody;
      break;
    case 3:
      if (state.hazard) {
        disableHazard();
      }
      state.leftIndicator = !state.leftIndicator;
      break;
    case 4:
      if (state.hazard) {
        disableHazard();
      }
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
    case 6:
      state.fan = !state.fan;
      break;
    case 7:
      state.freeOne = !state.freeOne;
      break;
    case 8:
      state.freeTwo = !state.freeTwo;
      break;
    case 9:
      state.freeThree = !state.freeThree;
      break;
  }

  updateOutputs();
  updateUnderbodyPixels();
  sendSwitchLog(index);
  sendStatus(index + 1);
  publishActorState();
}

void readButtons() {
  const uint32_t now = millis();
  for (uint8_t i = 0; i < BUTTON_COUNT; i++) {
    const bool rawPressed = digitalRead(BUTTON_PINS[i]) == LOW;
    if (rawPressed != buttons[i].lastRawPressed) {
      buttons[i].lastRawPressed = rawPressed;
      buttons[i].changedAt = now;
    }
    if ((now - buttons[i].changedAt) >= DEBOUNCE_MS && rawPressed != buttons[i].stablePressed) {
      buttons[i].stablePressed = rawPressed;
      sendButtonLog(i, buttons[i].stablePressed);
      publishButtonEvent(i, buttons[i].stablePressed);
      if (buttons[i].stablePressed) {
        handleButtonPress(i);
      }
    }
  }
}

void initializeButtonStates() {
  const uint32_t now = millis();
  for (uint8_t i = 0; i < BUTTON_COUNT; i++) {
    const bool rawPressed = digitalRead(BUTTON_PINS[i]) == LOW;
    buttons[i].lastRawPressed = rawPressed;
    buttons[i].stablePressed = rawPressed;
    buttons[i].changedAt = now;
  }
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  serialCommand.reserve(96);

  for (uint8_t pin : BUTTON_PINS) {
    configureButtonInput(pin);
  }
  delay(120);
  initializeButtonStates();

  configureOutputPin(LOW_BEAM_PIN);
  configureOutputPin(HIGH_BEAM_PIN);
  configureOutputPin(INDICATOR_LEFT_PIN);
  configureOutputPin(INDICATOR_RIGHT_PIN);
  configureOutputPin(FAN_PIN);
  configureOutputPin(FREE_ONE_PIN);
  configureOutputPin(FREE_TWO_PIN);
  configureOutputPin(FREE_THREE_PIN);

  underbodyPixels.begin();
  underbodyPixels.setBrightness(180);
  underbodyPixels.clear();
  underbodyPixels.show();

  delay(300);
  updateOutputs();
  updateUnderbodyPixels();
  sendStatus();

  WiFi.mode(WIFI_STA);
  mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.setCallback(handleMqttMessage);
  mqttClient.setBufferSize(512);
}

void loop() {
  readSerialCommands();
  readButtons();
  updateOutputs();
  updateUnderbodyPixels();
  ensureWifiConnected();
  ensureMqttConnected();

  const uint32_t now = millis();
  if (now - lastStatusAt >= STATUS_INTERVAL_MS) {
    lastStatusAt = now;
    sendStatus();
    publishStatus("online", true);
    publishActorState();
  }

  delay(5);
}
