// MesseAuto ESP32 Sensorik
// Sendet Temperatur und Sitzabstand als JSON per Serial (Werkbank) und per
// WLAN/MQTT (Messebetrieb) an den Fahrzeug-Pi.
// Sensorannahme:
// - Abstand: HC-SR04 kompatibel oder aehnlicher Ultraschallsensor
// - Temperatur: analoger LM35/TMP36-aehnlicher Sensor an ADC

#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>

#include "wifi_credentials.h"

static const uint32_t BAUDRATE = 115200;

static const int PIN_DISTANCE_TRIG = 18;
static const int PIN_DISTANCE_ECHO = 19;
static const int PIN_TEMPERATURE_ADC = 34;

// Anpassen, wenn ein anderer analoger Temperatursensor verwendet wird.
static const bool TEMPERATURE_SENSOR_TMP36 = false;
static const float ADC_REFERENCE_VOLTAGE = 3.3f;
static const int ADC_MAX_VALUE = 4095;

// Telemetrierate MA-05-002: Standard ca. 1 Hz, hier konfigurierbar.
static const uint32_t TELEMETRY_INTERVAL_MS = 1000;

uint32_t lastStatusMs = 0;
uint32_t lastHelloMs = 0;

// --- MesseCar WLAN/MQTT (MA-05-001/002/003) ---
//
// Kein Internet auf dem lokalen AP, daher keine NTP-Zeit verfuegbar.
// `timestamp_ms` in MQTT-Nachrichten ist deshalb `millis()` (Geraete-Uptime),
// analog zum ESP Actor - siehe MQTT.md.
static const uint32_t WIFI_RETRY_INTERVAL_MS = 5000;
static const uint32_t MQTT_RETRY_INTERVAL_MS = 3000;
static const char *MQTT_CLIENT_ID = "esp_sensor_aux";
static const char *TOPIC_STATUS = "messecar/sensor/status";
static const char *TOPIC_TELEMETRY = "messecar/sensor/telemetry";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
uint32_t lastWifiAttemptAt = 0;
uint32_t lastMqttAttemptAt = 0;

// Medianfilter (3 Werte) fuer den Abstand, reduziert Ausreisser der
// Ultraschallmessung (MA-05-002 "Medianfilter der Distanz beibehalten").
float distanceHistoryMm[3] = {NAN, NAN, NAN};
uint8_t distanceHistoryIndex = 0;

void setup() {
  Serial.begin(BAUDRATE);
  pinMode(PIN_DISTANCE_TRIG, OUTPUT);
  pinMode(PIN_DISTANCE_ECHO, INPUT);
  analogReadResolution(12);
  sendHello();

  WiFi.mode(WIFI_STA);
  mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.setBufferSize(512);
}

void loop() {
  uint32_t now = millis();
  if (now - lastHelloMs > 5000) {
    sendHello();
  }
  if (now - lastStatusMs > TELEMETRY_INTERVAL_MS) {
    sendSensorStatus();
  }
  ensureWifiConnected();
  ensureMqttConnected();
}

void sendHello() {
  lastHelloMs = millis();
  Serial.printf("{\"device\":\"esp32_sensor\",\"type\":\"hello\",\"baudrate\":%lu}\n", BAUDRATE);
}

void sendSensorStatus() {
  lastStatusMs = millis();

  float distanceMm = medianFilteredDistanceMm();
  float temperatureC = readTemperatureC();
  bool distanceValid = isfinite(distanceMm) && distanceMm > 0;
  bool temperatureValid = isfinite(temperatureC);

  if (!distanceValid) {
    Serial.printf(
      "{\"device\":\"esp32_sensor\",\"type\":\"sensor_error\",\"timestamp_ms\":%lu,"
      "\"sensor\":\"seat_distance\",\"message\":\"Kein gueltiger Abstandswert erkannt\"}\n",
      millis()
    );
  } else {
    const char *position = seatPosition(distanceMm);
    Serial.printf(
      "{\"device\":\"esp32_sensor\",\"type\":\"sensor_status\",\"timestamp_ms\":%lu,"
      "\"temperature_c\":%.1f,\"seat_distance_mm\":%.1f,\"seat_position\":\"%s\",\"errors\":[]}\n",
      millis(),
      temperatureC,
      distanceMm,
      position
    );
  }

  publishTelemetry(temperatureValid ? temperatureC : NAN, distanceValid ? distanceMm : NAN);
}

