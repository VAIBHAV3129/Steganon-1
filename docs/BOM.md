# Steganon-1 Bill of Materials (BOM)

| Category | Component Item | Qty | Specification  |
| -------- | -------------- | --- | -------------------------------- |
| **Compute** | Raspberry Pi Pico 2W (RP2350) | 2 | Dual-core ARM Cortex-M33; handles AES-256 and UI |
| **Radio** | Grove RFM95 LoRa Module | 2 | 865-867MHz (Configured for India ISM Band) |
| **Positioning** | SmartElex NEO-M9N GNSS | 2 | Concurrent 4 GNSS reception with SMA connector|
| **Display** | 1.3 inch I2C OLED Module | 2 | 128x64 Blue Monochrome status display |
| **Input** | 4x4 Matrix Keypad Module | 2 | 16-button interface for secure message entry |
| **Storage** | DFRobot MicroSD Card Module | 2 | SPI interface for local off-grid message logging |
| **Antenna** | 5dBi LoRa Magnetic Antenna | 2 | High-gain omnidirectional antenna |
| **RF Cable** | SMA to U.FL Cable (20cm) | 2 | Interfaces module U.FL to chassis SMA |
| **Power** | 18650 Li-Ion Battery | 4 | 3.7V 2900mAh power source |
| **Power** | TP4056 Charger Module | 2 | USB-C charging with over-discharge protection |
| **Power** | MT3608 Step-up Converter | 2 | Boosts battery to 5V for GPS/OLED rails |
| **Power** | AMS1117 3.3V Power Module | 2 | LDO regulation for RP2350 and LoRa logic |
| **Audio** | Active Buzzer Module | 2 | Audible alerts for transmission or low battery |

---

### System Integration Summary
* **Dual-Node Strategy**: This BOM provides full components for two complete nodes, enabling point-to-point (P2P) encrypted communication testing.
* **Power Rail Logic**: The **MT3608** provides a 5V rail for the GPS and OLED, while the **AMS1117** ensures a clean 3.3V supply for the RP2350 and LoRa module to prevent frequency drift.
* **Regulatory Compliance**: All radio hardware is selected to operate within the **865–867 MHz** license-free band in India.
