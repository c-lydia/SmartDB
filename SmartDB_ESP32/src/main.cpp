#include <Arduino.h>
#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include <addons/TokenHelper.h>
#include "config.h"  

void setup(){
WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
config.api_key = API_KEY;
config.database_url = DATABASE_URL;

}


FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

bool signupOK = false;
bool relayState = true;
bool jetsonAvailable = false;

float fakeTemperature = 25.0;
float fakeCurrent = 2.5;
float fakeVoltage = 220.0;
int dataCounter = 0;

unsigned long alertCooldown = 0;
const unsigned long ALERT_COOLDOWN_MS = 30000;

HardwareSerial JetsonSerial(2);


void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println();
  Serial.println("SmartDB System Starting");
  Serial.println("================================");
  
  setupWiFi();
  setupFirebase();
  setupJetsonCommunication();
  setupRelay();
}

void setupWiFi() {
  Serial.print("Connecting to WiFi: ");
  Serial.println(WIFI_SSID);  
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);  
  
  int count = 0;
  while (WiFi.status() != WL_CONNECTED && count < 30) {
    delay(500);
    Serial.print(".");
    count++;
  }
  
  Serial.println();
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("WiFi Connected");
    Serial.print("IP Address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi Connection Failed");
  }
}

void setupFirebase() {
  Serial.println("Initializing Firebase...");
  
  config.api_key = API_KEY; 
  config.database_url = DATABASE_URL;  
  
  if (Firebase.signUp(&config, &auth, "", "")) {
    Serial.println("Firebase signup successful");
    signupOK = true;
  } else {
    Serial.print("Firebase signup failed: ");
    Serial.println(config.signer.signupError.message.c_str());
    signupOK = false;
  }
  
  config.token_status_callback = tokenStatusCallback;
  
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
}


void setupJetsonCommunication() {
  JetsonSerial.begin(115200, SERIAL_8N1, 16, 17);
  Serial.println("Jetson Nano UART initialized on pins 16 and 17");
}

void setupRelay() {
  pinMode(18, OUTPUT);
  digitalWrite(18, HIGH);
  relayState = true;
  Serial.println("Relay initialized. Power ON");
}

void sendDataToFirebase(float temperature, float current, float voltage) {
  if (!signupOK) {
    Serial.println("Firebase not ready, skipping upload");
    return;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skipping upload");
    return;
  }
  
  dataCounter++;
  
  String path = "/readings/data_" + String(dataCounter);
  
  FirebaseJson json;
  json.set("temperature", temperature);
  json.set("current", current);
  json.set("voltage", voltage);
  json.set("timestamp", Firebase.getTimestamp());
  json.set("device", "SmartDB_ESP32");
  json.set("readings_count", dataCounter);
  json.set("relay_state", relayState);
  
  Serial.println("Sending data to Firebase...");
  Serial.print("Path: ");
  Serial.println(path);
  
  if (Firebase.RTDB.setJSON(&fbdo, path, &json)) {
    Serial.println("Data sent successfully!");
    Serial.print("Data stored at: ");
    Serial.println(fbdo.dataPath());
  } else {
    Serial.print("Failed to send data: ");
    Serial.println(fbdo.errorReason());
  }
}

void sendAlertToFirebase(Alert alert) {
  if (!signupOK) {
    return;
  }
  
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, alert stored locally");
    return;
  }
  
  String path = "/alerts/alert_" + String(millis());
  
  FirebaseJson json;
  json.set("type", getAlertTypeString(alert.type));
  json.set("level", getAlertLevelString(alert.level));
  json.set("value", alert.value);
  json.set("threshold", alert.threshold);
  json.set("message", alert.message);
  json.set("relay_cut", alert.relayCut);
  json.set("timestamp", Firebase.getTimestamp());
  json.set("acknowledged", false);
  json.set("device", "SmartDB_ESP32");
  
  Serial.println("Sending alert to Firebase...");
  
  if (Firebase.RTDB.setJSON(&fbdo, path, &json)) {
    Serial.println("Alert sent successfully!");
  } else {
    Serial.print("Failed to send alert: ");
    Serial.println(fbdo.errorReason());
  }
}

