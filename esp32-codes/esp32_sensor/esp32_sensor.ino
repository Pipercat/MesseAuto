// MesseAuto ESP32 Sensorik
// Sendet Temperatur und Sitzabstand als JSON an den Fahrzeug-Pi.
// Sensorannahme:
// - Abstand: HC-SR04 kompatibel oder aehnlicher Ultraschallsensor
// - Temperatur: analoger LM35/TMP36-aehnlicher Sensor an ADC

static const uint32_t BAUDRATE = 115200;

static const int PIN_DISTANCE_TRIG = 18;
static const int PIN_DISTANCE_ECHO = 19;
static const int PIN_TEMPERATURE_ADC = 34;

// Anpassen, wenn ein anderer analoger Temperatursensor verwendet wird.
static const bool TEMPERATURE_SENSOR_TMP36 = false;
static const float ADC_REFERENCE_VOLTAGE = 3.3f;
static const int ADC_MAX_VALUE = 4095;

uint32_t lastStatusMs = 0;
uint32_t lastHelloMs = 0;

void setup() {
  Serial.begin(BAUDRATE);
  pinMode(PIN_DISTANCE_TRIG, OUTPUT);
  pinMode(PIN_DISTANCE_ECHO, INPUT);
  analogReadResolution(12);
  sendHello();
}

void loop() {
  uint32_t now = millis();
  if (now - lastHelloMs > 5000) {
    sendHello();
  }
  if (now - lastStatusMs > 500) {
    sendSensorStatus();
  }
}

void sendHello() {
  lastHelloMs = millis();
  Serial.printf("{\"device\":\"esp32_sensor\",\"type\":\"hello\",\"baudrate\":%lu}\n", BAUDRATE);
}

void sendSensorStatus() {
  lastStatusMs = millis();

  float distanceMm = readDistanceMm();
  float temperatureC = readTemperatureC();

  if (!isfinite(distanceMm) || distanceMm <= 0) {
    Serial.printf(
      "{\"device\":\"esp32_sensor\",\"type\":\"sensor_error\",\"timestamp_ms\":%lu,"
      "\"sensor\":\"seat_distance\",\"message\":\"Kein gueltiger Abstandswert erkannt\"}\n",
      millis()
    );
    return;
  }

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
