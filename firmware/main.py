
import time
import json

class Logger:
    LEVELS = {"DEBUG": 10, "INFO": 20, "WARN": 30, "ERROR": 40}

    def __init__(self, level="INFO"):
        self._level = self.LEVELS.get(level, 20)

    def _log(self, lvl_name, msg):
        if self.LEVELS[lvl_name] < self._level:
            return
        ts = int(time.time())
        print("[{}][{}] {}".format(ts, lvl_name, msg))

    def debug(self, msg): self._log("DEBUG", msg)
    def info(self, msg):  self._log("INFO", msg)
    def warn(self, msg):  self._log("WARN", msg)
    def error(self, msg): self._log("ERROR", msg)


def crc32(data_bytes):
    """
    Software CRC32 (Ethernet/PKZIP poly 0xEDB88320).
    MicroPython friendly: avoids zlib.
    """
    if not isinstance(data_bytes, (bytes, bytearray)):
        raise TypeError("crc32 expects bytes")

    crc = 0xFFFFFFFF
    for b in data_bytes:
        crc ^= b
        for _ in range(8):
            mask = -(crc & 1)
            crc = (crc >> 1) ^ (0xEDB88320 & mask)
    return (~crc) & 0xFFFFFFFF


class RingBuffer:
    """
    Ring buffer for staging frames (bytes objects).
    Useful for decoupling pipeline from transport.
    """
    def __init__(self, capacity):
        self._cap = int(capacity)
        self._buf = [None] * self._cap
        self._head = 0
        self._tail = 0
        self._size = 0

    def push(self, item):
        if self._size == self._cap:
            raise OverflowError("RingBuffer full")
        self._buf[self._head] = item
        self._head = (self._head + 1) % self._cap
        self._size += 1

    def pop(self):
        if self._size == 0:
            return None
        item = self._buf[self._tail]
        self._buf[self._tail] = None
        self._tail = (self._tail + 1) % self._cap
        self._size -= 1
        return item

    def __len__(self):
        return self._size


# ============================================================
#                             CONFIGURATION 
# ============================================================

class Config:
    class DEVICE:
        FW_VERSION = "0.1.0-single"
        NODE_ID = "NODE-0001"
        NETWORK_ID = "STEGANON-1"

    class LORA:
        # India 865–867 MHz ISM band (commonly used). Tune per regulatory + module limits.
        FREQUENCY_HZ = 866_000_000

        TX_POWER_DBM = 17
        SPREADING_FACTOR = 7
        BANDWIDTH_HZ = 125_000
        CODING_RATE = "4/5"
        SYNC_WORD = 0x12

    
        LOOPBACK_RX = False           
        MAX_PAYLOAD_BYTES = 240       

    class CRYPTO:
       )
        AES256_KEY = "0123456789ABCDEF0123456789ABCDEF"  
        AES256_IV  = "ABCDEF0123456789"                  

    class PINS:
        # SPI placeholders (RFM95/SX127x)
        SPI_SCK = None
        SPI_MOSI = None
        SPI_MISO = None
        LORA_CS = None
        LORA_RESET = None
        LORA_DIO0 = None

        # UART placeholders (NEO-M9N)
        GPS_UART_TX = None
        GPS_UART_RX = None
        GPS_BAUD = 9600

        # I2C placeholders (future sensors/secure element/etc.)
        I2C_SCL = None
        I2C_SDA = None


# ============================================================
# 2) PACKET STRUCTURE
# ============================================================

