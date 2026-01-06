#include "esp_camera.h"
#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h> 
#include "soc/soc.h"           
#include "soc/rtc_cntl_reg.h"  

// --- 1. DÉFINITION DU MODÈLE DE CAMÉRA (AI THINKER) ---
#define CAMERA_MODEL_AI_THINKER
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26 // Data Pin (SDA)
#define SIOC_GPIO_NUM     27 // Clock Pin (SCL)
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// --- 2. CONFIGURATION RÉSEAU ---
const char* ssid = "ESP32_Robot";       // <<--- N'OUBLIEZ PAS DE REMETTRE VOTRE WIFI
const char* password = "12345678"; // <<--- N'OUBLIEZ PAS DE REMETTRE VOTRE MDP

// --- 3. PINS MOTEURS & ULTRASON ---
#define M1_A 12 
#define M1_B 13 
#define M2_A 14 
#define M2_B 15 

#define TRIG_PIN 3
#define ECHO_PIN 2  

WebServer server(80);

// --- FONCTIONS MOTEURS ---
void stopCar() {
  digitalWrite(M1_A, LOW); digitalWrite(M1_B, LOW);
  digitalWrite(M2_A, LOW); digitalWrite(M2_B, LOW);
}

void moveForward() {
  digitalWrite(M1_A, LOW); digitalWrite(M1_B, HIGH); // Inversé
  digitalWrite(M2_A, LOW); digitalWrite(M2_B, HIGH); // Inversé
}

void moveBackward() {
  digitalWrite(M1_A, HIGH); digitalWrite(M1_B, LOW); // Inversé
  digitalWrite(M2_A, HIGH); digitalWrite(M2_B, LOW); // Inversé
}

void turnLeft() {
  digitalWrite(M1_A, HIGH); digitalWrite(M1_B, LOW); // Utilise les pins de turnRight
  digitalWrite(M2_A, LOW); digitalWrite(M2_B, LOW);
}

void turnRight() {
  digitalWrite(M1_A, LOW); digitalWrite(M1_B, LOW);  // Utilise les pins de turnLeft
  digitalWrite(M2_A, HIGH); digitalWrite(M2_B, LOW);
}

// --- FONCTION ULTRASON ---
String measureDistanceJson() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000); 
  long distance = duration * 0.034 / 2;

  StaticJsonDocument<64> doc;
  doc["distance"] = distance;
  String output;
  serializeJson(doc, output);
  return output;
}

// --- HANDLERS HTTP ---
void handleCommand() {
  if (server.hasArg("go")) {
    String action = server.arg("go");
    if (action == "fwd") moveForward();
    else if (action == "bwd") moveBackward();
    else if (action == "stop") stopCar();
    else if (action == "turnLeft") turnLeft();
    else if (action == "turnRight") turnRight();
    else stopCar();
    server.send(200, "text/plain", "OK");
  } else {
    server.send(400, "text/plain", "Missing arg 'go'");
  }
}

void handleDistance() {
  String jsonDistance = measureDistanceJson();
  server.send(200, "application/json", jsonDistance);
}

void handleJpg() {
  camera_fb_t * fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Camera capture failed");
    server.send(500, "text/plain", "Camera capture failed");
    return;
  }
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.setContentLength(fb->len);
  server.send(200, "image/jpeg", "");
  WiFiClient client = server.client();
  client.write(fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

// --- SETUP CAMERA ---
bool setupCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  
  // CORRECTION BASÉE SUR VOTRE HEADER
  config.pin_sccb_scl = SIOC_GPIO_NUM; 
  config.pin_sccb_sda = SIOD_GPIO_NUM; 
  
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  if(psramFound()){
    config.frame_size = FRAMESIZE_VGA; // Au lieu de FRAMESIZE_SVGA
    config.jpeg_quality = 12;          // 12 est un bon compromis vitesse/qualité
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 10;
    config.fb_count = 1;
  }
  
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    return false;
  }
  return true;
}

// --- SETUP PRINCIPAL ---
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); 

  Serial.begin(115200);

  // Configuration des pins
  pinMode(M1_A, OUTPUT); pinMode(M1_B, OUTPUT);
  pinMode(M2_A, OUTPUT); pinMode(M2_B, OUTPUT);
  pinMode(TRIG_PIN, OUTPUT); 
  pinMode(ECHO_PIN, INPUT);
  
  stopCar(); 

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  // Ajout d'un timeout pour éviter le blocage infini si le WiFi est mauvais
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 20) {
    delay(500);
    Serial.print(".");
    retry++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.print("WiFi IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi Connection Failed! Continuing offline...");
  }

  if (!setupCamera()) {
      Serial.println("Camera Setup Failed!");
  }

  // --- NOUVELLES ROUTES SIMPLIFIÉES ---
server.on("/fwd", HTTP_GET, []() { moveForward(); server.send(200, "text/plain", "OK"); });
server.on("/bwd", HTTP_GET, []() { moveBackward(); server.send(200, "text/plain", "OK"); });
server.on("/turnLeft", HTTP_GET, []() { turnLeft(); server.send(200, "text/plain", "OK"); });
server.on("/turnRight", HTTP_GET, []() { turnRight(); server.send(200, "text/plain", "OK"); });
server.on("/stop", HTTP_GET, []() { stopCar(); server.send(200, "text/plain", "OK"); });

  server.on("/distance", handleDistance);
  server.on("/capture", handleJpg); 
  
  server.begin();
  Serial.println("Server started");
} 

void loop() {
  server.handleClient();
  delay(1); 
}