"""Version 1 addressed RS485 wheel-speed protocol; no ROS dependencies."""
import struct
from dataclasses import dataclass

SYNC = b'\xaa\x55'
VERSION = 1
SET_RPM = 0x01
FEEDBACK = 0x81
MAX_PAYLOAD = 16


def crc16(data: bytes) -> int:
    """CRC-16/MODBUS: init FFFF, reflected polynomial A001, no final XOR."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
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
                self.buffer[:] = b'\xaa' if self.buffer.endswith(b'\xaa') else b''
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
    return struct.pack('<hh', round(left * 10), round(right * 10))


def feedback_payload(left: float, right: float, left_duty: int,
                     right_duty: int, sample_ms: int, status: int) -> bytes:
    return struct.pack('<hhhhIH', round(left * 10), round(right * 10),
                       left_duty, right_duty, sample_ms, status)


def decode_feedback(payload: bytes):
    if len(payload) != 14:
        raise ValueError('feedback must contain 14 bytes')
    left, right, dl, dr, sample, status = struct.unpack('<hhhhIH', payload)
    if abs(dl) > 1000 or abs(dr) > 1000:
        raise ValueError('invalid feedback duty')
    return left / 10, right / 10, dl, dr, sample, status
