import math
import os
import pty
import select
import threading
import time
import unittest

import rclpy
from std_msgs.msg import Float64MultiArray
from navibot_motor_bridge.protocol import (
    Packet, Parser, encode, crc16, rpm_payload, feedback_payload,
    decode_feedback, SET_RPM, FEEDBACK,
)
from navibot_motor_bridge.bridge import MotorBridge
import struct


class ProtocolTests(unittest.TestCase):
    def test_crc_reference_and_signed_values(self):
        self.assertEqual(crc16(b'123456789'), 0x29B1)
        self.assertEqual(struct.unpack('<hh', rpm_payload(-12.3, 135)), (-12, 135))
        self.assertEqual(decode_feedback(feedback_payload(0, 0, -12, 4)),
                         (-12, 4, 0, 0))

    def test_parser_recovers_from_noise_corruption_and_split_frames(self):
        packet = Packet(1, SET_RPM, 255, rpm_payload(-10, 20))
        wire = encode(packet)
        bad = bytearray(wire)
        bad[-1] ^= 1
        parser = Parser()
        self.assertEqual(parser.feed(b'noise' + bad + wire[:1]), [])
        self.assertEqual(parser.feed(wire[1:5]), [])
        self.assertEqual(parser.feed(wire[5:] + wire), [packet, packet])
        self.assertEqual(parser.feed(b'\x5a\x5a\x01\x01\x01\x01\xff' + wire), [packet])


class BridgeIntegrationTests(unittest.TestCase):
    def test_two_nanos_targets_timeout_crc_and_feedback_loss(self):
        master, slave = pty.openpty()
        port = os.ttyname(slave)
        stopped = threading.Event()
        received = []
        suppress_rear = threading.Event()
        faults = []

        def nano_bus():
            parser = Parser()
            try:
                while not stopped.is_set():
                    if not select.select([master], [], [], 0.02)[0]:
                        continue
                    for packet in parser.feed(os.read(master, 1024)):
                        if packet.kind != SET_RPM:
                            continue
                        left, right = struct.unpack('<hh', packet.payload)
                        received.append((packet.address, left, right))
                        if packet.address == 2 and suppress_rear.is_set():
                            continue
                        payload = feedback_payload(0, 0, left, right)
                        # Wrong-sequence, bad-CRC and echo packets must not count as feedback.
                        wrong_payload = feedback_payload(0, 0, 99, 99)
                        wrong = encode(Packet(packet.address, FEEDBACK, (packet.sequence-1)&255, wrong_payload))
                        bad = bytearray(encode(Packet(packet.address, FEEDBACK, packet.sequence, wrong_payload)))
                        bad[-1] ^= 1
                        os.write(master, encode(packet) + wrong + bad)
                        reply = encode(Packet(packet.address, FEEDBACK, packet.sequence, payload))
                        os.write(master, reply[:4])
                        os.write(master, reply[4:])
            except Exception as exc:
                faults.append(exc)

        thread = threading.Thread(target=nano_bus)
        thread.start()
        rclpy.init(args=['--ros-args', '-p', f'port:={port}'])
        node = MotorBridge()
        sender = rclpy.create_node('bridge_test_sender')
        pub = sender.create_publisher(Float64MultiArray, '/motor_bridge/target_rpm', 1)

        def spin_for(seconds, target=None):
            end = time.monotonic()+seconds
            while time.monotonic()<end:
                if target is not None:
                    pub.publish(Float64MultiArray(data=target))
                rclpy.spin_once(node, timeout_sec=0.005)

        try:
            spin_for(0.4)
            spin_for(0.4, [10.0, -20.0, 30.0, -40.0])
            self.assertIn((1, 10, -20), received)
            self.assertIn((2, 30, -40), received)
            self.assertEqual(node.rpm, [10, -20, 30, -40])
            # At the configured 20 transactions/sec, wait past command expiry
            # and collect enough zero-target packets to assert the stop.
            spin_for(0.6)
            self.assertTrue(all(l == r == 0 for _, l, r in received[-4:]))
            spin_for(0.1, [float('nan'), 0.0, 0.0, 0.0])
            self.assertEqual(node.command_at, 0.0)
            suppress_rear.set()
            spin_for(0.5, [10.0]*4)
            self.assertTrue(all(l == r == 0 for _, l, r in received[-4:]))
            suppress_rear.clear()
            spin_for(0.15)
            self.assertTrue(all(l == r == 0 for _, l, r in received[-4:]))
            spin_for(0.15, [5.0]*4)
            self.assertTrue(any(l == r == 5 for _, l, r in received[-4:]))
            node.close()
            self.assertTrue(all(l == r == 0 for _, l, r in received[-2:]))
        finally:
            node.close()
            node.destroy_node()
            sender.destroy_node()
            rclpy.shutdown()
            stopped.set()
            thread.join(timeout=1)
            os.close(slave)
            os.close(master)
        self.assertFalse(faults)
