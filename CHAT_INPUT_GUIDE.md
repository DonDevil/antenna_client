# Chat Input Requirements & Examples

## ⚠️ Server Validation Rules

The antenna optimization server enforces these rules on user input:

| Rule | Requirement | Example |
|------|-------------|---------|
| **Minimum Length** | >= 10 characters | ❌ "hi" / ✅ "2.4 GHz antenna" |
| **Maximum Length** | <= 4000 characters | ✅ Normal text / ❌ Very long documents |
| **Content Type** | Must be a real antenna design request | ✅ "2.4 GHz patch" / ❌ Random text |

---

## ✅ Valid Chat Messages

The server will accept and process these types of messages:

### **Frequency Specifications**
```
"I need a 2.4 GHz antenna"
"Design a WiFi antenna for 5 GHz"
"Create an antenna tuned to 900 MHz"
```

### **With Bandwidth**
```
"2.4 GHz patch antenna with 200 MHz bandwidth"
"5 GHz WiFi antenna with 80 MHz bandwidth"
"UWB antenna from 3 to 10 GHz"
```

### **With Constraints**
```
"Microstrip patch antenna at 2.4 GHz on FR-4 substrate"
"Compact antenna, 2.4 GHz, minimum 6 dBi gain"
"2.4 GHz patch antenna optimized for efficiency"
```

### **Better Examples**
```
✅ "I need a 2.4 GHz patch antenna optimized for WiFi"
✅ "Design a 5 GHz antenna with 200 MHz bandwidth on FR-4"
✅ "Create a compact microstrip patch antenna at 2.4 GHz"
✅ "I'm looking for a high-gain antenna at 900 MHz"
```

---

## ❌ Invalid Chat Messages

These will be rejected with an error:

### **Too Short (< 10 chars)**
```
❌ "hi"
❌ "hello"
❌ "antenna"
❌ "2.4 GHz"  (exactly 7 chars)
```

### **Not Antenna-Related**
```
❌ "what is a flower?"
❌ "tell me a joke"
❌ "how to cook pasta"
❌ Random single words
```

### **Malformed**
```
❌ "2.4" (too short and ambiguous)
❌ "GHz" (not enough context)
❌ Just numbers/symbols without context
```

---

## 🎯 Error Messages You Might See

| Error | Meaning | Solution |
|-------|---------|----------|
| **Message too short** | Message < 10 chars | Type at least 10 characters with antenna specs |
| **No response from server** | Server rejected as invalid | Be more specific: add frequency, bandwidth, or substrate |
| **Cannot connect to server** | Server not running at 192.168.234.89:8000 | Run health check: `python health_check.py` |

---

## 💡 Tips for Success

### **Do:**
- ✅ Specify a **frequency** (e.g., "2.4 GHz", "5 GHz", "900 MHz")
- ✅ Type **at least 10 characters** for the server to process
- ✅ Use **antenna-specific terms** (patch, microstrip, WiFi, etc.)
- ✅ Mention **substrate material** if you prefer one (FR-4, Rogers, etc.)
- ✅ Ask for **optimization criteria** (gain, efficiency, size, etc.)

### **Don't:**
- ❌ Send messages shorter than 10 characters
- ❌ Send random text unrelated to antennas
- ❌ Send incomplete specs like just "2.4" or "GHz"
- ❌ Expect exact designs without frequency info

---

## 📝 Recommended Starting Messages

Copy and paste one of these to start:

```
I need a 2.4 GHz patch antenna optimized for WiFi applications
```

```
Design a 5 GHz compact microstrip antenna with high gain
```

```
Create a 900 MHz antenna on FR-4 substrate with good bandwidth
```

```
I'm looking for a microstrip patch antenna at 2.4 GHz for IoT
```

```
Can you design a 5.8 GHz antenna with minimum 5 dBi gain?
```

---

## 🔧 Testing

To test the chat integration:

1. **Start the app:**
   ```powershell
   python main.py
   ```

2. **Try a valid message:**
   ```
   I need a 2.4 GHz patch antenna on FR-4 substrate
   ```

3. **Watch the chat:**
   - Message appears as "You (HH:MM:SS): [message]"
   - Loading indicator "⏳ Sending to server..." appears
   - Server response appears as "Assistant (HH:MM:SS): [response]"

4. **If you get an error,** check:
   - Message length (>= 10 chars)
   - Server running: `python health_check.py`
   - Network connection: `ping 192.168.234.89`

---

## 📊 Request Schema (For Reference)

The chat generates requests with:

| Field | Value | Example |
|-------|-------|---------|
| `schema_version` | `optimize_request.v1` | (server requirement) |
| `user_request` | Your message | "2.4 GHz patch antenna" |
| `frequency_ghz` | Extracted or default | 2.4 |
| `bandwidth_mhz` | Extracted or default | 200 |
| `antenna_family` | `microstrip_patch` | (default) |
| `materials` | `["Copper (annealed)"]` | (default) |
| `substrates` | `["FR-4 (lossy)"]` | (default) |

---

**Last Updated**: April 3, 2026  
**Server**: 192.168.234.89:8000  
**Validation**: Enabled
