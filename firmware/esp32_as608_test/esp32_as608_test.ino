/*
  Test cam bien van tay AS608 tren ESP32 that + dong bo ket qua enroll len Supabase qua MQTT.
  Muc tieu: kiem tra ket noi UART, dang ky (enroll) 1 van tay, xac thuc (verify) real-time,
  va gui su kien enroll thanh cong len backend qua broker MQTT (huong 2 da chot).

  Thu vien can cai (Arduino IDE > Sketch > Include Library > Manage Libraries):
    - Adafruit Fingerprint Sensor Library (tac gia Adafruit)
    - PubSubClient (Nick O'Leary)
    - ArduinoJson (Benoit Blanchon)
    - ESP32Servo (Kevin Harrington / Jakub...) - dieu khien servo SG90 mo cua

  Day noi (theo so do da chot):
    AS608 VCC + VA -> ESP32 3.3V (noi chung 1 chan)
    AS608 GND      -> ESP32 GND
    AS608 TXD      -> ESP32 GPIO18 (RX2)
    AS608 RXD      -> ESP32 GPIO19 (TX2)
    AS608 TOUCH    -> khong noi

    Servo SG90 (mo cua):
    SG90 day do (VCC)   -> ngoai nguon 5V rieng (KHONG lay tu 3.3V/5V cua ESP32 qua USB -
                           servo giat dong lam ESP32 reset/mat WiFi) - vi du pin 5V tu mach
                           giam ap rieng hoac nguon USB thu 2, GND phai noi CHUNG voi ESP32 GND
    SG90 day den (GND)  -> GND chung voi ESP32
    SG90 day cam (PWM)  -> ESP32 GPIO13
    (Neu dung relay thay servo: xem comment canh #define DOOR_SERVO_PIN de doi sang
     digitalWrite, va relay module thuong co san opto-isolation nen co the dung chung
     nguon 3.3V/5V cua ESP32 duoc, kiem tra datasheet module dang co)

  Luong MQTT (khop voi backend/app/services/mqtt_subscriber.py va devices.py):
    Backend -> ESP32       access/{DEVICE_ID}/cmd        {action:"enroll_fingerprint", employee_code, slot_id}
    ESP32 -> Backend       access/{DEVICE_ID}/enroll      {employee_code, credential_type, slot_id}
    Backend -> ESP32       access/{DEVICE_ID}/enroll_ack {success, message, ...}
    Backend -> ESP32       access/{DEVICE_ID}/cmd        {action:"open_door"} - CHI gui sau khi
                           backend da cham access_policies va ket luan "accepted" (xem
                           backend/app/services/access_control.py) - ESP32 khong tu quyet dinh,
                           chi thi hanh mo servo roi tu khoa lai sau DOOR_OPEN_MS (fail-secure)
    ESP32 -> Backend       access/{DEVICE_ID}/heartbeat  {status:"online", rssi, uptime_s} -
                           moi 30s (QoS 0, khong retain), backend cap nhat devices.status
                           + devices.last_seen trong Supabase (xem mqtt_subscriber.py)
    ESP32 -> Backend       access/{DEVICE_ID}/lwt        {status:"offline"} - Last Will,
                           retained, broker TU gui ho khi ESP32 mat ket noi dot ngot (rot
                           nguon, mat WiFi...) - khong can ESP32 con song de gui duoc

  Co 2 cach kich hoat enroll:
    1) Tu trang web (khong can Serial Monitor) - bam nut tren web, ESP32 tu nhan lenh qua
       topic "cmd" va tu chay, chi can dat ngon tay len cam bien khi duoc yeu cau.
    2) Thu cong tren Serial Monitor (115200 baud), go 1 trong cac phim:
       e = dang ky (enroll) van tay moi (hoi ID + ma nhan vien ngay tren Serial)
       v = xac thuc (verify) mot lan
       l = xac thuc lien tuc (giong luc hoat dong thuc te)
       n = kiem tra so luong template da luu
       d = xoa 1 template theo ID
*/

#include <Adafruit_Fingerprint.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <ESP32Servo.h>

