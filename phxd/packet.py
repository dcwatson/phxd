from phxd.constants import *
from phxd.utils import decodeString

from struct import *


class HLObject:
    def __init__(self, type, data):
        self.type = type
        self.data = data

    def __str__(self):
        return "HLObject [type=%x,size=%d]" % (self.type, len(self.data))

    def flatten(self):
        """ Returns a flattened, byte-swapped string for this hotline object. """
        return pack("!2H", self.type, len(self.data)) + self.data


class HLContainer:

    def __init__(self):
        self.objs = []

    def addObject(self, obj):
        """ Adds a HLObject to the object list. """
        self.objs.append(obj)

    def addString(self, type, data):
        """ Wraps a string in a HLObject and adds it. """
        if isinstance(data, str):
            self.addObject(HLObject(type, data.encode('utf-8', 'replace')))
        else:
            self.addObject(HLObject(type, data))

    def addNumber(self, type, data):
        """ Wraps a number in a HLObject, byte-swapping it based
        on its magnitude, and adds it. """
        num = int(data)
        packed = ""
        if num < (1 << 16):
            packed = pack("!H", num)
        elif num < (1 << 32):
            packed = pack("!L", num)
        elif num < (1 << 64):
            packed = pack("!Q", num)
        obj = HLObject(type, packed)
        self.addObject(obj)

    def addInt16(self, type, data):
        """ Adds a 16-bit byte-swapped number as a HLObject. """
        num = int(data)
        obj = HLObject(type, pack("!H", num))
        self.addObject(obj)

    def addInt32(self, type, data):
        """ Adds a 32-bit byte-swapped number as a HLObject. """
        num = int(data)
        obj = HLObject(type, pack("!L", num))
        self.addObject(obj)

    def addInt64(self, type, data):
        """ Adds a 64-bit byte-swapped number as a HLObject. """
        num = int(data)
        obj = HLObject(type, pack("!Q", num))
        self.addObject(obj)

    def addBinary(self, type, data):
        obj = HLObject(type, data)
        self.addObject(obj)

    def addContainer(self, type, cont):
        obj = HLObject(type, cont.flatten())
        self.addObject(obj)

    def getObject(self, type):
        for obj in self.objs:
            if obj.type == type:
                return obj
        return None

    def removeObject(self, type):
        obj = self.getObject(type)
        if obj is not None:
            self.objs.remove(obj)

    def getString(self, type, default=None):
        """ Returns a string for the specified object type, or
        a default value when the specified type is not present. """
        for obj in self.objs:
            if (obj.type == type) and (len(obj.data) > 0):
                return decodeString(obj.data)
        return default

    def getNumber(self, type, default=None):
        """ Returns a byte-swapped number for the specified object type, or
        a default value when the specified type is not present. """
        for obj in self.objs:
            if obj.type == type:
                if len(obj.data) == 2:
                    return unpack("!H", obj.data)[0]
                elif len(obj.data) == 4:
                    return unpack("!L", obj.data)[0]
                elif len(obj.data) == 8:
                    return unpack("!Q", obj.data)[0]
        return default

    def getBinary(self, type, default=None):
        for obj in self.objs:
            if (obj.type == type) and (len(obj.data) > 0):
                return obj.data
        return default

    def getContainer(self, type):
        for obj in self.objs:
            if obj.type == type:
                cont = HLContainer()
                cont.parse(obj.data)
                return cont
        return None

    def getContainers(self, type):
        ret = []
        for obj in self.objs:
            if obj.type == type:
                cont = HLContainer()
                cont.parse(obj.data)
                ret.append(cont)
        return ret

    def getObjects(self, type):
        objs = []
        for obj in self.objs:
            if obj.type == type:
                objs.append(obj)
        return objs

    def parse(self, data):
        if len(data) < 2:
            return
        count = unpack("!H", data[0:2])[0]
        pos = 2
        while count > 0:
            (obj_type, obj_size) = unpack("!2H", data[pos:pos + 4])
            pos += 4
            obj = HLObject(obj_type, data[pos:pos + obj_size])
            self.addObject(obj)
            pos += obj_size
            count -= 1

    def flatten(self):
        data = b""
        for obj in self.objs:
            data += obj.flatten()
        return pack("!H", len(self.objs)) + data


class HLPacket (HLContainer):
    def __init__(self, type=0, seq=0, flags=0):
        HLContainer.__init__(self)
        self.type = type
        self.seq = seq
        self.flags = flags

    def __str__(self):
        s = "HLPacket [type=%x,seq=%d,flags=%d]" % (self.type, self.seq, self.flags)
        for obj in self.objs:
            s += "\n  " + str(obj)
        return s

    def parse(self, data):
        """ Tries to parse an entire packet from the data passed in. If successful,
        returns the number of bytes parsed, otherwise returns 0. """
        if len(data) < 20:
            return 0
        (self.type, self.seq, self.flags, size, check) = unpack("!5L", data[0:20])
        if (len(data) - 20) < size:
            return 0
        if size >= 2:
            HLContainer.parse(self, data[20:20 + size])
        return 20 + size

    def response(self):
        return HLPacket(HTLS_HDR_TASK, self.seq)

    def error(self, err):
        p = HLPacket(HTLS_HDR_TASK, self.seq, 1)
        p.addString(DATA_ERROR, str(err))
        return p

    def flatten(self):
        data = HLContainer.flatten(self)
        return pack("!5L", self.type, self.seq, self.flags, len(data), len(data)) + data
