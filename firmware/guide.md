## The Steganon-1 Data Path:

- Input: User types a message on the UI (OLED/Buttons).

- Processing: RP2350 fetches GPS coordinates from the NEO-M9N.

- Encryption: RP2350 wraps the message and GPS data in an encrypted packet.

- Output: The RFM95 broadcasts the packet over LoRa frequencies.