#define AS608_RX_PIN 18   // ESP32 RX2 <- AS608 TXD
#define AS608_TX_PIN 19   // ESP32 TX2 -> AS608 RXD
#define AS608_BAUD   57600

// Servo SG90 mo cua - chan tin hieu con TRONG, chua dung cho gi khac trong file nay.
// Neu dung relay thay vi servo: doi pinMode(DOOR_SERVO_PIN, OUTPUT) + digitalWrite HIGH/LOW
// trong openDoor()/closeDoor() thay cho servo.write(), giu nguyen phan con lai.
#define DOOR_SERVO_PIN   13
#define DOOR_ANGLE_LOCKED 0
#define DOOR_ANGLE_OPEN   90
#define DOOR_OPEN_MS      4000  // mo bao nhieu lau truoc khi tu khoa lai (fail-secure)

Servo doorServo;
bool doorIsOpen = false;
unsigned long doorCloseAt = 0;

// ==== Sua 3 gia tri nay theo mang cua ban (giong esp32_access_point_test.ino) ====
const char* WIFI_SSID     = "Nha Tro SV Khanh An";
const char* WIFI_PASSWORD = "68686868";
const char* MQTT_BROKER   = "192.168.1.249";   // IP may chay Mosquitto
const int   MQTT_PORT     = 1883;
const int   BACKEND_PORT  = 8001;              // FastAPI (cung may voi Mosquitto)
const char* DEVICE_ID     = "esp32_test_01";

char topicEnroll[64];
char topicEnrollAck[64];
char topicCmd[64];
char topicProgress[64];
char topicVerifyResult[64];
char topicHeartbeat[64];
char topicLwt[64];

unsigned long lastHeartbeat = 0;
const unsigned long HEARTBEAT_INTERVAL = 30000; // 30s - giong esp32_access_point_test.ino

HardwareSerial as608Serial(2); // dung UART2
Adafruit_Fingerprint finger(&as608Serial);

WiFiClient espClient;
PubSubClient mqtt(espClient);

volatile bool ackReceived = false;
String ackMessage = "";

// Lenh enroll nhan tu web qua MQTT - xu ly trong loop(), KHONG xu ly ngay trong
// callback vi cac buoc chup/luu van tay chan lau, se lam gian doan mqtt.loop().
volatile bool pendingEnrollRequested = false;
int pendingSlotId = -1;
String pendingEmployeeCode = "";

volatile bool pendingVerifyRequested = false;
int pendingVerifySlotId = -1;
String pendingVerifyEmployeeCode = "";

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Dang ket noi WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.print("Da ket noi WiFi, IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("KHONG ket noi duoc WiFi - van test duoc van tay, nhung khong dong bo len Supabase.");
  }
}

void onMqttMessage(char* topic, byte* payload, unsigned int length) {
  String msg;
  for (unsigned int i = 0; i < length; i++) msg += (char)payload[i];
  String topicStr = String(topic);

  if (topicStr == topicEnrollAck) {
    ackMessage = msg;
    ackReceived = true;
    return;
  }

  if (topicStr == topicCmd) {
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, msg) != DeserializationError::Ok) {
      Serial.println("Lenh MQTT nhan duoc khong phai JSON hop le.");
      return;
    }
    const char* action = doc["action"] | "";
    if (strcmp(action, "enroll_fingerprint") == 0) {
      pendingEmployeeCode = String((const char*)(doc["employee_code"] | ""));
      pendingSlotId = doc["slot_id"] | -1;
      pendingEnrollRequested = true; // xu ly trong loop(), khong xu ly o day
    } else if (strcmp(action, "verify_fingerprint") == 0) {
      pendingVerifyEmployeeCode = String((const char*)(doc["employee_code"] | ""));
      pendingVerifySlotId = doc["slot_id"] | -1;
      pendingVerifyRequested = true; // xu ly trong loop(), khong xu ly o day
    } else if (strcmp(action, "open_door") == 0) {
      // Backend chi gui lenh nay SAU KHI da cham access_policies va ket luan "accepted" -
      // ESP32 khong tu quyet dinh mo cua, chi thi hanh. Servo nhanh nen xu ly ngay o day
      // (khac enroll/verify van tay can doi nguoi dat tay, phai tri hoan qua loop()).
      openDoor();
    }
  }
}

