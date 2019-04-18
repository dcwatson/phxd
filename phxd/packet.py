from phxd.constants import DATA_ERROR, HTLS_HDR_TASK
from phxd.utils import decode_string

import collections
import struct


NUMBER_FORMATS = collections.OrderedDict((
    (16, '!H'),
    (32, '!L'),
    (64, '!Q'),
))


class HLObject:

    def __init__(self, kind, data):
        self.kind = kind
        self.data = data

    def __str__(self):
        return "HLObject [kind=%x,size=%d]" % (self.kind, len(self.data))

    def flatten(self):
        """ Returns a flattened, byte-swapped string for this hotline object. """
        return struct.pack("!2H", self.kind, len(self.data)) + self.data


class HLContainer:

    def __init__(self):
        self.objs = []

    def add(self, kind, data: bytes):
        self.objs.append(HLObject(kind, data))
        return self

    def add_string(self, kind, s):
        return self.add(kind, str(s).encode('utf-8', 'replace'))

    def add_number(self, kind, num, bits=None):
        """ Wraps a number in a HLObject, byte-swapping it based
        on its magnitude, and adds it. """
        num = int(num)
        if bits and bits in NUMBER_FORMATS:
            return self.add(kind, struct.pack(NUMBER_FORMATS[bits], num))
        else:
            for bits, fmt in NUMBER_FORMATS.items():
                if num < (1 << bits):
                    return self.add(kind, struct.pack(fmt, num))
        raise ValueError('Number too large.')

    def add_container(self, kind, cont):
        return self.add(kind, cont.flatten())

    def get(self, kind, default=None):
        for obj in self.objs:
            if obj.kind == kind:
                return obj
        return default

    def string(self, kind, default=None):
        """ Returns a string for the specified object kind, or
        a default value when the specified kind is not present. """
        obj = self.get(kind)
        return decode_string(obj.data) if obj else default

    def number(self, kind, default=None):
        """ Returns a byte-swapped number for the specified object kind, or
        a default value when the specified kind is not present. """
        obj = self.get(kind)
        if obj:
            bits = len(obj.data) * 8
            if bits in NUMBER_FORMATS:
                return struct.unpack(NUMBER_FORMATS[bits], obj.data)[0]
        return default

    def binary(self, kind, default=None):
        obj = self.get(kind)
        return obj.data if obj else default

    def objects(self, kind):
        return [obj for obj in self.objs if obj.kind == kind]

    def containers(self, kind):
        return [HLContainer().parse(obj.data) for obj in self.objects(kind)]

    def parse(self, data: bytes):
        if len(data) < 2:
            return self
        count = struct.unpack("!H", data[:2])[0]
        pos = 2
        while count > 0:
            (obj_kind, obj_size) = struct.unpack("!2H", data[pos:pos + 4])
            pos += 4
            self.add(obj_kind, data[pos:pos + obj_size])
            pos += obj_size
            count -= 1
        return self

    def flatten(self):
        return struct.pack("!H", len(self.objs)) + b''.join(obj.flatten() for obj in self.objs)


class HLPacket (HLContainer):

    def __init__(self, kind=0, seq=0, flags=0):
        super().__init__()
        self.kind = kind
        self.seq = seq
        self.flags = flags

    def __str__(self):
        s = "HLPacket [kind=%x,seq=%d,flags=%d]" % (self.kind, self.seq, self.flags)
        for obj in self.objs:
            s += "\n  " + str(obj)
        return s

    def parse(self, data: bytes):
        """ Tries to parse an entire packet from the data passed in. If successful,
        returns the number of bytes parsed, otherwise returns 0. """
        if len(data) < 20:
            return 0
        (self.kind, self.seq, self.flags, size, check) = struct.unpack("!5L", data[0:20])
        if (len(data) - 20) < size:
            return 0
        if size >= 2:
            super().parse(data[20:20 + size])
        return 20 + size

    def response(self):
        return HLPacket(HTLS_HDR_TASK, self.seq)

    def error(self, err):
        return HLPacket(HTLS_HDR_TASK, self.seq, 1).add_string(DATA_ERROR, err)

    def flatten(self):
        data = super().flatten()
        return struct.pack("!5L", self.kind, self.seq, self.flags, len(data), len(data)) + data
