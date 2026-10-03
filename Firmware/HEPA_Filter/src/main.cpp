#include <Arduino.h>
#include <DHT.h>
#include <Adafruit_NeoPixel.h>

// --- Pin Definitions ---
const int MQ135_PIN = A0;   // MQ-135 Analog out
const int FAN1_PIN  = 5;    // D1 on NodeMCU/Wemos (Intake Fan)
const int FAN2_PIN  = 4;    // D2 on NodeMCU/Wemos (Exhaust Fan)
const int LED_PIN   = 14;   // D5 on NodeMCU/Wemos (WS2812B Data)
const int DHT_PIN   = 12;   // D6 on NodeMCU/Wemos (DHT11 Data)

// --- Constants & Tuning ---
const int NUM_LEDS = 10;           // Total LEDs on your strip
const int LED_INTENSITY = 51;      // 20% brightness (out of 255)

const float FAN2_OFFSET = 1.10;    // Fan 2 runs 10% faster to prevent acoustic beating
const int MIN_FAN_SPEED = 255;     // ~25% duty cycle baseline (keeps air moving)
const int MAX_FAN_SPEED = 1023;    // 100% duty cycle limit for ESP8266

// MQ-135 thresholds (You may need to tweak these based on your room's baseline)
const float CLEAN_AIR_ADC = 150.0; // Typical ADC reading in clean air
const float POOR_AIR_ADC = 600.0;  // Typical ADC reading when polluted

// --- Object Initialization ---
DHT dht(DHT_PIN, DHT11);
Adafruit_NeoPixel strip(NUM_LEDS, LED_PIN, NEO_GRB + NEO_KHZ800);

// Timing state
unsigned long lastSensorRead = 0;
const unsigned long SENSOR_INTERVAL = 2000; // Read sensors every 2 seconds

// System state
int currentFanSpeed = MIN_FAN_SPEED;
int currentAQI = 0; // 0 (Good) to 100 (Bad)


// Calculates the MQ135 temperature & humidity correction factor
// Based on the standard datasheet polynomial fit normalized to 20C and 33% RH
float getMQ135CorrectionFactor(float temp, float hum) {
  return (0.00035 * temp * temp) - (0.02718 * temp) + 1.3753 - (hum - 33.0) * 0.0018;
}


void setup() {
  Serial.begin(115200);
  
  // Setup Fans (25kHz PWM frequency for PC fans)
  analogWriteFreq(25000);
  pinMode(FAN1_PIN, OUTPUT);
  pinMode(FAN2_PIN, OUTPUT);
  
  // Setup Sensors and LEDs
  dht.begin();
  strip.begin();
  strip.setBrightness(LED_INTENSITY);
  strip.show(); // Initialize all pixels to 'off'
}


void loop() {
  unsigned long currentMillis = millis();

  // 1. Read Sensors (Non-blocking loop)
  if (currentMillis - lastSensorRead >= SENSOR_INTERVAL) {
    lastSensorRead = currentMillis;

    float humidity = dht.readHumidity();
    float tempC = dht.readTemperature();
    int rawADC = analogRead(MQ135_PIN);

    // Apply correction factor if DHT11 readings are valid
    float correctedADC = rawADC;
    if (!isnan(humidity) && !isnan(tempC)) {
      float cf = getMQ135CorrectionFactor(tempC, humidity);
      correctedADC = rawADC * cf; 
    }

    // 2. Calculate Air Quality Index (0-100)
    currentAQI = map(correctedADC, CLEAN_AIR_ADC, POOR_AIR_ADC, 0, 100);
    currentAQI = constrain(currentAQI, 0, 100);

    // 3. Determine Target Fan Speed
    currentFanSpeed = map(currentAQI, 0, 100, MIN_FAN_SPEED, MAX_FAN_SPEED);
    
    // Serial monitor debugging
    Serial.printf("T: %.1fC | H: %.1f%% | Raw ADC: %d | Corr ADC: %.1f | AQI: %d | Fan1: %d\n", 
                  tempC, humidity, rawADC, correctedADC, currentAQI, currentFanSpeed);
  }

  // 4. Update Hardware PWM
  int fan2Speed = (int)(currentFanSpeed * FAN2_OFFSET);
  if (fan2Speed > 1023) {
      fan2Speed = 1023; // Prevent 10-bit overflow
  }
  analogWrite(FAN1_PIN, currentFanSpeed);
  analogWrite(FAN2_PIN, fan2Speed);

  // 5. Update LED Strip
  // Map AQI to a Green -> Yellow -> Red gradient
  int r = 0, g = 0, b = 0;
  if (currentAQI <= 50) {
    g = 255;
    r = map(currentAQI, 0, 50, 0, 255); // Ramps up Red to make Yellow
  } else {
    r = 255;
    g = map(currentAQI, 50, 100, 255, 0); // Ramps down Green to make pure Red
  }

  // Map the current fan speed to the number of lit LEDs
  int ledsToLight = map(currentFanSpeed, MIN_FAN_SPEED, MAX_FAN_SPEED, 1, NUM_LEDS);

  strip.clear();
  for (int i = 0; i < ledsToLight; i++) {
    strip.setPixelColor(i, strip.Color(r, g, b));
  }
  strip.show();

  // 10ms delay to keep the main loop stable
  delay(10);
}