#include <Arduino.h>
#include <WiFi.h>
#include <Firebase_ESP_Client.h>
#include <addons/TokenHelper.h>

const char* WIFI_SSID = "Chau Darith";
const char* WIFI_PASSWORD = "12345678";

#define API_KEY "AIzaSyAyLWOnnvc8AxLe8nRBnK9szMh-8l_HetU"
#define DATABASE_URL "https://smartdb-3ca26-default-rtdb.asia-southeast1.firebasedatabase.app"

FirebaseData fbdo;
FirebaseAuth auth;
FirebaseConfig config;

bool signupOK = false;

float fakeTemperature = 25.0;
float fakeCurrent = 2.5;
int dataCounter = 0;

void setup() {
  Serial.begin(115200);
  delay(2000);
  
  Serial.println();
  Serial.println("SmartDB Firebase Integration");
  
  setupWiFi();
  setupFirebase();
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
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("WiFi Failed");
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
    Serial.printf("Firebase signup failed: %s\n", config.signer.signupError.message.c_str());
    signupOK = false;
  }
  
  config.token_status_callback = tokenStatusCallback;
  
  Firebase.begin(&config, &auth);
  Firebase.reconnectWiFi(true);
}

void sendDataToFirebase(float temperature, float current) {
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
  json.set("timestamp", Firebase.getTimestamp());
  json.set("device", "SmartDB_ESP32");
  json.set("readings_count", dataCounter);
  
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

void sendAlertToFirebase(String alertType, float value, float threshold) {
  if (!signupOK) {
    return;
  }
  
  String path = "/alerts/alert_" + String(millis());
  
  FirebaseJson json;
  json.set("alert_type", alertType);
  json.set("value", value);
  json.set("threshold", threshold);
  json.set("timestamp", Firebase.getTimestamp());
  json.set("status", "active");
  json.set("device", "SmartDB_ESP32");
  
  Serial.println("Sending alert to Firebase...");
  
  if (Firebase.RTDB.setJSON(&fbdo, path, &json)) {
    Serial.println("Alert sent successfully!");
  } else {
    Serial.print("Failed to send alert: ");
    Serial.println(fbdo.errorReason());
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

void checkForAlerts(float temperature, float current) {
  const float TEMP_THRESHOLD = 60.0;
  const float CURRENT_THRESHOLD = 10.0;
  
  if (temperature > TEMP_THRESHOLD) {
    Serial.println("FIRE ALERT: Temperature exceeds threshold!");
    sendAlertToFirebase("Overheat", temperature, TEMP_THRESHOLD);
  }
  
  if (current > CURRENT_THRESHOLD) {
    Serial.println("OVERLOAD ALERT: Current exceeds threshold!");
    sendAlertToFirebase("Overload", current, CURRENT_THRESHOLD);
  }
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
  
  Serial.println("--- Sensor Data (Fake) ---");
  Serial.print("Temperature: ");
  Serial.print(temperature, 1);
  Serial.println(" C");
  
  Serial.print("Current: ");
  Serial.print(current, 2);
  Serial.println(" A");
  
  sendDataToFirebase(temperature, current);
  checkForAlerts(temperature, current);
  
  Serial.println();
  
  delay(10000);
}