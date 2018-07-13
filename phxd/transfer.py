from phxd.utils import HLCharConst

from struct import pack, unpack
import os
import time


class HLTransfer:

    def __init__(self, id, path, incoming):
        self.id = id
        self.path = path
        self.name = os.path.basename(path)
        self.total = 0
        self.transferred = 0
        self.offset = 0
        self.started = False
        self.startTime = 0.0
        self.lastActivity = time.time()
        self.incoming = incoming
        # this is really only useful for the server
        self.owner = 0

    def isIncoming(self):
        return self.incoming

    def overallPercent(self):
        return 0

    def getTotalBPS(self):
        """ Returns the overall speed (in BPS) of this transfer. """
        elapsed = time.time() - self.startTime
        if elapsed > 0.0:
            return int(float(self.transferred) / elapsed)
        return 0

    def isComplete(self):
        """ Returns True if all data has been sent or received. """
        return self.transferred >= self.total

    def parseData(self, data):
        """ Called when data is received from a transfer. """
        raise Exception("Transfer does not implement parseData.")

    def getDataChunk(self):
        """ Called when writing data to a transfer. """
        raise Exception("Transfer does not implement getDataChunk.")

    def start(self):
        """ Called when the connection is opened. """
        self.started = True
        self.startTime = time.time()

    def finish(self):
        """ Called when the connection is closed. """
        pass


class HLOutgoingTransfer(HLTransfer):

    READ_SIZE = 2 ** 14

    def __init__(self, id, path, offset=0):
        HLTransfer.__init__(self, id, path, False)
        self.offset = offset
        self.file = open(path, "rb")
        self.file.seek(offset)

        # calculate how much actual data is left to send, and
        # build the FILP header, INFO fork, and DATA header
        dataSize = os.path.getsize(path) - offset
        self.header = self._buildHeaderData(self.name, dataSize)
        self.total = len(self.header) + dataSize
        self.sentHeader = False

    def overallPercent(self):
        done = self.offset + self.transferred
        total = os.path.getsize(self.path) + len(self.header)
        if total > 0:
            return int((float(done) / float(total)) * 100)
        return 0

    def getDataChunk(self):
        """ Returns the next chunk of data to be sent out. """
        self.lastActivity = time.time()
        if self.sentHeader:
            # We already sent the header, read from the file.
            data = self.file.read(self.READ_SIZE)
            self.transferred += len(data)
            return data
        else:
            # Send the header, mark it as sent.
            self.sentHeader = True
            self.transferred += len(self.header)
            return self.header

    def finish(self):
        """ Called when the download connection closes. """
        self.file.close()

    def _buildHeaderData(self, name, size):
        """ Builds the header info for the file transfer, including the FILP header, INFO header and fork, and DATA header. """
        namedata = name.encode('utf-8')
        data = pack("!LHLLLLH", HLCharConst("FILP"), 1, 0, 0, 0, 0, 2)
        data += pack("!4L", HLCharConst("INFO"), 0, 0, 74 + len(name))
        data += pack("!5L", HLCharConst("AMAC"), HLCharConst("????"), HLCharConst("????"), 0, 0)
        data += bytes(32)
        data += pack("!HHL", 0, 0, 0)
        data += pack("!HHL", 0, 0, 0)
        data += pack("!HH", 0, len(namedata))
        data += namedata
        data += pack("!H", 0)
        data += pack("!4L", HLCharConst("DATA"), 0, 0, size)
        return data


STATE_FILP = 0
STATE_HEADER = 1
STATE_FORK = 2


class HLIncomingTransfer(HLTransfer):

    def __init__(self, id, path):
        HLTransfer.__init__(self, id, path, True)
        self.file = open(path, "ab")
        self.initialSize = os.path.getsize(path)
        self.buffer = b""
        self.state = STATE_FILP
        self.forkCount = 0
        self.currentFork = 0
        self.forkSize = 0
        self.forkOffset = 0

    def overallPercent(self):
        done = self.initialSize + self.transferred
        total = self.initialSize + self.total
        if total > 0:
            return int((float(done) / float(total)) * 100)
        return 0

    def parseData(self, data):
        """ Called when data is received from the upload connection. Writes any data received for the DATA fork out to the specified file. """
        self.buffer += data
        self.transferred += len(data)
        self.lastActivity = time.time()
        while True:
            if self.state == STATE_FILP:
                if len(self.buffer) < 24:
                    return False
                (proto, vers, _r1, _r2, _r3, _r4, self.forkCount) = unpack("!LHLLLLH", self.buffer[0:24])
                self.buffer = self.buffer[24:]
                self.state = STATE_HEADER
            elif self.state == STATE_HEADER:
                if len(self.buffer) < 16:
                    return False
                (self.currentFork, _r1, _r2, self.forkSize) = unpack("!4L", self.buffer[0:16])
                self.buffer = self.buffer[16:]
                self.forkOffset = 0
                self.state = STATE_FORK
            elif self.state == STATE_FORK:
                remaining = self.forkSize - self.forkOffset
                if len(self.buffer) < remaining:
                    # We don't have the rest of the fork yet.
                    if self.currentFork == HLCharConst("DATA"):
                        # Write to the file if this is the DATA fork.
                        self.file.write(self.buffer)
                    self.forkOffset += len(self.buffer)
                    self.buffer = b""
                    return False
                else:
                    # We got the rest of the current fork.
                    if self.currentFork == HLCharConst("DATA"):
                        self.file.write(self.buffer[0:remaining])
                    self.buffer = self.buffer[remaining:]
                    self.forkCount -= 1
                    if self.forkCount <= 0:
                        return True
                    self.state = STATE_HEADER

    def finish(self):
        """ Called when the upload connection closes. If the upload is complete, renames the file, stripping off the .hpf extension. """
        self.file.close()
