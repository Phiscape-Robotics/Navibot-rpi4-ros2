"""Pi bus master for two independent two-wheel Nano speed controllers."""
import math
import time

import rclpy
from rclpy.node import Node
import serial
from std_msgs.msg import Float64MultiArray, String

from .protocol import Packet, Parser, SET_RPM, FEEDBACK, encode, rpm_payload, decode_feedback


class MotorBridge(Node):
    def __init__(self):
        super().__init__('motor_bridge')
        defaults = {
            'port': '/dev/ttyUSB0', 'baudrate': 115200,
            'front_address': 1, 'rear_address': 2,
            'poll_rate': 50.0, 'reply_timeout': 0.012,
            'command_timeout': 0.25, 'feedback_timeout': 0.25,
            'max_rpm': 135.0,
        }
        for key, value in defaults.items():
            self.declare_parameter(key, value)
        self.cfg = {key: self.get_parameter(key).value for key in defaults}
        self.addresses = [self.cfg['front_address'], self.cfg['rear_address']]
        if (len(set(self.addresses)) != 2 or
                any(not 1 <= a <= 247 for a in self.addresses)):
            raise ValueError('Nano addresses must be distinct, between 1 and 247')
        for key in ('poll_rate', 'reply_timeout', 'command_timeout',
                    'feedback_timeout', 'max_rpm'):
            if not math.isfinite(self.cfg[key]) or self.cfg[key] <= 0:
                raise ValueError(f'{key} must be finite and positive')
        if self.cfg['max_rpm'] > 3276.7:
            raise ValueError('max_rpm exceeds protocol range')
        if self.cfg['reply_timeout'] >= 1 / self.cfg['poll_rate']:
            raise ValueError('reply_timeout must be shorter than poll interval')
        self.bus = None
        self.next_connect = 0.0
        self.targets = [0.0] * 4
        self.command_at = 0.0
        self.sequence = 0
        self.index = 0
        self.rpm = [float('nan')] * 4
        self.duty = [float('nan')] * 4
        self.feedback_at = [0.0, 0.0]
        self.status = [0, 0]
        self.sample_ms = [0, 0]
        self.rpm_pub = self.create_publisher(Float64MultiArray, '~/wheel_rpm', 10)
        self.duty_pub = self.create_publisher(Float64MultiArray, '~/wheel_duty', 10)
        self.status_pub = self.create_publisher(String, '~/status', 10)
        self.create_subscription(Float64MultiArray, '~/target_rpm', self.on_target, 1)
        self.create_timer(1 / self.cfg['poll_rate'], self.poll)
        self.create_timer(0.2, self.publish_feedback)
        self.get_logger().info('Wheel order: front_left, front_right, rear_left, rear_right')

    def on_target(self, msg):
        values = list(msg.data)
        if (len(values) != 4 or
                any(not math.isfinite(v) or abs(v) > self.cfg['max_rpm'] for v in values)):
            self.targets = [0.0] * 4
            self.command_at = 0.0
            self.get_logger().error(
                'Rejected RPM command: need four finite values within max_rpm',
                throttle_duration_sec=1.0)
            return
        # Ignore queued commands while disconnected; require a fresh command after reconnect.
        if self.bus is not None:
            self.targets = values
            self.command_at = time.monotonic()

    def connect(self):
        now = time.monotonic()
        if now < self.next_connect:
            return False
        self.next_connect = now + 2.0
        try:
            self.bus = serial.Serial(self.cfg['port'], self.cfg['baudrate'],
                                     timeout=0, write_timeout=0.02, exclusive=True)
            self.targets = [0.0] * 4
            self.command_at = 0.0
            self.feedback_at = [0.0, 0.0]
            self.get_logger().info(f"Opened {self.cfg['port']}; awaiting fresh RPM commands")
            return True
        except (serial.SerialException, OSError) as exc:
            self.bus = None
            self.get_logger().warning(f'Serial connection unavailable: {exc}')
            return False

    def exchange(self, index, left, right):
        address = self.addresses[index]
        self.sequence = (self.sequence + 1) & 255
        sequence = self.sequence
        self.bus.reset_input_buffer()
        self.bus.write(encode(Packet(address, SET_RPM, sequence, rpm_payload(left, right))))
        parser = Parser()
        deadline = time.monotonic() + self.cfg['reply_timeout']
        while time.monotonic() < deadline:
            data = self.bus.read(256)
            if not data:
                time.sleep(0.0005)
                continue
            for packet in parser.feed(data):
                if (packet.address != address or packet.kind != FEEDBACK or
                        packet.sequence != sequence):
                    continue
                try:
                    return decode_feedback(packet.payload)
                except ValueError:
                    continue
        return None

    def poll(self):
        if self.bus is None and not self.connect():
            return
        index = self.index
        self.index = 1 - self.index
        now = time.monotonic()
        # Loss of either controller inhibits motion on all four wheels.
        healthy = all(t and now - t <= self.cfg['feedback_timeout']
                      for t in self.feedback_at) and not any(s & 0x0006 for s in self.status)
        valid = self.command_at and now - self.command_at <= self.cfg['command_timeout']
        if not healthy:
            self.command_at = 0.0
        targets = self.targets if healthy and valid else [0.0] * 4
        try:
            reply = self.exchange(index, *targets[2 * index:2 * index + 2])
            if reply is not None:
                left, right, dl, dr, sample, status = reply
                self.rpm[2 * index:2 * index + 2] = [left, right]
                self.duty[2 * index:2 * index + 2] = [dl / 10.0, dr / 10.0]
                self.feedback_at[index] = time.monotonic()
                self.sample_ms[index] = sample
                self.status[index] = status
        except (serial.SerialException, OSError) as exc:
            self.get_logger().error(f'Serial failure: {exc}')
            self.bus.close()
            self.bus = None
            self.command_at = 0.0

    def publish_feedback(self):
        now = time.monotonic()
        rpm, duty = list(self.rpm), list(self.duty)
        states = []
        for i in range(2):
            fresh = bool(self.feedback_at[i] and
                         now - self.feedback_at[i] <= self.cfg['feedback_timeout'])
            if not fresh:
                rpm[2*i:2*i+2] = [float('nan')] * 2
                duty[2*i:2*i+2] = [float('nan')] * 2
            states.append(f'{self.addresses[i]}:fresh={fresh},flags={self.status[i]},'
                          f'sample_ms={self.sample_ms[i]}')
        self.rpm_pub.publish(Float64MultiArray(data=rpm))
        self.duty_pub.publish(Float64MultiArray(data=duty))
        self.status_pub.publish(String(data='; '.join(states)))

    def close(self):
        if self.bus is not None:
            try:
                for i in range(2):
                    self.exchange(i, 0.0, 0.0)
            except (serial.SerialException, OSError):
                pass
            finally:
                self.bus.close()
                self.bus = None


def main(args=None):
    rclpy.init(args=args)
    node = None
    try:
        node = MotorBridge()
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        if node is not None:
            node.close()
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