void openDoor() {
  doorServo.write(DOOR_ANGLE_OPEN);
  doorIsOpen = true;
  doorCloseAt = millis() + DOOR_OPEN_MS;
  Serial.println(">>> MO CUA (servo) - se tu khoa lai sau " + String(DOOR_OPEN_MS / 1000) + "s");
}

void closeDoorIfDue() {
  if (doorIsOpen && millis() >= doorCloseAt) {
    doorServo.write(DOOR_ANGLE_LOCKED);
    doorIsOpen = false;
    Serial.println(">>> Da tu khoa cua lai.");
  }
}

void publishHeartbeat() {
  StaticJsonDocument<128> doc;
  doc["status"] = "online";
  doc["rssi"] = WiFi.RSSI();
  doc["uptime_s"] = millis() / 1000;

  char buf[128];
  serializeJson(doc, buf);
  mqtt.publish(topicHeartbeat, buf); // QoS 0, khong retain - giong esp32_access_point_test.ino
}

void connectMqtt() {
  if (WiFi.status() != WL_CONNECTED) return;
  if (mqtt.connected()) return;

  Serial.print("Dang ket noi MQTT broker...");

  // Last Will: neu mat ket noi dot ngot, broker tu publish ho trang thai offline (retained)
  // len topicLwt - khong can ESP32 con song de gui, dung de do "mat ket noi" thuc su.
  StaticJsonDocument<64> lwtDoc;
  lwtDoc["status"] = "offline";
  char lwtBuf[64];
  serializeJson(lwtDoc, lwtBuf);

  if (mqtt.connect(DEVICE_ID, NULL, NULL, topicLwt, 1, true, lwtBuf)) {
    Serial.println(" thanh cong!");
    mqtt.subscribe(topicEnrollAck, 1);
    mqtt.subscribe(topicCmd, 1);
    publishHeartbeat(); // bao online ngay sau khi vua ket noi, khong doi het 30s dau tien
    lastHeartbeat = millis();
  } else {
    Serial.print(" that bai, rc=");
    Serial.println(mqtt.state());
  }
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println();
  Serial.println("=== Test AS608 tren ESP32 ===");

  as608Serial.begin(AS608_BAUD, SERIAL_8N1, AS608_RX_PIN, AS608_TX_PIN);
  delay(100);

  if (finger.verifyPassword()) {
    Serial.println("Da tim thay cam bien AS608, ket noi UART OK!");
  } else {
    Serial.println("KHONG tim thay cam bien. Kiem tra lai:");
    Serial.println("  - Day TXD/RXD co bi cam nguoc khong (TXD sensor -> RX2, RXD sensor -> TX2)");
    Serial.println("  - VCC/VA da noi 3.3V chua, GND da noi chung chua");
    Serial.println("  - Baudrate co dung 57600 khong (mot so module dung 9600)");
    while (1) { delay(1000); }
  }

  doorServo.setPeriodHertz(50);
  doorServo.attach(DOOR_SERVO_PIN, 500, 2400);
  doorServo.write(DOOR_ANGLE_LOCKED); // trang thai khoi dong = khoa (fail-secure)

  finger.getParameters();
  Serial.print("So template toi da: ");
  Serial.println(finger.capacity);
  Serial.print("Kich thuoc security level: ");
  Serial.println(finger.security_level);

  snprintf(topicEnroll, sizeof(topicEnroll), "access/%s/enroll", DEVICE_ID);
  snprintf(topicEnrollAck, sizeof(topicEnrollAck), "access/%s/enroll_ack", DEVICE_ID);
  snprintf(topicCmd, sizeof(topicCmd), "access/%s/cmd", DEVICE_ID);
  snprintf(topicProgress, sizeof(topicProgress), "access/%s/enroll_progress", DEVICE_ID);
  snprintf(topicVerifyResult, sizeof(topicVerifyResult), "access/%s/verify_result", DEVICE_ID);
  snprintf(topicHeartbeat, sizeof(topicHeartbeat), "access/%s/heartbeat", DEVICE_ID);
  snprintf(topicLwt, sizeof(topicLwt), "access/%s/lwt", DEVICE_ID);

  connectWiFi();
  mqtt.setServer(MQTT_BROKER, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  connectMqtt();

  printMenu();
}

void printMenu() {
  Serial.println();
  Serial.println("--- Chon lenh ---");
  Serial.println("e = dang ky (enroll) van tay moi");
  Serial.println("v = xac thuc (verify) 1 lan");
  Serial.println("l = xac thuc lien tuc (nhu luc hoat dong that)");
  Serial.println("n = so luong template da luu");
  Serial.println("d = xoa 1 template theo ID");
  Serial.println("-----------------");
}

void loop() {
  connectMqtt();
  mqtt.loop();
  closeDoorIfDue();

  if (millis() - lastHeartbeat > HEARTBEAT_INTERVAL) {
    publishHeartbeat();
    lastHeartbeat = millis();
  }

  if (pendingEnrollRequested) {
    pendingEnrollRequested = false;
    Serial.println();
    Serial.print("Lenh tu web: dang ky van tay ID #");
    Serial.print(pendingSlotId);
    Serial.print(" cho nhan vien ");
    Serial.println(pendingEmployeeCode);
    enrollFingerprintAuto(pendingSlotId, pendingEmployeeCode);
    printMenu();
  }

  if (pendingVerifyRequested) {
    pendingVerifyRequested = false;
    Serial.println();
    Serial.print("Lenh tu web: xac thuc van tay, ky vong ID #");
    Serial.print(pendingVerifySlotId);
    Serial.print(" (");
    Serial.print(pendingVerifyEmployeeCode);
    Serial.println(")");
    verifyFingerprintAuto(pendingVerifySlotId, pendingVerifyEmployeeCode);
    printMenu();
  }

  if (Serial.available()) {
    char cmd = Serial.read();
    flushSerialLineEnding(); // xoa \r hoac \n con sot lai sau ky tu lenh

    switch (cmd) {
      case 'e': enrollFingerprint(); printMenu(); break;
      case 'v': verifyOnce(); printMenu(); break;
      case 'l': verifyLoop(); printMenu(); break;
      case 'n': countTemplates(); printMenu(); break;
      case 'd': deleteFingerprint(); printMenu(); break;
      default: break; // bo qua ky tu xuong dong, khoang trang...
    }
  }
}

// ================== ENROLL (thu cong, go 'e' tren Serial) ==================
void enrollFingerprint() {
  Serial.print("Nhap ID muon luu (1-127): ");
  int id = readNumberFromSerial();
  if (id <= 0) {
    Serial.println("ID khong hop le, huy.");
    return;
  }

  if (!captureAndStoreFingerprint(id)) return;

  Serial.print("Nhap ma nhan vien (vd: NV001) de gan cho ID #");
  Serial.print(id);
  Serial.print(": ");
  String employeeCode = readStringFromSerial();
  if (employeeCode.length() == 0) {
    Serial.println("Khong nhap ma nhan vien - bo qua buoc dong bo Supabase.");
    return;
  }
  syncEnrollToBackend(id, employeeCode);
}

// ================== ENROLL (tu dong, kich hoat tu web qua MQTT) ==================
void enrollFingerprintAuto(int id, String employeeCode) {
  if (id <= 0 || employeeCode.length() == 0) {
    Serial.println("Lenh tu web thieu slot_id/employee_code hop le, huy.");
    return;
  }
  if (!captureAndStoreFingerprint(id)) return;
  syncEnrollToBackend(id, employeeCode);
}

// Gui tien trinh (step + message) len MQTT de web hien thi giong dang xem Serial Monitor.
void publishProgress(const char* step, const char* message) {
  StaticJsonDocument<192> doc;
  doc["step"] = step;
  doc["message"] = message;
  char buf[192];
  serializeJson(doc, buf);
  if (mqtt.connected()) mqtt.publish(topicProgress, buf, false); // QoS0 - chi la thong bao tien trinh
}

// Hoi backend "slot_id nay la nhan vien nao" qua HTTP GET - dung khi phat hien
// van tay trung de bao ten thay vi chi bao mot con so tho.
String resolveSlotToEmployeeCode(int slotId) {
  if (WiFi.status() != WL_CONNECTED) return "(khong ro - mat WiFi)";

  HTTPClient http;
  char url[160];
  snprintf(url, sizeof(url), "http://%s:%d/api/v1/devices/%s/slot/%d",
           MQTT_BROKER, BACKEND_PORT, DEVICE_ID, slotId);
  http.begin(url);
  int httpCode = http.GET();

  String result = "(khong ro)";
  if (httpCode == 200) {
    String payload = http.getString();
    StaticJsonDocument<256> doc;
    if (deserializeJson(doc, payload) == DeserializationError::Ok) {
      const char* code = doc["employee_code"] | "";
      if (strlen(code) > 0) result = String(code);
    }
  }
  http.end();
  return result;
}

// Chup 2 lan va luu template vao AS608 - dung chung cho ca 2 luong enroll o tren.
// Tra ve true neu luu thanh cong.
bool captureAndStoreFingerprint(int id) {
  Serial.print("Bat dau dang ky van tay cho ID #");
  Serial.println(id);

  int p = -1;
  Serial.println("Dat ngon tay len cam bien...");
  publishProgress("waiting_finger_1", "Dat ngon tay len cam bien (lan 1)");
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    switch (p) {
      case FINGERPRINT_OK: Serial.println("Da chup anh."); break;
      case FINGERPRINT_NOFINGER: break; // cho, khong in spam
      default: Serial.println("Loi khi chup anh, thu lai."); break;
    }
  }
  publishProgress("captured_1", "Da chup van tay lan 1 thanh cong");

  p = finger.image2Tz(1);
  if (p != FINGERPRINT_OK) {
    Serial.println("Loi xu ly anh lan 1, huy dang ky.");
    publishProgress("error", "Loi xu ly anh lan 1, huy dang ky");
    return false;
  }

  // Kiem tra trung lap: van tay nay da ton tai o slot nao khac chua? Chi can 1 lan
  // chup la kiem tra duoc, khong can doi het ca 2 lan chup moi bao loi.
  publishProgress("checking_duplicate", "Dang kiem tra van tay co bi trung khong...");
  p = finger.fingerFastSearch();
  if (p == FINGERPRINT_OK) {
    int existingId = finger.fingerID;
    String owner = resolveSlotToEmployeeCode(existingId);
    String msg = "Van tay nay da dang ky cho " + owner + " (slot #" + String(existingId) + ") - huy dang ky";
    Serial.println(msg);
    publishProgress("error", msg.c_str());
    return false;
  }

  Serial.println("Nhac ngon tay ra...");
  publishProgress("remove_finger", "Nhac ngon tay ra khoi cam bien");
  delay(1500);
  p = 0;
  while (p != FINGERPRINT_NOFINGER) {
    p = finger.getImage();
  }

  Serial.println("Dat lai CUNG ngon tay do len cam bien lan 2...");
  publishProgress("waiting_finger_2", "Dat LAI CUNG ngon tay do len cam bien (lan 2)");
  p = -1;
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    switch (p) {
      case FINGERPRINT_OK: Serial.println("Da chup anh lan 2."); break;
      case FINGERPRINT_NOFINGER: break;
      default: Serial.println("Loi khi chup anh, thu lai."); break;
    }
  }
  publishProgress("captured_2", "Da chup van tay lan 2 thanh cong");

  p = finger.image2Tz(2);
  if (p != FINGERPRINT_OK) {
    Serial.println("Loi xu ly anh lan 2, huy dang ky.");
    publishProgress("error", "Loi xu ly anh lan 2, huy dang ky");
    return false;
  }

  p = finger.createModel();
  if (p != FINGERPRINT_OK) {
    Serial.println("2 anh khong khop nhau (khac ngon tay hoac dat lech qua nhieu), huy dang ky.");
    publishProgress("error", "2 lan quet khong khop nhau - khac ngon tay hoac dat lech qua nhieu");
    return false;
  }

  publishProgress("storing", "Dang luu template vao cam bien...");
  p = finger.storeModel(id);
  if (p == FINGERPRINT_OK) {
    Serial.print("DANG KY THANH CONG - da luu vao ID #");
    Serial.println(id);
    return true;
  }

  Serial.println("Loi khi luu template vao bo nho cam bien.");
  publishProgress("error", "Loi khi luu template vao bo nho cam bien");
  return false;
}