// MA-05-003: nur tatsaechlich gueltige Messwerte senden. Ungueltige Felder
// werden im JSON weggelassen statt einen erfundenen Wert zu senden; Pi 1
// behandelt ein fehlendes Feld bereits als "missing"-Fehlerzustand.
void publishTelemetry(float temperatureC, float distanceMm) {
  if (!mqttClient.connected()) {
    return;
  }
  JsonDocument doc;
  doc["device"] = "esp_sensor_aux";
  doc["timestamp_ms"] = millis();
  if (isfinite(temperatureC)) {
    doc["temperature_c"] = temperatureC;
  }
  if (isfinite(distanceMm) && distanceMm > 0) {
    doc["seat_distance_cm"] = distanceMm / 10.0f;
  }
  char buffer[192];
  serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(TOPIC_TELEMETRY, buffer, false);
}

void publishStatus(const char *status, bool retain) {
  if (!mqttClient.connected()) {
    return;
  }
  JsonDocument doc;
  doc["device"] = "esp_sensor_aux";
  doc["timestamp_ms"] = millis();
  doc["status"] = status;
  char buffer[128];
  serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(TOPIC_STATUS, buffer, retain);
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
  willDoc["device"] = "esp_sensor_aux";
  willDoc["status"] = "offline";
  char willBuffer[128];
  serializeJson(willDoc, willBuffer, sizeof(willBuffer));

  const bool connected = mqttClient.connect(MQTT_CLIENT_ID, TOPIC_STATUS, 1, true, willBuffer);
  if (connected) {
    publishStatus("online", true);
  }
}

float medianFilteredDistanceMm() {
  distanceHistoryMm[distanceHistoryIndex] = readDistanceMm();
  distanceHistoryIndex = (distanceHistoryIndex + 1) % 3;

  float sorted[3] = {distanceHistoryMm[0], distanceHistoryMm[1], distanceHistoryMm[2]};
  for (uint8_t i = 0; i < 3; i++) {
    if (!isfinite(sorted[i])) {
      return NAN; // ein ungueltiger Wert im Fenster -> kein stabiler Median
    }
  }
  // Fuer drei Werte reicht ein einfacher Sortierschritt; der Median reduziert Ausreisser.
  if (sorted[0] > sorted[1]) { float t = sorted[0]; sorted[0] = sorted[1]; sorted[1] = t; }
  if (sorted[1] > sorted[2]) { float t = sorted[1]; sorted[1] = sorted[2]; sorted[2] = t; }
  if (sorted[0] > sorted[1]) { float t = sorted[0]; sorted[0] = sorted[1]; sorted[1] = t; }
  return sorted[1];
}

float readDistanceMm() {
  digitalWrite(PIN_DISTANCE_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_DISTANCE_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_DISTANCE_TRIG, LOW);

  unsigned long duration = pulseIn(PIN_DISTANCE_ECHO, HIGH, 30000);
  if (duration == 0) {
    return NAN;
  }

  // Schallgeschwindigkeit: ca. 0,343 mm/us, Hin- und Rueckweg.
  return (duration * 0.343f) / 2.0f;
}

float readTemperatureC() {
  int raw = analogRead(PIN_TEMPERATURE_ADC);
  float voltage = (raw * ADC_REFERENCE_VOLTAGE) / ADC_MAX_VALUE;

  if (TEMPERATURE_SENSOR_TMP36) {
    return (voltage - 0.5f) * 100.0f;
  }

  // LM35: 10 mV pro Grad Celsius.
  return voltage * 100.0f;
}

const char *seatPosition(float distanceMm) {
  if (distanceMm >= 45 && distanceMm <= 55) {
    return "front";
  }
  if (distanceMm >= 90 && distanceMm <= 110) {
    return "middle";
  }
  if (distanceMm >= 145 && distanceMm <= 165) {
    return "rear";
  }
  return "unknown";
}
