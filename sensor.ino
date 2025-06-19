#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

#include <WiFi.h>
#include "esp_wpa2.h"
#include <HTTPClient.h>
#include <WiFiClientSecure.h>

#include <RTClib.h>

RTC_DS3231 rtc;
#define OLED_RESET -1
Adafruit_SSD1306 display(128, 64, &Wire, OLED_RESET);

const char* ssid = "HGU_WLAN";
const char* identity = "22000776";
const char* username = "22000776";
const char* password = "-----------"; 
const char* serverURL = "https://iot-final-td9q.onrender.com/lora";

const int irSensorPin1 = 13;
const int irSensorPin2 = 14;

const unsigned long detectionInterval = 500;
const unsigned long analysisInterval = 10000;
//아래 보다 짧은 duration은 무시 
const unsigned long minDetectionDuration = 50;

enum SensorID { SENSOR1, SENSOR2 };

struct SensorPeriod {
  SensorID sensor;
  unsigned long startTime;
  unsigned long endTime;
};

#define MAX_EVENTS 50
SensorPeriod eventQueue[MAX_EVENTS];
volatile int queueStart = 0;
volatile int queueEnd = 0;

// bool prevState1 = HIGH;
// bool prevState2 = HIGH;
bool detecting1 = false;
bool detecting2 = false;
unsigned long detectStart1 = 0;
unsigned long detectStart2 = 0;

void setup() {
  Serial.begin(115200);
  pinMode(irSensorPin1, INPUT);
  pinMode(irSensorPin2, INPUT);

//  if (!rtc.begin()) {
//     Serial.println("❌ RTC 초기화 실패");
//   } else {
//     Serial.println("✅ RTC 초기화 성공");

//     DateTime now = rtc.now();
//     Serial.print("RTC 현재 시간: ");
//     Serial.print(now.hour()); Serial.print(":");
//     Serial.print(now.minute()); Serial.print(":");
//     Serial.print(now.second()); Serial.print(" ");
//     Serial.println(now.day());
//   }


  WiFi.disconnect(true);
  WiFi.mode(WIFI_STA);

  esp_wifi_sta_wpa2_ent_set_identity((uint8_t *)identity, strlen(identity));
  esp_wifi_sta_wpa2_ent_set_username((uint8_t *)username, strlen(username));
  esp_wifi_sta_wpa2_ent_set_password((uint8_t *)password, strlen(password));
  esp_wifi_sta_wpa2_ent_enable();

  WiFi.begin(ssid);
  Serial.print("WiFi 연결 중...");

  configTime(9 * 3600, 0, "pool.ntp.org");

  // 동기화 확인
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    Serial.println("❌ NTP 시간 불러오기 실패");
  } else {
    Serial.println("✅ 시간 동기화 완료");
  }


  xTaskCreatePinnedToCore(sendTask, "SendTask", 8192, NULL, 1, NULL, 1);
}

String getCurrentTimeStr() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "00000000";  // 실패 시 기본값
  }

  char timeStr[9];
  sprintf(timeStr, "%02d%02d%02d%02d",
          timeinfo.tm_mday,
          timeinfo.tm_hour,
          timeinfo.tm_min,
          timeinfo.tm_sec);  // DDHHMMSS
  return timeStr; 
  // return prefix + ":" + String(count) + "/" + String(timeStr);
}


void loop() {
  unsigned long currentTime = millis();

  int state1 = digitalRead(irSensorPin1);
  if (state1 == LOW && !detecting1) {
    detecting1 = true;
    detectStart1 = currentTime;
  }
  if (state1 == HIGH && detecting1) {
    detecting1 = false;
    if (currentTime - detectStart1 >= minDetectionDuration) {
      enqueueEvent({SENSOR1, detectStart1, currentTime});
    }
  }

  int state2 = digitalRead(irSensorPin2);
  if (state2 == LOW && !detecting2) {
    detecting2 = true;
    detectStart2 = currentTime;
  }
  if (state2 == HIGH && detecting2) {
    detecting2 = false;
    if (currentTime - detectStart2 >= minDetectionDuration) {
      enqueueEvent({SENSOR2, detectStart2, currentTime});
    }
  }

  delay(10);
}

void enqueueEvent(SensorPeriod event) {
  int nextEnd = (queueEnd + 1) % MAX_EVENTS;
  if (nextEnd != queueStart) {
    eventQueue[queueEnd] = event;
    queueEnd = nextEnd;
  }
}

bool dequeueEvent(SensorPeriod &event) {
  if (queueStart == queueEnd) return false;
  event = eventQueue[queueStart];
  queueStart = (queueStart + 1) % MAX_EVENTS;
  return true;
}

int compareByStartTime(const void* a, const void* b) {
  SensorPeriod* sa = (SensorPeriod*)a;
  SensorPeriod* sb = (SensorPeriod*)b;
  if (sa->startTime < sb->startTime) return -1;
  else if (sa->startTime > sb->startTime) return 1;
  else return 0;
}

// String getCurrentTimeStr() {
//   DateTime now = rtc.now();

//   char timeStr[9];
//   sprintf(timeStr, "%02d%02d%02d%02d", now.hour(), now.minute(), now.second(), now.day());
//   return String(timeStr);  // 예: "10230418" (10시 23분 04초, 18일)
// }

//암호화 부분 
#include <Crypto.h>
#include <AES.h>

AES128 aes;
byte aesKey[] = "kmhhsyhguiot1234";  // 16-byte key

