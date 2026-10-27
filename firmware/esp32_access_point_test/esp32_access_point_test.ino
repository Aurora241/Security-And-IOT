/*
  Test kết nối ESP32 -> Mosquitto broker (local)
  Dùng đúng topic đã thiết kế ở tuần 1-2 cho module Access Control.

  Thư viện cần cài trong Arduino IDE (Sketch > Include Library > Manage Libraries):
    - PubSubClient (Nick O'Leary)
    - ArduinoJson   (Benoit Blanchon)
*/

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ==== Sửa 3 giá trị này theo mạng của bạn ====
const char* WIFI_SSID     = "TEN_WIFI_CUA_BAN";
const char* WIFI_PASSWORD = "MAT_KHAU_WIFI";
const char* MQTT_BROKER   = "192.168.1.249";   // IP máy chạy Mosquitto
const int   MQTT_PORT     = 1883;

// ==== Định danh thiết bị — khớp với devices.id / access_points trong DB ====
const char* DEVICE_ID = "esp32_test_01";

char topicCmd[64];
char topicStatus[64];
char topicHeartbeat[64];
char topicLwt[64];

WiFiClient espClient;
PubSubClient mqtt(espClient);

unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 30000; // 30s theo thiết kế

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Dang ket noi WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Da ket noi WiFi, IP: ");
  Serial.println(WiFi.localIP());
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, payload, length);
  if (err) {
    Serial.println("Loi parse JSON");
    return;
  }

  const char* action = doc["action"];
  Serial.print("Nhan lenh: ");
  Serial.println(action);

  if (strcmp(action, "unlock") == 0) {
    // TODO: điều khiển relay/servo mở cửa thật ở đây (giai đoạn sau)
    Serial.println(">>> [MO CUA] (mô phỏng, chưa nối relay thật)");

    // Publish lại trạng thái cửa — đúng thiết kế: retained
    StaticJsonDocument<128> statusDoc;
    statusDoc["door"] = "unlocked";
    statusDoc["timestamp"] = millis();
    char buf[128];
    serializeJson(statusDoc, buf);
    mqtt.publish(topicStatus, buf, true); // true = retained
  }
}

void connectMqtt() {
  while (!mqtt.connected()) {
    Serial.print("Dang ket noi MQTT broker...");

    // Last Will: nếu mất kết nối đột ngột, broker tự publish trạng thái offline
    StaticJsonDocument<64> lwtDoc;
    lwtDoc["status"] = "offline";
    char lwtBuf[64];
    serializeJson(lwtDoc, lwtBuf);

    if (mqtt.connect(DEVICE_ID, NULL, NULL, topicLwt, 1, true, lwtBuf)) {
      Serial.println(" thanh cong!");
      mqtt.subscribe(topicCmd, 1); // QoS 1 cho lệnh điều khiển

      StaticJsonDocument<64> statusDoc;
      statusDoc["door"] = "locked";
      char buf[64];
      serializeJson(statusDoc, buf);
      mqtt.publish(topicStatus, buf, true);
    } else {
      Serial.print(" that bai, rc=");
      Serial.print(mqtt.state());
      Serial.println(" thu lai sau 2s");
      delay(2000);
    }
  }
}

void publishHeartbeat() {
  StaticJsonDocument<128> doc;
  doc["status"] = "online";
  doc["rssi"] = WiFi.RSSI();
  doc["uptime_s"] = millis() / 1000;

  char buf[128];
  serializeJson(doc, buf);
  mqtt.publish(topicHeartbeat, buf); // QoS 0 mặc định — theo đúng thiết kế
  Serial.print("Heartbeat: ");
  Serial.println(buf);
}

void setup() {
  Serial.begin(115200);

  snprintf(topicCmd, sizeof(topicCmd), "access/%s/cmd", DEVICE_ID);
  snprintf(topicStatus, sizeof(topicStatus), "access/%s/status", DEVICE_ID);
  snprintf(topicHeartbeat, sizeof(topicHeartbeat), "access/%s/heartbeat", DEVICE_ID);
  snprintf(topicLwt, sizeof(topicLwt), "access/%s/lwt", DEVICE_ID);

  connectWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
}

void loop() {
  if (!mqtt.connected()) {
    connectMqtt();
  }
  mqtt.loop();

  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    publishHeartbeat();
    lastHeartbeat = millis();
  }
}