String getAlertTypeString(AlertType type) {
  switch(type) {
    case ALERT_OVERHEAT: return "OVERHEAT";
    case ALERT_OVERLOAD: return "OVERLOAD";
    case ALERT_VOLTAGE_FLUCTUATION: return "VOLTAGE_FLUCTUATION";
    case ALERT_THERMAL_HOTSPOT: return "THERMAL_HOTSPOT";
    case ALERT_ANOMALY_DETECTED: return "ANOMALY_DETECTED";
    default: return "UNKNOWN";
  }
}

String getAlertLevelString(AlertLevel level) {
  switch(level) {
    case ALERT_WARNING: return "WARNING";
    case ALERT_CRITICAL: return "CRITICAL";
    case ALERT_EMERGENCY: return "EMERGENCY";
    default: return "NONE";
  }
}

void checkAlerts(float temperature, float current, float voltage) {
  unsigned long now = millis();
  
  if (now - alertCooldown < ALERT_COOLDOWN_MS) {
    return;
  }
  
  Alert newAlert;
  newAlert.timestamp = now;
  newAlert.acknowledged = false;
  newAlert.relayCut = false;
  newAlert.level = ALERT_NONE;
  
  if (temperature > TEMP_EMERGENCY) {
    newAlert.type = ALERT_OVERHEAT;
    newAlert.level = ALERT_EMERGENCY;
    newAlert.value = temperature;
    newAlert.threshold = TEMP_EMERGENCY;
    newAlert.message = "Emergency: Extreme temperature detected";
    newAlert.relayCut = true;
    
  } else if (temperature > TEMP_CRITICAL) {
    newAlert.type = ALERT_OVERHEAT;
    newAlert.level = ALERT_CRITICAL;
    newAlert.value = temperature;
    newAlert.threshold = TEMP_CRITICAL;
    newAlert.message = "Critical: High temperature detected";
    newAlert.relayCut = false;
    
  } else if (temperature > TEMP_WARNING) {
    newAlert.type = ALERT_OVERHEAT;
    newAlert.level = ALERT_WARNING;
    newAlert.value = temperature;
    newAlert.threshold = TEMP_WARNING;
    newAlert.message = "Warning: Elevated temperature detected";
    newAlert.relayCut = false;
  }
  
  if (current > CURRENT_EMERGENCY && newAlert.level < ALERT_EMERGENCY) {
    newAlert.type = ALERT_OVERLOAD;
    newAlert.level = ALERT_EMERGENCY;
    newAlert.value = current;
    newAlert.threshold = CURRENT_EMERGENCY;
    newAlert.message = "Emergency: Extreme current overload";
    newAlert.relayCut = true;
    
  } else if (current > CURRENT_CRITICAL && newAlert.level < ALERT_CRITICAL) {
    newAlert.type = ALERT_OVERLOAD;
    newAlert.level = ALERT_CRITICAL;
    newAlert.value = current;
    newAlert.threshold = CURRENT_CRITICAL;
    newAlert.message = "Critical: High current overload";
    newAlert.relayCut = false;
    
  } else if (current > CURRENT_WARNING && newAlert.level < ALERT_WARNING) {
    newAlert.type = ALERT_OVERLOAD;
    newAlert.level = ALERT_WARNING;
    newAlert.value = current;
    newAlert.threshold = CURRENT_WARNING;
    newAlert.message = "Warning: High current detected";
    newAlert.relayCut = false;
  }
  
  if ((voltage < VOLTAGE_MIN || voltage > VOLTAGE_MAX) && newAlert.level < ALERT_WARNING) {
    newAlert.type = ALERT_VOLTAGE_FLUCTUATION;
    newAlert.level = ALERT_WARNING;
    newAlert.value = voltage;
    newAlert.threshold = (voltage < VOLTAGE_MIN) ? VOLTAGE_MIN : VOLTAGE_MAX;
    newAlert.message = "Warning: Voltage fluctuation detected";
    newAlert.relayCut = false;
  }
  
  if (newAlert.level != ALERT_NONE) {
    currentAlert = newAlert;
    alertCooldown = now;
    
    printAlert(newAlert);
    sendAlertToFirebase(newAlert);
    
    if (newAlert.relayCut) {
      cutRelay();
    }
  }
}