// Gui su kien enroll len backend qua MQTT (huong 2) de luu anh xa
// employee_code <-> fingerprint_slot_id vao Supabase. Van tay THAT van chi
// nam tren AS608, khong gui len mang - dung theo chinh sach da chot.
void syncEnrollToBackend(int slotId, String employeeCode) {
  if (!mqtt.connected()) {
    Serial.println("Chua ket noi MQTT/WiFi - bo qua buoc dong bo Supabase (van tay van luu tren cam bien).");
    return;
  }

  StaticJsonDocument<128> doc;
  doc["employee_code"] = employeeCode;
  doc["credential_type"] = "fingerprint";
  doc["slot_id"] = slotId;
  char buf[128];
  serializeJson(doc, buf);

  ackReceived = false;
  mqtt.publish(topicEnroll, buf, false);
  Serial.print("Da gui len broker: ");
  Serial.println(buf);
  Serial.println("Cho backend xac nhan...");

  unsigned long start = millis();
  while (!ackReceived && millis() - start < 5000) {
    mqtt.loop();
    delay(20);
  }

  if (ackReceived) {
    Serial.print("Phan hoi tu backend: ");
    Serial.println(ackMessage);
  } else {
    Serial.println("Khong nhan duoc phan hoi trong 5s - kiem tra backend/mosquitto co dang chay khong.");
  }
}

