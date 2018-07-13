from pydispatch import dispatcher
from twisted.internet import defer
from twisted.internet.protocol import ClientFactory

from phxd.client.signals import *
from phxd.constants import *
from phxd.packet import HLPacket
from phxd.protocol import HLProtocol
from phxd.utils import HLClientMagic, HLEncode


class HLClient (ClientFactory):

    protocol = HLProtocol

    def __init__(self):
        self.connection = None
        self.lastTaskID = 0
        self.tasks = {}
        self.seq_signals = {}
        self.type_signals = {
            HTLS_HDR_CHAT: chat_received,
            HTLS_HDR_MSG: message_received,
        }
        self._nickname = "unnamed"

    def _getNick(self):
        return self._nickname

    def _setNick(self, n):
        self._nickname = n
        if self.connection is not None:
            p = HLPacket(HTLC_HDR_USER_CHANGE)
            p.addString(DATA_NICK, self._nickname)
            self.sendPacket(p)

    nickname = property(_getNick, _setNick)

    # Notification methods called from HLProtocol

    def notifyConnect(self, conn):
        self.connection = conn
        conn.writeMagic(HLClientMagic())
        conn.waitForMagic(HTLS_MAGIC_LEN)

    def notifyMagic(self, conn, magic):
        dispatcher.send(signal=client_connected, sender=self, client=self)

    def notifyDisconnect(self, conn):
        dispatcher.send(signal=client_disconnected, sender=self, client=self)

    def notifyPacket(self, conn, packet):
        # First, send a generic signal that we got a packet
        dispatcher.send(signal=packet_received, sender=self, packet=packet, client=self)
        # Call back any task Deferreds created by calling our task methods (ex: sendLogin)
        if packet.seq in self.tasks:
            self.tasks[packet.seq].callback(packet)
            del self.tasks[packet.seq]
        # Fire off any signals passed into sendPacket for a given packet sequence
        if packet.seq in self.seq_signals:
            dispatcher.send(signal=self.seq_signals[packet.seq], sender=self, packet=packet, client=self)
            del self.seq_signals[packet.seq]
        # Finally, send out signals based on packet type, for packets not originating from a client task
        if packet.type in self.type_signals:
            dispatcher.send(signal=self.type_signals[packet.type], sender=self, packet=packet, client=self)

    # Task management

    def nextTaskID(self):
        self.lastTaskID += 1
        return self.lastTaskID

    def taskDeferred(self):
        self.tasks[self.lastTaskID] = defer.Deferred()
        return self.tasks[self.lastTaskID]

    # Basic hotline functionality

    def sendPacket(self, packet, signal=None):
        if self.connection is not None:
            if signal and (packet.seq > 0):
                self.seq_signals[packet.seq] = signal
            self.connection.writePacket(packet)

    def sendLogin(self, login, passwd):
        p = HLPacket(HTLC_HDR_LOGIN, self.nextTaskID())
        p.addBinary(DATA_LOGIN, HLEncode(login))
        p.addBinary(DATA_PASSWORD, HLEncode(passwd))
        p.addString(DATA_NICK, self.nickname)
        self.sendPacket(p, login_received)
        return self.taskDeferred()

    def sendChange(self, nick):
        p = HLPacket(HTLC_HDR_USER_CHANGE)
        p.addString(DATA_NICK, nick)
        self.sendPacket(p)

    def sendChat(self, chat):
        if chat:
            p = HLPacket(HTLC_HDR_CHAT)
            p.addString(DATA_STRING, chat)
            self.sendPacket(p)

    def sendIcon(self, icon):
        if icon:
            p = HLPacket(HTLC_HDR_ICON_SET)
            p.addBinary(DATA_GIFICON, icon)
            self.sendPacket(p)

    def sendMessage(self, msg, to):
        p = HLPacket(HTLC_HDR_MSG, self.nextTaskID())
        p.addString(DATA_STRING, msg)
        p.addNumber(DATA_UID, to)
        self.sendPacket(p)
        return self.taskDeferred()
