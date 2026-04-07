# Modern UI Quick Reference

## 🚀 Quick Start

```bash
# Run the new modern UI
python ui/main_qml_app.py

# Keep using the old UI (unchanged)
python main.py
```

---

## 🎨 What Changed

### Before (Old Design)
```
┌─ Flat gray layout
├─ Dated appearance
├─ Dense, crowded
└─ Limited visual hierarchy
```

### After (New Design)
```
┌─ Dark theme with blue accents
├─ Professional, modern look
├─ Well-organized with breathing room
├─ Clear visual hierarchy
├─ Smooth animations & interactions
└─ Premium appearance
```

---

## 📍 Layout Overview

```
╔════════════════════════════════════════════╗
║   🎯 Antenna Design Studio  [●●● • Status]║  ← Top Bar
╠════════════┬──────────────────┬───────────╣
║   LEFT     │    MIDDLE        │   RIGHT   ║
║ (420px)    │    CHAT          │  (380px)  ║
║            │    (elastic)     │           ║
║ • Modes    │ ┌──────────────┐ │ Results   │
║ • Antenna  │ │ Chat msgs    │ │ • Freq    │
║ • Materials│ │              │ │ • BW      │
║ • Dims     │ │ User msg >>  │ │ • Gain    │
║ • Specs    │ │ << AI resp   │ │ • VSWR    │
║ • Buttons  │ └──────────────┘ │ • Export  │
║            │ Input field ⌘    │           ║
╚════════════╩──────────────────╩───────════╝
```

---

## 🎨 Color Palette

| Color | Hex | Usage |
|-------|-----|-------|
| Primary Blue | `#3b82f6` | Buttons, user messages |
| Cyan | `#06b6d4` | Hover states, accents |
| Green | `#22c55e` | Success indicators |
| Orange | `#f59e0b` | Warnings/alerts |
| Dark Navy | `#0f172a` | Main background |
| Slate | `#1e293b` | Surface areas |
| Light Slate | `#334155` | Cards, inputs |
| Border | `#475569` | Subtle dividers |

---

## 🎯 Key UI Elements

### Chat Modes
- **⚡ Speed Mode** - Uses fast intent-parse (1.2s avg)
- **💎 Quality Mode** - Uses rich chat model (36s avg)

### Status Indicators
- 🟢 CST - Connected
- 🟢 API - Connected
- 🟠 Server - Warning/Offline

### Antenna Types
- 📡 Patch (default)
- 📌 Dipole
- 🎯 Monopole
- 📢 Horn
- 🌀 Helical

### Result Metrics
- 📡 Frequency (GHz)
- 📈 Bandwidth (MHz)
- 📶 Gain (dB)
- ✓ VSWR (ratio)

---

## ⚙️ Files

| File | Purpose |
|------|---------|
| `ui/main_modern.qml` | 🎨 Modern UI definition |
| `ui/main_qml_app.py` | 🔗 Python ↔ QML bridge |
| `MODERN_UI_REDESIGN.md` | 📖 Full documentation |

---

## 💻 Running

```bash
# Modern QML version
cd e:/antenna_client
python ui/main_qml_app.py

# Classic widget version (still works)
python main.py
```

---

## ✨ Modern Features

✓ Dark theme (professional)  
✓ Smooth animations  
✓ Hover effects on buttons  
✓ Pulsing status indicators  
✓ Card-based layout  
✓ Emoji icons for quick ID  
✓ Chat bubbles (dual-sided)  
✓ Time metadata on messages  
✓ Color-coded indicators  
✓ Responsive panels  

---

## 🔧 Customize

### Change Primary Color
Edit `ui/main_modern.qml` line 18:
```qml
readonly property color primaryColor: "#3b82f6"  // Your color here
```

### Add New Metrics
Edit the Repeater in results panel:
```qml
model: [
    { label: "Your Metric", value: "X.XX", icon: "📊" },
    // ...
]
```

### Adjust Panel Widths
```qml
Layout.preferredWidth: 420  // Left panel (default)
Layout.preferredWidth: 380  // Right panel (default)
```

---

## 🎬 What Happens When You...

| Action | Result |
|--------|--------|
| Hover button | Smooth color transition |
| Send chat | Message appears on right in blue |
| AI responds | Message on left in gray |
| Status changes | Indicator color updates |
| Select Speed mode | Quick responses mode active |
| Select Quality mode | Rich responses mode active |

---

## 📊 Performance

- **Rendering:** Efficient QML layout engine
- **Memory:** Lightweight compared to web-based UIs
- **Startup:** ~2-3 seconds (QML compilation)
- **Responsiveness:** Instant (GPU-accelerated)

---

## 🆘 Troubleshooting

**"QML not found"**
```bash
pip install PySide6
```

**"Import errors in bridge"**
```bash
# Check your Python path includes antenna_client
python -c "import comm.api_client; print('OK')"
```

**"Want to go back to old UI"**
```bash
python main.py  # Original widget UI still works
```

---

Ready to use! Run `python ui/main_qml_app.py` and enjoy your modern UI. 🚀