// base64 인코딩용 문자 테이블
const char base64_table[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

// base64 인코딩 함수
String base64Encode(byte *data, int len) {
  String encoded = "";
  for (int i = 0; i < len; i += 3) {
    int b1 = data[i];
    int b2 = (i + 1 < len) ? data[i + 1] : 0;
    int b3 = (i + 2 < len) ? data[i + 2] : 0;

    encoded += base64_table[(b1 >> 2) & 0x3F];
    encoded += base64_table[((b1 << 4) | (b2 >> 4)) & 0x3F];
    if (i + 1 < len)
      encoded += base64_table[((b2 << 2) | (b3 >> 6)) & 0x3F];
    else
      encoded += '=';
    if (i + 2 < len)
      encoded += base64_table[b3 & 0x3F];
    else
      encoded += '=';
  }
  return encoded;
}

// PKCS7 패딩
String padPKCS7(String data) {
  int padLen = 16 - (data.length() % 16);
  for (int i = 0; i < padLen; i++) {
    data += (char)((uint8_t)padLen);  // 🛠 명시적 unsigned
  }
  return data;
}


// AES + base64 암호화
String encryptToBase64(String plainText) {
  String padded = padPKCS7(plainText);
  int paddedLen = padded.length();  // ⚠️ 정확한 길이 저장
  Serial.println(paddedLen);

  for (int i = 0; i < padded.length(); i++) {
    Serial.print((int)padded[i]); Serial.print(" ");
  }



  // 안전한 버퍼 초기화
  byte plainBytes[64];
  byte encrypted[64];
  memset(plainBytes, 0, 64);
  memset(encrypted, 0, 64);

  // null 없이 바이트 복사
  // padded.getBytes((unsigned char*)plainBytes, paddedLen+1);  // 🔧 여기만 바뀜
  for (int i = 0; i < paddedLen; i++) {
    plainBytes[i] = padded[i];
  }

  
  // AES 블록 단위 암호화
  // aes.setKey(aesKey, sizeof(aesKey));
  aes.setKey(aesKey, 16); 
  for (int i = 0; i < paddedLen; i += 16) {
    aes.encryptBlock(encrypted + i, plainBytes + i);
  }

  // base64 인코딩
  return base64Encode(encrypted, paddedLen);
}




void sendTask(void *pvParameters) {
  for (;;) {
    SensorPeriod localBuffer[MAX_EVENTS];
    int count = 0;
    while (dequeueEvent(localBuffer[count]) && count < MAX_EVENTS - 1) {
      count++;
    }

    //start time을 기준으로 정렬 
    if (count > 1) {
      qsort(localBuffer, count, sizeof(SensorPeriod), compareByStartTime);
    }

    int inCount = 0;
    int outCount = 0;

     //결과 출력 
    Serial.println("📝 이벤트 로그 출력:");
    for (int j = 0; j < count; j++) {
      Serial.print("  [");
      Serial.print(j);
      Serial.print("] 센서: ");
      Serial.print(localBuffer[j].sensor == SENSOR1 ? "SENSOR1" : "SENSOR2");
      Serial.print(", 시간: ");
      Serial.println(localBuffer[j].startTime);
    }


    bool used[MAX_EVENTS] = {false};

    for (int i = 0; i < count - 1; i++) {
      SensorPeriod a = localBuffer[i];
      SensorPeriod b = localBuffer[i + 1];

      if (abs((long)(b.startTime - a.startTime)) <= detectionInterval) {
        if (a.endTime < b.endTime) {
          if (a.sensor == SENSOR1 && b.sensor == SENSOR2) {
            inCount++;
            used[i] = true;
            used[i + 1] = true;
            i++;
          } else if (a.sensor == SENSOR2 && b.sensor == SENSOR1) {
            outCount++;
            used[i] = true;
            used[i + 1] = true;
            i++;
          }
        } else if (a.endTime > b.endTime) {
          // 교차 통과로 판단: 무시
          used[i] = true;
          used[i + 1] = true;
          i++;
        }
      }
    }

    if (count > 0 && !used[count - 1]) {
      enqueueEvent(localBuffer[count - 1]);
    }

    //결과 출력 
    Serial.println("⚠️ 쌍이 되지 않은 이벤트:");
    for (int j = 0; j < count; j++) {
      if (!used[j]) {
        Serial.print("  - 센서: ");
        Serial.print(localBuffer[j].sensor == SENSOR1 ? "SENSOR1" : "SENSOR2");
        Serial.print(", 시간: ");
        Serial.println(localBuffer[j].startTime);
      }
    }

    Serial.print("📊 10초 분석 결과 - IN: ");
    Serial.print(inCount);
    Serial.print(" | OUT: ");
    Serial.println(outCount);


    String timestamp = getCurrentTimeStr(); 
    String message = "Gym:" + String(inCount - outCount)+"/"+timestamp;
    Serial.println(message);
    String encrypted = encryptToBase64(message);
    Serial.println(encrypted);
    // String received = "Gym:" + String(inCount - outCount);

    if (WiFi.status() == WL_CONNECTED && (inCount - outCount) != 0) {
      WiFiClientSecure client;
      client.setInsecure();

      HTTPClient http;
      http.begin(client, serverURL);
      http.addHeader("Content-Type", "text/plain");

      int httpResponseCode = http.POST(encrypted);
      if (httpResponseCode > 0) {
        Serial.print("POST 성공, 응답 코드: ");
        Serial.println(httpResponseCode);
      } else {
        Serial.print("POST 실패, 오류 코드: ");
        Serial.println(httpResponseCode);
      }
      http.end();
    }

    vTaskDelay(analysisInterval / portTICK_PERIOD_MS);
  }
}
