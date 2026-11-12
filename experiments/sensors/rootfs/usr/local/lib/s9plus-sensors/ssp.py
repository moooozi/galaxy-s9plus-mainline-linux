#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Samsung SSP transport, adapted from ztOS sensors/zrn-ssp.py and sensord.

Only one command may await its echo. Transport packets and SSP messages can
both span reads. Unknown sensor sizes stop that frame rather than guessing.
"""
import os
import select
import struct
import time

# The owner's firmware uses signed 32-bit gyro axes, unlike its 16-bit accel.
SIZES = {0: 6, 1: 12, 9: 18}


class ProtocolError(RuntimeError):
    pass


def records(frame):
    at = 0
    while at < len(frame):
        tag = frame[at]
        at += 1
        if tag == 0x37:
            if at >= len(frame):
                raise ProtocolError('missing sensor id')
            sensor = frame[at]
            at += 1
            size = SIZES.get(sensor)
            if size is None:
                return
            if len(frame) - at < size + 8:
                raise ProtocolError('truncated sensor record')
            data = frame[at:at + size]
            if sensor == 9:
                values = (struct.unpack_from('<I', data)[0], 0, 0)
                if values[0] > 0x7fffffff:
                    raise ProtocolError('invalid illuminance')
            elif sensor == 1:
                values = struct.unpack('<iii', data)
            else:
                values = struct.unpack('<hhh', data)
            yield sensor, values
            at += size + 8
        elif tag == 0x03:
            if len(frame) - at < 2:
                raise ProtocolError('truncated debug length')
            size = struct.unpack_from('<H', frame, at)[0]
            at += 2
            if len(frame) - at < size:
                raise ProtocolError('truncated debug record')
            at += size
        elif tag == 0x05:
            if len(frame) - at < 2:
                raise ProtocolError('truncated metadata')
            at += 2
        elif tag == 0x0a:
            raise ProtocolError('hub restarted; firmware session must be restarted')
        elif tag != 0x06:
            return


class Hub:
    def __init__(self, fd, on_sample, writer=os.write):
        self.fd = fd
        self.on_sample = on_sample
        self.writer = writer
        self.raw = bytearray()
        self.stream = bytearray()
        self.index = 1
        self.pending = None
        self.reply = None

    def write(self, data):
        if self.writer(self.fd, data) != len(data):
            raise ProtocolError('short SSP write')

    def begin(self, command, payload=b'', read=0):
        if self.pending is not None:
            raise ProtocolError('overlapping SSP command')
        if read and payload:
            raise ValueError('read with payload')
        opts = (0 if read else 1) | (self.index << 3)
        self.index = self.index % 8000 + 1
        self.reply = None
        self.pending = (opts, read, payload)
        self.write(struct.pack('<BHHI', command, read or len(payload), opts, 0))
        if not read and not payload:
            self.pending = None
            self.reply = b''

    def feed(self, data):
        self.raw.extend(data)
        while len(self.raw) >= 2:
            size = struct.unpack_from('<H', self.raw)[0]
            if size > 8192:
                raise ProtocolError('oversized transport packet')
            if len(self.raw) < size + 2:
                break
            self.stream.extend(self.raw[2:size + 2])
            del self.raw[:size + 2]
            self.parse()
        if len(self.stream) > 8192:
            raise ProtocolError('oversized SSP stream')

    def parse(self):
        while len(self.stream) >= 4:
            opts, size = struct.unpack_from('<HH', self.stream)
            if opts & 3 == 2:
                if size > 8188:
                    raise ProtocolError('oversized hub frame')
                if len(self.stream) < size + 4:
                    return
                frame = bytes(self.stream[4:size + 4])
                del self.stream[:size + 4]
                for sensor, values in records(frame):
                    self.on_sample(sensor, values)
            elif self.pending and opts == self.pending[0]:
                _, read, payload = self.pending
                if read:
                    if size != read:
                        raise ProtocolError('read reply length mismatch')
                    if len(self.stream) < read + 4:
                        return
                    self.reply = bytes(self.stream[4:read + 4])
                    del self.stream[:read + 4]
                else:
                    if size != len(payload):
                        raise ProtocolError('write echo length mismatch')
                    self.write(payload)
                    self.reply = b''
                    del self.stream[:4]
                self.pending = None
            else:
                raise ProtocolError('unexpected transaction echo')

    def pump(self, timeout):
        if select.select([self.fd], [], [], timeout)[0]:
            data = os.read(self.fd, 8192)
            if not data:
                raise ProtocolError('hub transport closed')
            self.feed(data)

    def call(self, command, payload=b'', read=0, timeout=2):
        self.begin(command, payload, read)
        deadline = time.monotonic() + timeout
        while self.pending is not None:
            left = deadline - time.monotonic()
            if left <= 0:
                raise ProtocolError(f'no echo for command {command:#x}')
            self.pump(min(left, 0.2))
        return self.reply

    def timestamp(self):
        if self.pending is not None:
            raise ProtocolError('timestamp during transaction')
        ns = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        self.write(struct.pack('<BHHIq', 0xa7, 8, 1, 0, ns))