class P2PPacket:
    """
    Structured packet model.

    Required fields:
      - Timestamp
      - GPS_Latitude
      - GPS_Longitude
      - Encrypted_Payload
      - Steganographic_Header

    Adds:
      - CRC32 over canonical JSON (integrity)
    """

    def __init__(self, timestamp, gps_lat, gps_lon, encrypted_payload_hex, stego_header):
        self.Timestamp = int(timestamp)
        self.GPS_Latitude = float(gps_lat)
        self.GPS_Longitude = float(gps_lon)
        self.Encrypted_Payload = str(encrypted_payload_hex)
        self.Steganographic_Header = dict(stego_header)
        self.CRC32 = None

    def to_dict(self, include_crc=True):
        d = {
            "Timestamp": self.Timestamp,
            "GPS_Latitude": self.GPS_Latitude,
            "GPS_Longitude": self.GPS_Longitude,
            "Encrypted_Payload": self.Encrypted_Payload,
            "Steganographic_Header": self.Steganographic_Header,
        }
        if include_crc:
            d["CRC32"] = self.CRC32
        return d

    def canonical_bytes_for_crc(self):
        
        body = self.to_dict(include_crc=False)
        s = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return s.encode("utf-8")

    def compute_crc(self):
        self.CRC32 = crc32(self.canonical_bytes_for_crc())
        return self.CRC32

    def to_json(self):
        if self.CRC32 is None:
            self.compute_crc()
        return json.dumps(self.to_dict(include_crc=True))



class MockAES256:
    """
    MOCK AES-256-like interface:
      encrypt_to_hex(plaintext: str) -> hex str
      decrypt_from_hex(cipher_hex: str) -> str

    This is a deterministic XOR+mask obfuscator for pipeline development.
    Replace with real AES-256 later without changing call sites.
    """

    def __init__(self, key, iv):
        self._key = str(key)
        self._iv = str(iv)

    def encrypt_to_hex(self, plaintext):
        if not isinstance(plaintext, str):
            raise TypeError("plaintext must be a string")

        material = (self._key + self._iv).encode("utf-8")
        pt = plaintext.encode("utf-8")

        out = bytearray()
        for i, b in enumerate(pt):
            out.append(b ^ material[i % len(material)] ^ ((i * 31) & 0xFF))

        return "".join("{:02x}".format(x) for x in out)

    def decrypt_from_hex(self, ciphertext_hex):
        if not isinstance(ciphertext_hex, str):
            raise TypeError("ciphertext_hex must be a string")
        if len(ciphertext_hex) % 2 != 0:
            raise ValueError("ciphertext_hex length must be even")

        material = (self._key + self._iv).encode("utf-8")
        ct = bytes(int(ciphertext_hex[i:i+2], 16) for i in range(0, len(ciphertext_hex), 2))

        out = bytearray()
        for i, b in enumerate(ct):
            out.append(b ^ material[i % len(material)] ^ ((i * 31) & 0xFF))

        return out.decode("utf-8", errors="replace")



def wrap_as_fake_sensor_heartbeat(node_id, fw_version, encrypted_hex, gps_lat, gps_lon, timestamp):
    """
    Wrap encrypted payload into a plausible JSON "sensor heartbeat".

    Hiding method:
      - encrypted hex stored in meta.calibration_blob (looks like calibration/log data)
      - header contains lightweight metadata + marker (for bring-up visibility)
    """
    stego_header = {
        "schema": "hb.v1",
        "node": node_id,
        "msg_type": "heartbeat",
        
        "steg": "S1",
        "ts": int(timestamp),
    }

    heartbeat = {
        "device": {
            "id": node_id,
            "fw": fw_version,
            "loc_hint": "field_unit",
        },
        "telemetry": {
            "temperature_c": 27.4,
            "soil_moisture_pct": 41.2,
            "battery_mv": 3940,
        },
        "gps": {
            "lat": round(float(gps_lat), 6),
            "lon": round(float(gps_lon), 6),
        },
        "meta": {
            # Hidden channel:
            "calibration_blob": encrypted_hex,
            "calibration_rev": 3,
        },
        "header": stego_header,
    }

    return stego_header, json.dumps(heartbeat)


