// MesseAuto ESP32 Sensorik + Hupe (Aux)
// Sendet Temperatur und Sitzabstand als JSON per Serial (Werkbank) und per
// WLAN/MQTT (Messebetrieb) an den Fahrzeug-Pi. Erzeugt zusaetzlich lokal die
// Fahrzeughupe ueber einen MAX98357A I2S-Verstaerker (M11).
// Sensorannahme:
// - Abstand: HC-SR04 kompatibel oder aehnlicher Ultraschallsensor
// - Temperatur: analoger LM35/TMP36-aehnlicher Sensor an ADC

#include <ArduinoJson.h>
#include <PubSubClient.h>
#include <WiFi.h>
#include <driver/adc.h>
#include <driver/i2s.h>
#include <math.h>

#include "wifi_credentials.h"

static const uint32_t BAUDRATE = 115200;

static const int PIN_DISTANCE_TRIG = 18;
static const int PIN_DISTANCE_ECHO = 19;
// GPIO35 = ADC1_CHANNEL_7. Legacy-ADC-API statt analogRead(), da analogRead()
// in diesem Core-Stand den neuen "driver_ng" nutzt, der mit dem legacy I2S-Treiber
// (driver/i2s.h, fuer die Hupe) kollidiert (abort(): "ADC: CONFLICT!").
static const adc1_channel_t TEMPERATURE_ADC_CHANNEL = ADC1_CHANNEL_7;

// Anpassen, wenn ein anderer analoger Temperatursensor verwendet wird.
static const bool TEMPERATURE_SENSOR_TMP36 = false;
static const float ADC_REFERENCE_VOLTAGE = 3.3f;
static const int ADC_MAX_VALUE = 4095;

// Telemetrierate MA-05-002: Standard ca. 1 Hz, hier konfigurierbar.
static const uint32_t TELEMETRY_INTERVAL_MS = 1000;

uint32_t lastStatusMs = 0;
uint32_t lastHelloMs = 0;

// --- MesseCar WLAN/MQTT (MA-05-001/002/003, M11 Hupe) ---
//
// Kein Internet auf dem lokalen AP, daher keine NTP-Zeit verfuegbar.
// `timestamp_ms` in MQTT-Nachrichten ist deshalb `millis()` (Geraete-Uptime),
// analog zum ESP Actor - siehe MQTT.md.
static const uint32_t WIFI_RETRY_INTERVAL_MS = 5000;
static const uint32_t MQTT_RETRY_INTERVAL_MS = 3000;
static const char *MQTT_CLIENT_ID = "esp_sensor_aux";
static const char *TOPIC_STATUS = "messecar/sensor/status";
static const char *TOPIC_TELEMETRY = "messecar/sensor/telemetry";
static const char *TOPIC_HORN_COMMAND = "messecar/horn/command";
static const char *TOPIC_HORN_STATE = "messecar/horn/state";

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
uint32_t lastWifiAttemptAt = 0;
uint32_t lastMqttAttemptAt = 0;

// Medianfilter (3 Werte) fuer den Abstand, reduziert Ausreisser der
// Ultraschallmessung (MA-05-002 "Medianfilter der Distanz beibehalten").
float distanceHistoryMm[3] = {NAN, NAN, NAN};
uint8_t distanceHistoryIndex = 0;

// --- Hupe (M11) ---
//
// Zwei unabhaengige Ausloesewege:
// 1) MQTT messecar/horn/command von Pi 1 (Keepalive-Lease, MA-11-010/011).
// 2) Direkte Hardwareleitung vom ESP Actor (Actor-GPIO21 -> hier GPIO13),
//    siehe HARDWARE.md "Direkte Hupenleitung Actor -> Sensor/Aux" - wirkt
//    als lokaler Failsafe-Pfad unabhaengig von WLAN/MQTT-Latenz.
static const int PIN_HORN_DIRECT_TRIGGER = 13;
static const uint32_t HORN_KEEPALIVE_TIMEOUT_MS = 300;
static const float HORN_TONE_HZ = 420.0f;
static const int HORN_SAMPLE_RATE = 16000;

static const i2s_port_t HORN_I2S_PORT = I2S_NUM_0;
static const int PIN_I2S_LRC = 27;
static const int PIN_I2S_BCLK = 25;
static const int PIN_I2S_DIN = 26;

bool hornMqttActive = false;
int32_t hornLastSeq = -1;
uint32_t hornLastKeepaliveAt = 0;
bool hornAudioOn = false;
float hornPhase = 0.0f;

