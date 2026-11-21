"""Version 1 addressed RS485 wheel-speed protocol; no ROS dependencies."""
import struct
from dataclasses import dataclass

SYNC = b'\x5a\x5a'
VERSION = 1
SET_RPM = 0x01
FEEDBACK = 0x81
ACK_STATUS = 0
NACK_STATUS = 1
MAX_PAYLOAD = 16


def crc16(data: bytes) -> int:
    """CRC-16/CCITT-FALSE as implemented by the Nano (init FFFF, poly 1021)."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


@dataclass(frozen=True)
class Packet:
    address: int
    kind: int
    sequence: int
    payload: bytes


def encode(packet: Packet) -> bytes:
    if len(packet.payload) > MAX_PAYLOAD:
        raise ValueError('payload too large')
    body = struct.pack('<5B', VERSION, packet.address, packet.kind,
                       packet.sequence, len(packet.payload)) + packet.payload
    return SYNC + body + struct.pack('<H', crc16(body))


class Parser:
    """Incremental parser: tolerates split reads, noise and corrupt packets."""
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[Packet]:
        self.buffer.extend(data)
        packets = []
        while True:
            start = self.buffer.find(SYNC)
            if start < 0:
                self.buffer[:] = b'\x5a' if self.buffer.endswith(b'\x5a') else b''
                break
            del self.buffer[:start]
            if len(self.buffer) < 7:
                break
            version, address, kind, sequence, length = self.buffer[2:7]
            if version != VERSION or length > MAX_PAYLOAD:
                del self.buffer[0]
                continue
            size = 9 + length
            if len(self.buffer) < size:
                break
            body = bytes(self.buffer[2:size - 2])
            expected, = struct.unpack('<H', self.buffer[size - 2:size])
            if crc16(body) != expected:
                del self.buffer[0]
                continue
            packets.append(Packet(address, kind, sequence, bytes(self.buffer[7:size - 2])))
            del self.buffer[:size]
        return packets


def rpm_payload(left: float, right: float) -> bytes:
    """Nano request payload uses signed whole RPM, not tenths of RPM."""
    return struct.pack('<hh', round(left), round(right))


def feedback_payload(status: int, reason: int, left: float, right: float) -> bytes:
    """Nano reply: status, reason, then signed whole-RPM measurements."""
    return struct.pack('<BBhh', status, reason, round(left), round(right))


def decode_feedback(payload: bytes):
    if len(payload) != 6:
        raise ValueError('reply must contain 6 bytes')
    status, reason, left, right = struct.unpack('<BBhh', payload)
    if status not in (0, 1):
        raise ValueError('invalid reply status')
    return left, right, status, reason