// ================== VERIFY (1 lan) ==================
void verifyOnce() {
  Serial.println("Dat ngon tay len cam bien de xac thuc...");
  unsigned long start = millis();
  int p = -1;
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (millis() - start > 8000) {
      Serial.println("Het thoi gian cho, huy.");
      return;
    }
  }
  reportVerifyResult();
}

// ================== VERIFY (lien tuc) ==================
void verifyLoop() {
  Serial.println("Che do xac thuc lien tuc - go phim bat ky de dung.");
  while (!Serial.available()) {
    int p = finger.getImage();
    if (p == FINGERPRINT_OK) {
      reportVerifyResult();
      delay(1000); // tranh doc lai ngay lap tuc cung 1 lan cham
    }
  }
  Serial.read(); // xoa ky tu vua go de thoat
}

void reportVerifyResult() {
  int p = finger.image2Tz();
  if (p != FINGERPRINT_OK) {
    Serial.println("Loi xu ly anh, thu lai.");
    return;
  }

  p = finger.fingerFastSearch();
  if (p == FINGERPRINT_OK) {
    Serial.print(">>> MO CUA - Xac thuc thanh cong! ID #");
    Serial.print(finger.fingerID);
    Serial.print(" | Do tin cay (confidence): ");
    Serial.println(finger.confidence);
  } else if (p == FINGERPRINT_NOTFOUND) {
    Serial.println(">>> TU CHOI - Khong tim thay van tay khop trong CSDL.");
  } else {
    Serial.println(">>> Loi trong qua trinh tim kiem.");
  }
}

