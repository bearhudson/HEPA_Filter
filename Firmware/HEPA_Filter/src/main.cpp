#include <Arduino.h>

// Pin Definitions
const int POT_PIN = A0;      // ESP8266 only has one ADC pin
const int FAN1_PIN = 5;      // D1 on NodeMCU/Wemos
const int FAN2_PIN = 4;      // D2 on NodeMCU/Wemos

// Tuning
const float FAN2_OFFSET = 1.10; // Fan 2 runs 10% faster than Fan 1

void setup() {
  // Set global PWM frequency to 25kHz for standard PC fans
  analogWriteFreq(25000);
  
  // ESP8266 analogWrite range is 0-1023 by default. 
  // We will use this full 10-bit range for smoother RPM steps.
  pinMode(FAN1_PIN, OUTPUT);
  pinMode(FAN2_PIN, OUTPUT);
}

void loop() {
  // Read the potentiometer (0 to 1023)
  int potValue = analogRead(POT_PIN);
  
  // Since ADC is 10-bit (0-1023) and PWM is 10-bit (0-1023), 
  // we don't need the map() function like we did on the ESP32.
  int fan1Speed = potValue;
  
  // Apply offset to Fan 2
  int fan2Speed = (int)(fan1Speed * FAN2_OFFSET);
  
  // Constrain Fan 2 so it doesn't overflow the 10-bit max
  if (fan2Speed > 1023) {
    fan2Speed = 1023;
  }
  
  // Write the speeds to the fans
  analogWrite(FAN1_PIN, fan1Speed);
  analogWrite(FAN2_PIN, fan2Speed);
  
  // Small delay for ADC stability
  delay(50);
}