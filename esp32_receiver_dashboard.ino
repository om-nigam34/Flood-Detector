/*
  ESP32 RECEIVER -> Flood Guard Dashboard
  ----------------------------------------
  Add this to the receiver-side sketch (ESP32 + SX1276/SX1278 LoRa +
  SSD1306 OLED + relay/siren + SIM800L). It POSTs the telemetry
  already decoded from the LoRa packet to the dashboard's
  /api/telemetry endpoint over WiFi, alongside the existing local
  OLED/relay/GSM alert logic (those stay exactly as before).

  Library needed (Arduino Library Manager): ArduinoJson (Benoit Blanchon)
  WiFi.h and HTTPClient.h ship with the ESP32 board package.
*/

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ----------------------------- CONFIG -----------------------------
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// IP of the computer running app.py, e.g. "http://192.168.1.50:5000/api/telemetry"
const char* DASHBOARD_URL = "http://192.168.1.50:5000/api/telemetry";

// Must match FLOOD_API_KEY in app.py (default "changeme123")
const char* API_KEY = "changeme123";

const char* NODE_ID = "node-1";
// --------------------------------------------------------------------

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Connecting to WiFi");
  unsigned long start = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - start < 15000) {
    delay(300);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected, IP: " + WiFi.localIP().toString());
  } else {
    Serial.println("\nWiFi connect failed - will retry on next send");
  }
}

/*
  Call this right after you've decoded a LoRa telemetry packet and
  computed waterDepthCm / flowRateLpm / temperatureC / humidityPct /
  batteryVolts / rssi / status in your existing receiver code.
*/
bool sendToDashboard(float waterDepthCm, float flowRateLpm,
                      float temperatureC, float humidityPct,
                      float batteryVolts, int rssi,
                      const char* status) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  StaticJsonDocument<256> doc;
  doc["node_id"] = NODE_ID;
  doc["water_depth_cm"] = waterDepthCm;
  doc["flow_rate_lpm"] = flowRateLpm;
  doc["temperature_c"] = temperatureC;
  doc["humidity_pct"] = humidityPct;
  doc["battery_v"] = batteryVolts;
  doc["rssi"] = rssi;
  doc["status"] = status;

  String body;
  serializeJson(doc, body);

  HTTPClient http;
  http.begin(DASHBOARD_URL);
  http.addHeader("Content-Type", "application/json");
  http.addHeader("X-API-Key", API_KEY);
  http.setTimeout(5000);

  int code = http.POST(body);
  bool ok = (code == 201);
  Serial.printf("Dashboard POST -> HTTP %d%s\n", code, ok ? " (ok)" : "");
  http.end();
  return ok;
}

void setup() {
  Serial.begin(115200);

  // ... existing receiver setup: LoRa.begin(...), OLED init,
  //     pinMode(RELAY_PIN, OUTPUT), SIM800L serial init, etc.

  connectWiFi();
}

void loop() {
  // ... existing receiver loop: if (LoRa.parsePacket()) { decode
  //     packet into waterDepthCm, flowRateLpm, temperatureC,
  //     humidityPct, batteryVolts, rssi; update OLED; evaluate
  //     thresholds into `status`; drive relay/siren and SIM800L as
  //     already designed; THEN also push it to the web dashboard: }
  //
  // Example call once you have the decoded values:
  //
  //   sendToDashboard(waterDepthCm, flowRateLpm, temperatureC,
  //                    humidityPct, batteryVolts, rssi, status);
}