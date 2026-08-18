#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>

constexpr uint32_t SERIAL_BAUDRATE = 115200;
constexpr uint16_t SEND_INTERVAL_MS = 500;
constexpr uint8_t ONE_WIRE_PIN = 4;
constexpr uint8_t TRIGGER_PIN = 18;
constexpr uint8_t ECHO_PIN = 19;
constexpr uint32_t ECHO_TIMEOUT_US = 30000;
constexpr float MIN_DISTANCE_CM = 2.0f;
constexpr float MAX_DISTANCE_CM = 400.0f;
constexpr uint8_t DISTANCE_SAMPLES = 3;

OneWire oneWire(ONE_WIRE_PIN);
DallasTemperature temperatureSensors(&oneWire);
uint32_t lastSendAt = 0;

float readTemperatureC() {
  temperatureSensors.requestTemperatures();
  const float value = temperatureSensors.getTempCByIndex(0);
  if (value == DEVICE_DISCONNECTED_C || value < -55.0f || value > 125.0f) return NAN;
  return value;
}

float readDistanceOnceCm() {
  digitalWrite(TRIGGER_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIGGER_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIGGER_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return NAN;

  const float distance = duration * 0.0343f / 2.0f;
  if (distance < MIN_DISTANCE_CM || distance > MAX_DISTANCE_CM) return NAN;
  return distance;
}

float readDistanceCm() {
  float values[DISTANCE_SAMPLES];
  uint8_t valid = 0;

  for (uint8_t i = 0; i < DISTANCE_SAMPLES; i++) {
    const float value = readDistanceOnceCm();
    if (!isnan(value)) values[valid++] = value;
    delay(25);
  }

  if (valid == 0) return NAN;

  // Für drei Werte reicht ein einfacher Sortierschritt; der Median reduziert Ausreißer.
  for (uint8_t i = 0; i < valid; i++) {
    for (uint8_t j = i + 1; j < valid; j++) {
      if (values[j] < values[i]) {
        const float tmp = values[i];
        values[i] = values[j];
        values[j] = tmp;
      }
    }
  }
  return values[valid / 2];
}

void printJsonNumber(float value, uint8_t decimals) {
  if (isnan(value)) Serial.print("null");
  else Serial.print(value, decimals);
}

void sendSensorData() {
  const float temperatureC = readTemperatureC();
  const float seatDistanceCm = readDistanceCm();

  Serial.print("{\"device\":\"esp32_sensor\",\"temperature_c\":");
  printJsonNumber(temperatureC, 2);
  Serial.print(",\"seat_distance_cm\":");
  printJsonNumber(seatDistanceCm, 1);
  Serial.print(",\"uptime_ms\":");
  Serial.print(millis());
  Serial.println("}");
}

void setup() {
  Serial.begin(SERIAL_BAUDRATE);
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIGGER_PIN, LOW);
  temperatureSensors.begin();
  temperatureSensors.setWaitForConversion(true);
  delay(300);
  sendSensorData();
}

void loop() {
  const uint32_t now = millis();
  if (now - lastSendAt >= SEND_INTERVAL_MS) {
    lastSendAt = now;
    sendSensorData();
  }
  delay(5);
}