void setup() {
  Serial.begin(BAUDRATE);
  pinMode(PIN_DISTANCE_TRIG, OUTPUT);
  pinMode(PIN_DISTANCE_ECHO, INPUT);
  pinMode(PIN_HORN_DIRECT_TRIGGER, INPUT_PULLDOWN);
  adc1_config_width(ADC_WIDTH_BIT_12);
  adc1_config_channel_atten(TEMPERATURE_ADC_CHANNEL, ADC_ATTEN_DB_11);
  sendHello();

  WiFi.mode(WIFI_STA);
  mqttClient.setServer(MQTT_BROKER_HOST, MQTT_BROKER_PORT);
  mqttClient.setBufferSize(512);
  mqttClient.setCallback(handleMqttMessage);

  setupHornAudio();
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
  updateHorn();
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

void publishHornState() {
  if (!mqttClient.connected()) {
    return;
  }
  JsonDocument doc;
  doc["device"] = "esp_sensor_aux";
  doc["timestamp_ms"] = millis();
  doc["active"] = hornAudioOn;
  doc["audio_ok"] = true;
  char buffer[128];
  serializeJson(doc, buffer, sizeof(buffer));
  mqttClient.publish(TOPIC_HORN_STATE, buffer, false);
}

// MA-11-011: seq muss streng steigen, aeltere/doppelte active:true werden
// ignoriert. MA-11-010: Keepalive-Zeitstempel wird bei jedem gueltigen
// Command aktualisiert, updateHorn() erzwingt bei Timeout lokal AUS.
void handleMqttMessage(char *topic, byte *payload, unsigned int length) {
  if (strcmp(topic, TOPIC_HORN_COMMAND) != 0) {
    return;
  }
  JsonDocument doc;
  DeserializationError parseError = deserializeJson(doc, payload, length);
  if (parseError) {
    return;
  }
  if (!doc["device"].is<const char *>() || !doc["seq"].is<long>()) {
    return;
  }
  const int32_t seq = doc["seq"].as<int32_t>();
  if (seq <= hornLastSeq) {
    return; // veraltet/dupliziert
  }
  hornLastSeq = seq;

  const bool active = doc["active"] | false;
  if (active) {
    hornMqttActive = true;
    hornLastKeepaliveAt = millis();
  } else {
    hornMqttActive = false;
  }
}

// MA-11-010: kein gueltiges Keepalive fuer 300ms -> lokal AUS, unabhaengig
// vom zuletzt bekannten Sollzustand (WLAN-/Brokerverlust-Failsafe).
void updateHorn() {
  if (hornMqttActive && (millis() - hornLastKeepaliveAt) > HORN_KEEPALIVE_TIMEOUT_MS) {
    hornMqttActive = false;
  }

  const bool directTrigger = digitalRead(PIN_HORN_DIRECT_TRIGGER) == HIGH;
  const bool shouldSound = hornMqttActive || directTrigger;

  if (shouldSound != hornAudioOn) {
    hornAudioOn = shouldSound;
    publishHornState();
    if (!hornAudioOn) {
      // Ohne das wuerde die DMA die letzten Samples endlos weiter loopen
      // (Dauer-Brummen statt Stille), da i2s_write() sonst nicht mehr aufgerufen wird.
      i2s_zero_dma_buffer(HORN_I2S_PORT);
    }
  }

  if (hornAudioOn) {
    writeHornSamples();
  }
}

void setupHornAudio() {
  const i2s_config_t config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = HORN_SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_RIGHT_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = 0,
    .dma_buf_count = 4,
    .dma_buf_len = 256,
    .use_apll = false,
  };
  i2s_driver_install(HORN_I2S_PORT, &config, 0, nullptr);

  const i2s_pin_config_t pins = {
    .bck_io_num = PIN_I2S_BCLK,
    .ws_io_num = PIN_I2S_LRC,
    .data_out_num = PIN_I2S_DIN,
    .data_in_num = I2S_PIN_NO_CHANGE,
  };
  i2s_set_pin(HORN_I2S_PORT, &pins);
  i2s_zero_dma_buffer(HORN_I2S_PORT);
}

// Einfache Sinuston-Synthese (MA-11-005 "geeignete Synthese"). Schreibt
// jeweils einen kleinen Chunk pro loop()-Durchlauf, damit WLAN/MQTT/Sensorik
// nicht blockiert werden (DMA-Puffer traegt den Rest).
void writeHornSamples() {
  static int16_t buffer[128];
  const float phaseStep = 2.0f * PI * HORN_TONE_HZ / HORN_SAMPLE_RATE;

  for (int i = 0; i < 128; i += 2) {
    const int16_t sample = (int16_t)(sinf(hornPhase) * 12000.0f);
    buffer[i] = sample;      // links
    buffer[i + 1] = sample;  // rechts (SD offen -> ohnehin Mono-Mix)
    hornPhase += phaseStep;
    if (hornPhase > 2.0f * PI) {
      hornPhase -= 2.0f * PI;
    }
  }

  size_t bytesWritten = 0;
  i2s_write(HORN_I2S_PORT, buffer, sizeof(buffer), &bytesWritten, 0);
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

  // MA-11-012: Boot/Reconnect immer Hupe AUS, bis eine neue aktuelle
  // MQTT-Eingabe kommt (hornMqttActive/hornLastSeq bleiben unberuehrt,
  // starten bereits false/-1; retained Horn-Command ist ohnehin verboten).
  const bool connected = mqttClient.connect(MQTT_CLIENT_ID, TOPIC_STATUS, 1, true, willBuffer);
  if (connected) {
    mqttClient.subscribe(TOPIC_HORN_COMMAND, 1);
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
  int raw = adc1_get_raw(TEMPERATURE_ADC_CHANNEL);
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
