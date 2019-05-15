from pydispatch import dispatcher
from twisted.internet import reactor, ssl, task
from twisted.internet.protocol import Factory

from phxd import tracker
from phxd.constants import *
from phxd.packet import HLPacket
from phxd.protocol import HLProtocol
from phxd.server import database
from phxd.server.config import conf
from phxd.server.files import HLFileServer
from phxd.server.signals import *
from phxd.types import *
from phxd.utils import HLCharConst, HLServerMagic

from struct import unpack
import hashlib
import logging
import time


class HLServer(Factory):
    """ Factory subclass that handles all global server operations. Also owns database and fileserver objects. """

    protocol = HLProtocol

    def __init__(self):
        self.lastUID = 0
        self.lastChatID = 0
        self.connections = []
        self.chats = {}
        self.defaultIcon = ""
        self.tempBans = {}
        self.startTime = None
        self.database = database.instance(conf.DB_TYPE, conf.DB_ARG)
        self.fileserver = HLFileServer(self)
        self._listeners = []
        self._tickle = task.LoopingCall(self.checkUsers)
        self._pinger = task.LoopingCall(self.pingTracker)

    def _getUserlist(self):
        return [c.context for c in self.connections if c.context.valid]
    userlist = property(_getUserlist)

    def start(self):
        if not self.database.isConfigured():
            logging.info("[server] configuring database")
            self.database.setup()
            logging.info("[server] creating admin user")
            admin = HLAccount("admin")
            admin.name = "Administrator"
            admin.privs = 18443313597422501888
            admin.password = hashlib.md5(b"adminpass").hexdigest()
            self.database.saveAccount(admin)
        for port in conf.SERVER_PORTS:
            self._listeners.append(reactor.listenTCP(port, self))
            self._listeners.append(reactor.listenTCP(port + 1, self.fileserver))
        if conf.ENABLE_SSL:
            sslContext = ssl.DefaultOpenSSLContextFactory(conf.SSL_KEY_FILE, conf.SSL_CERT_FILE)
            self._listeners.append(reactor.listenSSL(conf.SSL_PORT, self, sslContext))
            self._listeners.append(reactor.listenSSL(conf.SSL_PORT + 1, self.fileserver, sslContext))
        self.startTime = time.time()
        self._tickle.start(5.0, False)
        if conf.ENABLE_TRACKER_REGISTER:
            self._pinger.start(conf.TRACKER_INTERVAL, True)
        logging.info("[server] started on ports %s", conf.SERVER_PORTS)

    def stop(self):
        for l in self._listeners:
            l.stopListening()
        self._tickle.stop()
        self._pinger.stop()

    # Notification methods called from HLProtocol instances

    def notifyConnect(self, conn):
        conn.waitForMagic(HTLC_MAGIC_LEN)
        self.connections.append(conn)
        addr = conn.transport.getPeer()
        self.lastUID += 1
        conn.context = HLUser(self.lastUID, addr.host)
        dispatcher.send(signal=client_connected, sender=self, server=self, user=conn.context)

    def notifyMagic(self, conn, magic):
        addr = conn.transport.getPeer()
        (proto1, proto2, major, minor) = unpack("!LLHH", magic)
        if (proto1 == HLCharConst("TRTP")) and (proto2 == HLCharConst("HOTL")):
            conn.writeMagic(HLServerMagic())
        else:
            logging.debug("incorrect magic from %s", addr.host)
            conn.transport.loseConnection()

    def notifyDisconnect(self, conn):
        self.connections.remove(conn)
        dispatcher.send(signal=client_disconnected, sender=self, server=self, user=conn.context)

    def notifyPacket(self, conn, packet):
        try:
            if packet.type not in PING_TYPES:
                conn.context.lastPacketTime = time.time()
                if conn.context.valid and ((conn.context.status & STATUS_AWAY) != 0):
                    conn.context.status &= ~STATUS_AWAY
                    self.sendUserChange(conn.context)
            dispatcher.send(signal=packet_received, sender=self, server=self, user=conn.context, packet=packet)
            dispatcher.send(signal=(packet_received, packet.type), sender=self, server=self, user=conn.context, packet=packet)
        except HLException as e:
            self.sendPacket(packet.error(e.msg), conn.context)
            if e.fatal:
                logging.debug("fatal error, disconnecting %s: %s", conn.context, str(e))
                conn.transport.loseConnection()
        except Exception as e:
            logging.exception("unhandled exception: %s", e)
            self.sendPacket(packet.error(e), conn.context)

    # Packet sending methods

    def sendPacket(self, packet, to=None):
        f = None
        if isinstance(to, int):
            def f(c):
                return c.context.uid == to
        elif isinstance(to, (list, tuple)):
            def f(c):
                return c.context.uid in to
        elif isinstance(to, HLUser):
            def f(c):
                return c.context == to
        elif callable(to):
            f = to
        conns = list(filter(f, self.connections))
        users = [c.context for c in conns]
        try:
            dispatcher.send(signal=packet_outgoing, sender=self, server=self, packet=packet, users=users)
            dispatcher.send(signal=(packet_outgoing, packet.type), sender=self, server=self, packet=packet, users=users)
        except Exception as e:
            print("error in packet filter:", str(e))
        except:
            logging.exception('packet filter error')
        for conn in conns:
            conn.writePacket(packet)

    def sendUserChange(self, user):
        change = HLPacket(HTLS_HDR_USER_CHANGE)
        change.addNumber(DATA_UID, user.uid)
        change.addString(DATA_NICK, user.nick)
        change.addNumber(DATA_ICON, user.icon)
        change.addNumber(DATA_STATUS, user.status)
        if user.color >= 0:
            change.addInt32(DATA_COLOR, user.color)
        self.sendPacket(change, lambda c: c.context.valid)

    # Banlist functions

    def addTempBan(self, addr, reason="no reason"):
        """ Adds a temporary ban for addr that will expire in BAN_TIME seconds. """
        if addr not in self.tempBans:
            self.tempBans[addr] = reason
            reactor.callLater(conf.BAN_TIME, self.removeTempBan, addr)
            logging.info("[ban] temporary ban for %s (%s)", addr, reason)

    def removeTempBan(self, addr):
        """ Removes a temporary ban for addr, if it exists. """
        if addr in self.tempBans:
            del self.tempBans[addr]

    def checkForBan(self, addr):
        """ Returns the reason given for a ban, if it exists. Otherwise returns None. """
        if addr in self.tempBans:
            return self.tempBans[addr]
        return self.database.checkBanlist(addr)

    # User functions

    def getUser(self, uid):
        """ Gets the HLUser object for the specified uid. """
        for user in self.userlist:
            if user.uid == uid:
                return user
        return None

    def disconnectUser(self, user):
        """ Actively disconnect the specified user. """
        for conn in self.connections:
            if conn.context == user:
                conn.transport.loseConnection()

    # Private chat functions

    def createChat(self):
        """ Creates and registers a new private chat, returns the ID of the newly created chat. """
        self.lastChatID += 1
        chat = HLChat(self.lastChatID)
        self.chats[self.lastChatID] = chat
        return chat

    def removeChat(self, id):
        """ Remove the specified private chat. """
        if id in self.chats:
            del self.chats[id]

    def getChat(self, id):
        """ Gets the HLChat object for the specified chat ID. """
        if id in self.chats:
            return self.chats[id]
        return None

    # Repeating tasks

    def checkUsers(self):
        now = time.time()
        for user in self.userlist:
            if (now - user.lastPacketTime) > conf.IDLE_TIME:
                newStatus = user.status | STATUS_AWAY
                if newStatus != user.status:
                    user.status = newStatus
                    self.sendUserChange(user)

    def pingTracker(self):
        for tracker_conf in conf.TRACKERS:
            try:
                tracker.send_update(tracker_conf['ADDRESS'], tracker_conf['PORT'], int(self.startTime), conf.SERVER_NAME,
                        conf.SERVER_DESCRIPTION, conf.SERVER_PORTS[0], len(self.userlist), tracker_conf['PASSWORD'])
            except:
                logging.exception('error pinging tracker')