// ================== VERIFY (tu dong, kich hoat tu web qua MQTT) ==================
// Verify 1:1: dung fingerFastSearch (1:N noi bo cam bien) nhung CHI cong nhan khop
// neu ID tim thay == expectedSlotId da duoc web/backend chi dinh truoc cho dung
// nhan vien nay - dung theo quyet dinh thiet ke #1 (khong phai 1:N thuan tuy).
void verifyFingerprintAuto(int expectedSlotId, String employeeCode) {
  if (expectedSlotId <= 0) {
    Serial.println("Lenh xac thuc tu web thieu slot_id hop le, huy.");
    return;
  }

  Serial.println("Dat ngon tay len cam bien de xac thuc...");
  publishProgress("waiting_finger_verify", "Dat ngon tay len cam bien de xac thuc");

  unsigned long start = millis();
  int p = -1;
  while (p != FINGERPRINT_OK) {
    p = finger.getImage();
    if (millis() - start > 10000) {
      Serial.println("Het thoi gian cho, huy xac thuc.");
      publishProgress("error", "Het thoi gian cho ngon tay");
      return;
    }
  }
  publishProgress("checking", "Dang kiem tra van tay...");

  p = finger.image2Tz();
  if (p != FINGERPRINT_OK) {
    Serial.println("Loi xu ly anh, huy xac thuc.");
    publishProgress("error", "Loi xu ly anh khi xac thuc");
    return;
  }

  bool matched = false;
  int foundId = -1;
  int confidence = 0;

  p = finger.fingerFastSearch();
  if (p == FINGERPRINT_OK) {
    foundId = finger.fingerID;
    confidence = finger.confidence;
    matched = (foundId == expectedSlotId);
    Serial.print(matched ? ">>> MO CUA - Xac thuc thanh cong! ID #" : ">>> TU CHOI - Van tay khong dung nguoi! ID tim thay #");
    Serial.print(foundId);
    Serial.print(" | Do tin cay: ");
    Serial.println(confidence);
  } else if (p == FINGERPRINT_NOTFOUND) {
    Serial.println(">>> TU CHOI - Khong tim thay van tay khop trong CSDL.");
  } else {
    Serial.println(">>> Loi trong qua trinh tim kiem.");
  }

  publishProgress(matched ? "matched" : "denied",
                   matched ? "Xac thuc thanh cong" : "Van tay khong khop");

  if (mqtt.connected()) {
    StaticJsonDocument<192> doc;
    doc["matched"] = matched;
    doc["found_id"] = foundId;
    doc["confidence"] = confidence;
    doc["expected_slot_id"] = expectedSlotId;
    doc["employee_code"] = employeeCode;
    char buf[192];
    serializeJson(doc, buf);
    mqtt.publish(topicVerifyResult, buf, true); // retained=true - backend/web doc duoc ngay ket qua gan nhat
  }
}

