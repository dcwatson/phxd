from phxd.utils import HLDecodeConst

from struct import unpack
import time


class HLTransfer:

    def __init__(self, id, file, incoming):
        self.id = id
        self.file = file
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

    def __init__(self, id, file, resume):
        HLTransfer.__init__(self, id, file, False)
        self.resume = resume
        self.total = self.file.streamSize(resume)
        self.stream = self.file.stream(resume, self.READ_SIZE)

    def overallPercent(self):
        # TODO: this doesn't take into account previous partial transfers
        if self.total > 0:
            return int((float(self.transferred) / float(self.total)) * 100)
        return 0

    def getDataChunk(self):
        """ Returns the next chunk of data to be sent out. """
        self.lastActivity = time.time()
        try:
            data = next(self.stream)
            self.transferred += len(data)
            return data
        except StopIteration:
            return b''

    def finish(self):
        """ Called when the download connection closes. """
        self.file.close()


STATE_FILP = 0
STATE_HEADER = 1
STATE_FORK = 2


class HLIncomingTransfer(HLTransfer):

    def __init__(self, id, file):
        HLTransfer.__init__(self, id, file, True)
        self.initialSize = self.file.size()
        self.buffer = b""
        self.state = STATE_FILP
        self.forkCount = 0
        self.currentFork = 0
        self.forkName = ''
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
                self.forkName = HLDecodeConst(self.currentFork)
                self.forkOffset = 0
                self.state = STATE_FORK
            elif self.state == STATE_FORK:
                remaining = self.forkSize - self.forkOffset
                if len(self.buffer) < remaining:
                    # We don't have the rest of the fork yet.
                    self.file.write(self.forkName, self.buffer)
                    self.forkOffset += len(self.buffer)
                    self.buffer = b""
                    return False
                else:
                    # We got the rest of the current fork.
                    self.file.write(self.forkName, self.buffer[0:remaining])
                    self.buffer = self.buffer[remaining:]
                    self.forkCount -= 1
                    if self.forkCount <= 0:
                        return True
                    self.state = STATE_HEADER

    def finish(self):
        """ Called when the upload connection closes. If the upload is complete, renames the file, stripping off the .hpf extension. """
        self.file.close()