def extract_hidden_payload_from_heartbeat(heartbeat_json):
    """
    Receive-side helper:
    - Parses the heartbeat JSON
    - Extracts meta.calibration_blob (encrypted hex)

    Returns: (node_id, encrypted_hex, parsed_dict)
    """
    obj = json.loads(heartbeat_json)
    node_id = obj.get("device", {}).get("id", "UNKNOWN")
    encrypted_hex = obj.get("meta", {}).get("calibration_blob", "")
    return node_id, encrypted_hex, obj


# ============================================================
# 5) HAL - Mock Drivers (RFM95 + NEO-M9N)
# ============================================================

class MockRFM95:
    """
    Mock LoRa (RFM95/SX127x family) radio HAL.

    Stable API:
      - init()
      - send(payload_bytes)
      - poll_receive() -> bytes|None

    For real driver later:
      - configure SPI
      - reset module
      - set frequency, SF, BW, CR, syncword
      - write FIFO, trigger TX, wait IRQ
      - for RX, check IRQ flags, read FIFO
    """

    def __init__(self, cfg_lora, pins, logger):
        self._cfg = cfg_lora
        self._pins = pins
        self._log = logger
        self._initialized = False
        self._rx = RingBuffer(capacity=8)

    def init(self):
        self._initialized = True
        self._log.info(
            "LoRa init (MOCK) OK: freq={}Hz txpwr={}dBm sf={} bw={}Hz cr={} sync=0x{:02x}".format(
                self._cfg.FREQUENCY_HZ,
                self._cfg.TX_POWER_DBM,
                self._cfg.SPREADING_FACTOR,
                self._cfg.BANDWIDTH_HZ,
                self._cfg.CODING_RATE,
                self._cfg.SYNC_WORD
            )
        )

    def send(self, payload_bytes):
        if not self._initialized:
            raise RuntimeError("LoRa not initialized")
        if not isinstance(payload_bytes, (bytes, bytearray)):
            raise TypeError("payload must be bytes")

        n = len(payload_bytes)
        if n > self._cfg.MAX_PAYLOAD_BYTES:
            self._log.warn("Payload size {} exceeds target {} bytes".format(n, self._cfg.MAX_PAYLOAD_BYTES))

        self._log.info("LoRa TX (MOCK) {} bytes".format(n))

        if getattr(self._cfg, "LOOPBACK_RX", False):
            try:
                self._rx.push(bytes(payload_bytes))
                self._log.debug("LoRa loopback queued RX frame")
            except OverflowError:
                self._log.warn("LoRa loopback RX queue full; dropping frame")

    def poll_receive(self):
        return self._rx.pop()

    def inject_rx(self, payload_bytes):
        """
        Test helper to simulate receiving a frame from the air.
        """
        self._rx.push(payload_bytes)


class MockNEOM9N:
    """
    Mock GPS HAL for u-blox NEO-M9N.

    Stable API:
      - init()
      - get_fix() -> (lat, lon)
    """

    def __init__(self, pins, logger):
        self._pins = pins
        self._log = logger
        self._initialized = False
        self._t = 0

    def init(self):
        self._initialized = True
        self._log.info("GPS init (MOCK) OK: uart_tx={} uart_rx={} baud={}".format(
            self._pins.GPS_UART_TX, self._pins.GPS_UART_RX, self._pins.GPS_BAUD
        ))

    def get_fix(self):
        if not self._initialized:
            raise RuntimeError("GPS not initialized")

        # Mock drift around Delhi. Replace with real NMEA/UBX parsing later.
        self._t += 1
        base_lat = 28.6139
        base_lon = 77.2090
        lat = base_lat + (self._t * 0.00001)
        lon = base_lon + (self._t * 0.00002)
        return lat, lon


# ============================================================
# 6) PIPELINE ORCHESTRATOR
# ============================================================

