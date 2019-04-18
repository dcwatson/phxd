from phxd.constants import HTLC_MAGIC_LEN, HTLS_MAGIC_LEN
from phxd.packet import HLPacket
from phxd.utils import HLClientMagic, HLServerMagic

from struct import unpack
import asyncio
import logging


logger = logging.getLogger(__name__)


class HLProtocol (asyncio.Protocol):
    """
    Protocol subclass to handle parsing and dispatching of raw hotline packet data.
    """

    # Mostly for the server to associate a HLUser with this connection.
    user = None

    # Subclasses override these.
    magic = None
    expected_magic_length = None

    def __init__(self, server):
        self.server = server
        self.packet = HLPacket()
        self.got_magic = False
        self.buffered = b''
        self.transport = None
        self.address = None
        self.port = None

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.address, self.port = self.transport.get_extra_info('peername')
        self.server.notify_connect(self)
        self.transport.write(self.magic)

    def connection_lost(self, exc):
        self.server.notify_disconnect(self)

    def data_received(self, data: bytes):
        self.buffered += data
        self.parse_buffer()

    def parse_buffer(self):
        if self.got_magic:
            done = False
            while not done:
                size = self.packet.parse(self.buffered)
                if size > 0:
                    self.buffered = self.buffered[size:]
                    self.server.notify_packet(self, self.packet)
                    self.packet = HLPacket()
                else:
                    done = True
        else:
            if len(self.buffered) >= self.expected_magic_length:
                magic = self.buffered[:self.expected_magic_length]
                self.buffered = self.buffered[self.expected_magic_length:]
                self.got_magic = True
                self.server.notify_magic(self, magic)
                if len(self.buffered) > 0:
                    self.parse_buffer()

    def write_packet(self, packet):
        self.transport.write(packet.flatten())


class HLServerProtocol (HLProtocol):
    magic = HLServerMagic()
    expected_magic_length = HTLC_MAGIC_LEN


class HLClientProtocol (HLProtocol):
    magic = HLClientMagic()
    expected_magic_length = HTLS_MAGIC_LEN


class HLTransferProtocol (asyncio.Protocol):

    transfer = None

    def __init__(self, server):
        self.server = server
        self.got_magic = False
        self.buffered = b''
        self.transport = None
        self.address = None
        self.port = None
        self.paused = False

    def connection_made(self, transport: asyncio.Transport):
        self.transport = transport
        self.address, self.port = self.transport.get_extra_info('peername')
        self.server.transfer_connect(self)

    def connection_lost(self, exc):
        if self.transfer:
            self.transfer.finish()
        self.server.transfer_disconnect(self)

    def data_received(self, data: bytes):
        self.buffered += data
        self.parse_buffer()

    def start(self, transfer, send_magic=False):
        """ This should be called after magic has been received. transferInfo should be a HLTransfer instance. """
        logger.debug('Starting transfer %d: incoming=%d', transfer.id, transfer.incoming)
        self.transfer = transfer
        self.transfer.start()
        if self.transfer.incoming:
            self.server.loop.call_later(0.0, self.parse_buffer)
        else:
            self.resume_writing()

    def parse_buffer(self):
        if len(self.buffered) < 1:
            return
        if self.got_magic:
            if self.transfer and self.transfer.incoming:
                self.transfer.parse_data(self.buffered)
                self.buffered = b''
                if self.transfer.is_complete():
                    # The upload is done, it's our job to close the connection.
                    self.transport.close()
            else:
                logger.debug('Received %d non-magic download bytes', len(self.buffered))
                self.transport.close()
        else:
            # Make sure we buffer at this point in case we don't get the
            # HTXF magic all at once, or get more than just the magic.
            if len(self.buffered) >= 16:
                # We got the HTXF magic, parse it.
                proto, xfid, size, flags = unpack("!4L", self.buffered[0:16])
                self.buffered = self.buffered[16:]
                self.got_magic = True
                self.server.transfer_magic(self, xfid, size, flags)

    def write_loop(self):
        if self.transport.is_closing():
            return
        chunk = self.transfer.next_chunk()
        if len(chunk) > 0:
            self.transport.write(chunk)
            if not self.paused:
                self.server.loop.call_later(0.0, self.write_loop)

    def pause_writing(self):
        self.paused = True

    def resume_writing(self):
        self.paused = False
        self.server.loop.call_later(0.0, self.write_loop)
