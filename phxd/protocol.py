from twisted.internet import reactor
from twisted.internet.interfaces import IProducer
from twisted.internet.protocol import Protocol
from zope.interface import implementer

from phxd.packet import HLPacket

from struct import unpack


class HLProtocol(Protocol):
    """ Protocol subclass to handle parsing and dispatching of raw hotline data. """

    context = None
    timer = None

    def __init__(self):
        self.packet = HLPacket()
        self.gotMagic = False
        self.expectedMagicLen = 0
        self.buffered = b""

    def connectionMade(self):
        """ Called when a connection is accepted. """
        self.factory.notifyConnect(self)

    def connectionLost(self, reason):
        """ Called when the connection is lost. """
        self.factory.notifyDisconnect(self)

    def dataReceived(self, data):
        """ Called when the socket receives data. """
        self.buffered += data
        self.parseBuffer()

    def parseBuffer(self):
        """ Parses the current buffer until the buffer is empty or until no more packets can be parsed. """
        if self.gotMagic:
            done = False
            while not done:
                size = self.packet.parse(self.buffered)
                if size > 0:
                    self.buffered = self.buffered[size:]
                    self.factory.notifyPacket(self, self.packet)
                    self.packet = HLPacket()
                else:
                    done = True
        else:
            if len(self.buffered) >= self.expectedMagicLen:
                magic = self.buffered[0:self.expectedMagicLen]
                self.buffered = self.buffered[self.expectedMagicLen:]
                self.gotMagic = True
                self.factory.notifyMagic(self, magic)
                if len(self.buffered) > 0:
                    self.parseBuffer()

    def waitForMagic(self, magicLen):
        self.expectedMagicLen = magicLen

    def writeMagic(self, magic):
        self.transport.write(magic)

    def writePacket(self, packet):
        """ Flattens and writes a packet out to the socket. """
        self.transport.write(packet.flatten())


@implementer(IProducer)
class HLTransferProtocol(Protocol):

    info = None
    gotMagic = False
    buffered = b""

    def connectionMade(self):
        self.factory.notifyConnect(self)

    def connectionLost(self, reason):
        if self.info:
            self.info.finish()
        self.factory.notifyDisconnect(self)

    def start(self, transferInfo, sendMagic=False):
        """ This should be called after magic has been received. transferInfo should be a HLTransfer instance. """
        self.info = transferInfo
        if not self.info.isIncoming():
            self.transport.registerProducer(self, False)
        self.info.start()
        reactor.callLater(0, self.parseBuffer)

    def parseBuffer(self):
        if len(self.buffered) < 1:
            return
        if self.gotMagic:
            if self.info and self.info.isIncoming():
                self.info.parseData(self.buffered)
                self.buffered = b""
                if self.info.isComplete():
                    # The upload is done, it's our job to close the connection.
                    self.transport.loseConnection()
            else:
                self.transport.loseConnection()
        else:
            # Make sure we buffer at this point in case we don't get the
            # HTXF magic all at once, or get more than just the magic.
            if len(self.buffered) >= 16:
                # We got the HTXF magic, parse it.
                (proto, xfid, size, flags) = unpack("!4L", self.buffered[0:16])
                self.buffered = self.buffered[16:]
                self.gotMagic = True
                self.factory.notifyMagic(self, xfid, size, flags)

    def dataReceived(self, data):
        self.buffered += data
        self.parseBuffer()

    def resumeProducing(self):
        """ The transport asked us for more data. Should only happen for downloads after we've been registered as a producer. """
        chunk = self.info.getDataChunk()
        if len(chunk) > 0:
            self.transport.write(chunk)
        else:
            self.transport.unregisterProducer()

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass
