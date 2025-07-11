# joycontrol-gui

A powerful Python application that emulates Nintendo Switch controllers over Bluetooth, featuring a modern GUI interface and comprehensive amiibo support.

## Features

### 🎮 Controller Emulation
- Emulates a Nintendo Switch Pro Controller
- Real-time button press simulation
- Analog stick click (L3/R3) support

### 🎨 Modern GUI Interface
- Dark-themed, modern user interface built with PySide6
- Real-time connection status monitoring
- Auto-reconnection capabilities
- Visual button feedback

### 📱 NFC/Amiibo Support
- Full amiibo emulation functionality
- Load amiibo files (.bin format)
- Mutable amiibo support with automatic backup creation
- Tag UID management
- 540/572 byte amiibo file support

### 🔌 Connection Management
- Connect to previously paired Nintendo Switch consoles
- Fresh pairing mode for new connections
- Automatic device discovery
- Bluetooth MAC address management
- Device unpairing capabilities

### System Requirements
- Linux-based operating system (tested on Ubuntu/Debian)
- Python 3.7 or higher
- CSR-based USB Bluetooth dongle (recommended)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/EshayDev/joycontrol-gui.git
   cd joycontrol-gui
   ```

2. **Install Python dependencies:**
   ```bash
   sudo pip install PySide6 dbus-python aioconsole hid crc8 --break-system-packages
   ```

3. **Install system dependencies (Ubuntu/Debian):**
   ```bash
   sudo apt update
   sudo apt install python3-dbus libhidapi-hidraw0 libbluetooth-dev bluez
   ```

4. **Configure Bluetooth service for Nintendo Switch compatibility:**
   
   **⚠️ WARNING: This configuration will break other Bluetooth devices!**
   
   Edit the Bluetooth service configuration:
   ```bash
   sudo nano /lib/systemd/system/bluetooth.service
   ```
   
   Change the ExecStart line to:
   ```
   ExecStart=/usr/lib/bluetooth/bluetoothd -C -P sap,input,avrcp
   ```
   
   This removes additional features that interfere with Switch pairing but breaks other Bluetooth functionality.

5. **Restart Bluetooth service:**
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart bluetooth
   ```

## Usage

### GUI Application

Run the main GUI application:
```bash
sudo python3 main.py
```

**Note:** Root privileges are required for Bluetooth HID operations.

### Amiibo Usage

1. Load amiibo .bin files through the GUI
2. Files are automatically backed up when made mutable
3. Supports both 540-byte and 572-byte amiibo formats
4. Toggle amiibo on/off during gameplay

### Pairing Process
1. Put your Nintendo Switch in controller pairing mode (change grip/order menu)
2. Run the application with sudo privileges
3. Select "Start Fresh Pairing" or choose a previously paired device
4. Follow the on-screen prompts

**Important**: The modified Bluetooth service configuration will break other Bluetooth devices while active.