class SteganonPipeline:
    """
    Orchestrates:
      GPS -> Encrypt -> Stego wrap -> Structured packet -> TX

    Keeps business logic independent of hardware drivers.
    """

    def __init__(self, cfg, lora, gps, crypto, logger):
        self._cfg = cfg
        self._lora = lora
        self._gps = gps
        self._crypto = crypto
        self._log = logger

    def build_transmission(self, user_message):
        if not isinstance(user_message, str):
            raise TypeError("user_message must be a string")

        # Timestamp
        ts = int(time.time())

        # GPS fix
        lat, lon = self._gps.get_fix()

        # Encrypt user message to hex
        encrypted_hex = self._crypto.encrypt_to_hex(user_message)

        # Stego wrap into fake heartbeat
        stego_header, heartbeat_json = wrap_as_fake_sensor_heartbeat(
            node_id=self._cfg.DEVICE.NODE_ID,
            fw_version=self._cfg.DEVICE.FW_VERSION,
            encrypted_hex=encrypted_hex,
            gps_lat=lat,
            gps_lon=lon,
            timestamp=ts,
        )

        # Structured packet (for internal routing / alternate transports / storage)
        pkt = P2PPacket(
            timestamp=ts,
            gps_lat=lat,
            gps_lon=lon,
            encrypted_payload_hex=encrypted_hex,
            stego_header=stego_header,
        )
        pkt.compute_crc()

        return pkt, heartbeat_json

    def transmit(self, heartbeat_json):
        payload = heartbeat_json.encode("utf-8")
        self._lora.send(payload)

    def poll_rx_and_decode(self):
        """
        Non-blocking receive-side demo:
        - Gets a frame from radio (if any)
        - Extracts hidden encrypted hex
        - Decrypts (mock)
        """
        rx = self._lora.poll_receive()
        if rx is None:
            return None

        try:
            rx_text = rx.decode("utf-8", errors="replace")
            node_id, encrypted_hex, _parsed = extract_hidden_payload_from_heartbeat(rx_text)
            plaintext = self._crypto.decrypt_from_hex(encrypted_hex) if encrypted_hex else ""
            return {
                "from": node_id,
                "encrypted_hex": encrypted_hex,
                "decrypted_plaintext": plaintext,
                "raw": rx_text,
            }
        except Exception as e:
            self._log.warn("RX decode failed: {}".format(e))
            return {"raw_bytes": rx}


# ============================================================
# 7) MAIN LOOP (System Heartbeat)
# ============================================================

def main():
    log = Logger(level="DEBUG")

    # Instantiate HAL
    lora = MockRFM95(cfg_lora=Config.LORA, pins=Config.PINS, logger=log)
    gps = MockNEOM9N(pins=Config.PINS, logger=log)

    # Mock crypto engine
    crypto = MockAES256(key=Config.CRYPTO.AES256_KEY, iv=Config.CRYPTO.AES256_IV)

    # Initialize HAL
    lora.init()
    gps.init()

    # Pipeline
    pipeline = SteganonPipeline(cfg=Config, lora=lora, gps=gps, crypto=crypto, logger=log)

    # Demo settings
    user_message = "HELLO FROM STEGANON-1 (P2P TEST)"
    interval_s = 2

    log.info("Entering heartbeat loop. interval={}s loopback_rx={}".format(
        interval_s, Config.LORA.LOOPBACK_RX
    ))
    log.info("Press Ctrl+C to stop.")

    while True:
        pkt, heartbeat_json = pipeline.build_transmission(user_message)

        print("\n[Transmission Ready] Structured Packet JSON:")
        print(pkt.to_json())

        print("[Transmission Ready] Stego Heartbeat JSON:")
        print(heartbeat_json)

        pipeline.transmit(heartbeat_json)

        # Optional: if LOOPBACK_RX enabled, show receive/decode path
        rx_info = pipeline.poll_rx_and_decode()
        if rx_info:
            print("[RX] Decoded:")
            print(json.dumps(rx_info, indent=2))

        time.sleep(interval_s)

if __name__ == "__main__":
    main()