// ================== TIEN ICH ==================
void countTemplates() {
  finger.getTemplateCount();
  Serial.print("So template dang luu trong cam bien: ");
  Serial.println(finger.templateCount);
}

void deleteFingerprint() {
  Serial.print("Nhap ID muon xoa: ");
  int id = readNumberFromSerial();
  if (id <= 0) {
    Serial.println("ID khong hop le, huy.");
    return;
  }
  int p = finger.deleteModel(id);
  if (p == FINGERPRINT_OK) {
    Serial.print("Da xoa ID #");
    Serial.println(id);
  } else {
    Serial.println("Xoa that bai (co the ID chua ton tai).");
  }
}

void flushSerialLineEnding() {
  delay(5); // cho ky tu ke tiep (\r hoac \n) kip toi bo dem
  while (Serial.available() && (Serial.peek() == '\n' || Serial.peek() == '\r')) {
    Serial.read();
  }
}

int readNumberFromSerial() {
  // doc theo dong thay vi parseInt() tho, tranh bi ky tu xuong dong con sot pha
  String input = "";
  unsigned long start = millis();
  unsigned long lastCharAt = millis();

  while (millis() - start < 15000) {
    if (Serial.available()) {
      char c = Serial.read();
      lastCharAt = millis();
      if (c == '\n' || c == '\r') {
        if (input.length() > 0) break; // da co du lieu, ket thuc dong
        else continue;                 // dong trong (ky tu thua), bo qua
      }
      input += c;
    } else if (input.length() > 0 && millis() - lastCharAt > 300) {
      break; // khong con ky tu moi trong 300ms -> coi nhu nhap xong
    }
  }

  input.trim();
  if (input.length() == 0) return -1;
  return input.toInt();
}

String readStringFromSerial() {
  String input = "";
  unsigned long start = millis();
  unsigned long lastCharAt = millis();

  while (millis() - start < 15000) {
    if (Serial.available()) {
      char c = Serial.read();
      lastCharAt = millis();
      if (c == '\n' || c == '\r') {
        if (input.length() > 0) break;
        else continue;
      }
      input += c;
    } else if (input.length() > 0 && millis() - lastCharAt > 300) {
      break;
    }
  }

  input.trim();
  return input;
}