void printAlert(Alert alert) {
  Serial.println("========================================");
  Serial.println("ALERT TRIGGERED");
  Serial.println("========================================");
  
  Serial.print("Level: ");
  Serial.println(getAlertLevelString(alert.level));
  
  Serial.print("Type: ");
  Serial.println(getAlertTypeString(alert.type));
  
  Serial.print("Value: ");
  Serial.println(alert.value);
  
  Serial.print("Threshold: ");
  Serial.println(alert.threshold);
  
  Serial.print("Message: ");
  Serial.println(alert.message);
  
  Serial.print("Relay Cut: ");
  Serial.println(alert.relayCut ? "Yes" : "No");
  
  Serial.println("========================================");
}

void cutRelay() {
  Serial.println("Relay Cut. Power disconnected");
  relayState = false;
  digitalWrite(18, LOW);
}

void restoreRelay() {
  Serial.println("Relay Restored. Power reconnected");
  relayState = true;
  digitalWrite(18, HIGH);
}

void sendDataToJetson(float temp, float current, float voltage) {
  String data = String(temp) + "," + 
                String(current) + "," + 
                String(voltage) + "," + 
                String(millis()) + "\n";
  
  JetsonSerial.print(data);
}

void receiveFromJetson() {
  if (JetsonSerial.available()) {
    String response = JetsonSerial.readStringUntil('\n');
    
    if (response.startsWith("ANOMALY_SCORE:")) {
      int colonIndex = response.indexOf(':');
      int pipeIndex = response.indexOf('|');
      
      if (pipeIndex > 0) {
        float score = response.substring(colonIndex + 1, pipeIndex).toFloat();
        String action = response.substring(pipeIndex + 1);
        
        Serial.print("Jetson AI Score: ");
        Serial.println(score);
        jetsonAvailable = true;
        
        if (score > 0.8) {
          Serial.println("Jetson detected high anomaly");
          cutRelay();
          
          Alert alert;
          alert.type = ALERT_ANOMALY_DETECTED;
          alert.level = ALERT_EMERGENCY;
          alert.value = score;
          alert.threshold = 0.8;
          alert.message = "Jetson AI detected fire risk";
          alert.relayCut = true;
          sendAlertToFirebase(alert);
        }
      }
    }
  }
}

float generateFakeTemperature() {
  fakeTemperature += random(-10, 11) / 10.0;
  
  if (fakeTemperature < 20) fakeTemperature = 20;
  if (fakeTemperature > 80) fakeTemperature = 80;
  
  return fakeTemperature;
}

float generateFakeCurrent() {
  fakeCurrent += random(-5, 6) / 10.0;
  
  if (fakeCurrent < 0) fakeCurrent = 0;
  if (fakeCurrent > 15) fakeCurrent = 15;
  
  return fakeCurrent;
}

float generateFakeVoltage() {
  fakeVoltage += random(-3, 4) / 10.0;
  
  if (fakeVoltage < 190) fakeVoltage = 190;
  if (fakeVoltage > 250) fakeVoltage = 250;
  
  return fakeVoltage;
}

void printSensorData(float temperature, float current, float voltage) {
  Serial.println("================================");
  Serial.println("Sensor Data");
  Serial.println("-------------------------------");
  Serial.print("Temperature: ");
  Serial.print(temperature, 1);
  Serial.println(" C");
  
  Serial.print("Current: ");
  Serial.print(current, 2);
  Serial.println(" A");
  
  Serial.print("Voltage: ");
  Serial.print(voltage, 1);
  Serial.println(" V");
  
  Serial.print("Relay State: ");
  Serial.println(relayState ? "ON" : "OFF");
  
  Serial.print("Jetson Nano: ");
  Serial.println(jetsonAvailable ? "Connected" : "Not Available");
  
  Serial.print("Data Counter: ");
  Serial.println(dataCounter);
  Serial.println("================================");
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi lost, reconnecting...");
    WiFi.reconnect();
    delay(5000);
    return;
  }
  
  float temperature = generateFakeTemperature();
  float current = generateFakeCurrent();
  float voltage = generateFakeVoltage();
  
  sendDataToJetson(temperature, current, voltage);
  receiveFromJetson();
  
  checkAlerts(temperature, current, voltage);
  
  static unsigned long lastPrint = 0;
  if (millis() - lastPrint > 10000) {
    lastPrint = millis();
    printSensorData(temperature, current, voltage);
    sendDataToFirebase(temperature, current, voltage);
  }
  
  delay(500);
}