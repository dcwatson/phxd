# from phxd import tracker
from phxd.constants import *
from phxd.packet import HLPacket
from phxd.protocol import HLServerProtocol, HLTransferProtocol
from phxd.server import database
from phxd.server.config import conf
from phxd.server.irc.protocol import IRCProtocol
from phxd.server.signals import (
    client_connected, client_disconnected, packet_outgoing, packet_type_received, transfer_aborted, transfer_completed,
    transfer_started)
from phxd.transfer import HLIncomingTransfer, HLOutgoingTransfer
from phxd.types import *
from phxd.utils import HLCharConst

from struct import unpack
import asyncio
import hashlib
import logging
import time


class HLServer:

    def __init__(self, loop=None):
        self.loop = loop or asyncio.get_event_loop()
        self.last_uid = 0
        self.last_chat_id = 0
        self.connections = []
        self.chats = {
            0: HLChat(0, channel=conf.IRC_DEFAULT_CHANNEL),
        }
        self.default_icon = ""
        self.tempBans = {}
        self.start_time = None
        self.database = database.instance(conf.DB_TYPE, conf.DB_ARG)
        self.last_transfer_id = 0
        self.transfers = []

    @property
    def userlist(self):
        return [c.user for c in self.connections if c.user.valid]

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
            self.loop.run_until_complete(
                self.loop.create_server(lambda: HLServerProtocol(self), conf.SERVER_BIND, port)
            )
            # File server runs on port + 1
            self.loop.run_until_complete(
                self.loop.create_server(lambda: HLTransferProtocol(self), conf.SERVER_BIND, port + 1)
            )
        """
        if conf.ENABLE_SSL:
            sslContext = ssl.DefaultOpenSSLContextFactory(conf.SSL_KEY_FILE, conf.SSL_CERT_FILE)
            self._listeners.append(reactor.listenSSL(conf.SSL_PORT, self, sslContext))
            self._listeners.append(reactor.listenSSL(conf.SSL_PORT + 1, self, sslContext))
        """
        if conf.ENABLE_IRC:
            self.loop.run_until_complete(
                self.loop.create_server(lambda: IRCProtocol(self), conf.SERVER_BIND, conf.IRC_PORT)
            )
        self.start_time = time.time()
        self.loop.call_later(5.0, self.check_users)
        if conf.ENABLE_TRACKER_REGISTER:
            self.loop.call_later(conf.TRACKER_INTERVAL, self.ping_tracker)
        logging.info("[server] started on ports %s", conf.SERVER_PORTS)

    # Notification methods called from HLProtocol instances

    def notify_connect(self, conn):
        self.last_uid += 1
        conn.user = HLUser(self.last_uid, conn.address)
        self.connections.append(conn)
        client_connected.send(conn, server=self, user=conn.user)

    def notify_magic(self, conn, magic):
        (proto1, proto2, major, minor) = unpack("!LLHH", magic)
        if (proto1 != HLCharConst("TRTP")) or (proto2 != HLCharConst("HOTL")):
            logging.debug("incorrect magic from %s:%s", conn.address, conn.port)
            conn.transport.close()

    def notify_disconnect(self, conn):
        client_disconnected.send(conn, server=self, user=conn.user)
        self.connections.remove(conn)

    def notify_packet(self, conn, packet):
        try:
            if packet.kind not in PING_TYPES:
                conn.user.last_packet_time = time.time()
                if conn.user.valid and ((conn.user.status & STATUS_AWAY) != 0):
                    conn.user.status &= ~STATUS_AWAY
                    self.send_user_change(conn.user)
            # TODO: https://github.com/jek/blinker/pull/42
            packet_type_received.send(str(packet.kind), server=self, user=conn.user, packet=packet)
        except HLException as e:
            self.send_packet(packet.error(e.msg), conn.user)
            if e.fatal:
                logging.debug("fatal error, disconnecting %s: %s", conn.user, str(e))
                conn.transport.close()
        except Exception as e:
            logging.exception("unhandled exception: %s", e)
            self.send_packet(packet.error(e), conn.user)

    # Notifications from HLTransferProtocol

    def transfer_connect(self, conn):
        pass

    def transfer_disconnect(self, conn):
        if conn.transfer in self.transfers:
            if conn.transfer.is_complete():
                logging.info("[xfer] completed %s", conn.transfer)
                transfer_completed.send(self, transfer=conn.transfer)
            else:
                logging.info("[xfer] aborted %s", conn.transfer)
                transfer_aborted.send(self, transfer=conn.transfer)
            self.transfers.remove(conn.transfer)

    def transfer_magic(self, conn, xfid, size, flags):
        for transfer in self.transfers:
            if transfer.id == xfid:
                if transfer.incoming and transfer.total == 0:
                    transfer.total = size
                conn.start(transfer)
                transfer_started.send(self, transfer=transfer)

    # Notifications from IRCProtocol

    def irc_connect(self, conn):
        self.last_uid += 1
        conn.user = HLUser(self.last_uid, conn.address)
        self.connections.append(conn)
        client_connected.send(conn, server=self, user=conn.user)

    def irc_disconnect(self, conn):
        client_disconnected.send(conn, server=self, user=conn.user)
        self.connections.remove(conn)

    # Packet sending methods

    def send_packet(self, packet, to=None):
        if isinstance(to, int):
            conns = [c for c in self.connections if c.user.uid == to]
        elif isinstance(to, (list, tuple)):
            conns = [c for c in self.connections if c.user.uid in to]
        elif isinstance(to, HLUser):
            conns = [c for c in self.connections if c.user == to]
        elif callable(to):
            conns = [c for c in self.connections if to(c)]
        else:
            conns = self.connections
        try:
            packet_outgoing.send(packet.kind, server=self, packet=packet, users=[c.user for c in conns])
        except:
            logging.exception('packet filter error')
        for conn in conns:
            conn.write_packet(packet)

    def send_user_change(self, user, join=False):
        change = HLPacket(HTLS_HDR_USER_CHANGE)
        change.add_number(DATA_UID, user.uid)
        change.add_string(DATA_NICK, user.nick)
        change.add_number(DATA_ICON, user.icon)
        change.add_number(DATA_STATUS, user.status)
        if user.color >= 0:
            change.add_number(DATA_COLOR, user.color, bits=32)
        if join:
            # For clients who want to be dumb about knowing if this was a join or change.
            # Plus it makes sending channel JOINs in the IRC handler easier.
            change.add_number(DATA_JOIN, 1)
        self.send_packet(change, lambda c: c.user.valid)

    # File transfers

    def add_upload(self, user, file):
        self.last_transfer_id += 1
        info = HLIncomingTransfer(self.last_transfer_id, file, user)
        self.transfers.append(info)
        return info

    def add_download(self, user, file, resume):
        self.last_transfer_id += 1
        info = HLOutgoingTransfer(self.last_transfer_id, file, user, resume)
        self.transfers.append(info)
        return info

    def check_transfers(self):
        # TODO: when a transfer times out, close it's transport connection
        deadlist = []
        now = time.time()
        for x in self.transfers:
            if (now - x.lastActivity) > conf.XFER_TIMEOUT:
                deadlist.append(x)
        for dead in deadlist:
            logging.info("[xfer] timed out %s", dead)
            self.transfers.remove(dead)

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

    def get_user(self, uid):
        """ Gets the HLUser object for the specified uid. """
        for conn in self.connections:
            if conn.user.uid == uid:
                return conn.user
        return None

    def disconnect_user(self, user):
        """ Actively disconnect the specified user. """
        for conn in self.connections:
            if conn.user == user:
                conn.transport.close()

    # Private chat functions

    def create_chat(self, channel=None):
        """ Creates and registers a new private chat, returns the ID of the newly created chat. """
        self.last_chat_id += 1
        return self.chats.setdefault(self.last_chat_id, HLChat(self.last_chat_id, channel=channel))

    def remove_chat(self, chat_id):
        """ Remove the specified private chat. """
        if chat_id in self.chats:
            del self.chats[chat_id]

    def get_chat(self, chat_id):
        """ Gets the HLChat object for the specified chat ID. """
        return self.chats.get(chat_id)

    def get_channel(self, channel):
        for chat_id, chat in self.chats.items():
            if chat.channel == channel:
                return chat
        return None

    # Repeating tasks

    def check_users(self):
        now = time.time()
        for user in self.userlist:
            if (now - user.last_packet_time) > conf.IDLE_TIME:
                new_status = user.status | STATUS_AWAY
                if new_status != user.status:
                    user.status = new_status
                    self.send_user_change(user)
        self.loop.call_later(5.0, self.check_users)

    def ping_tracker(self):
        try:
            tracker.send_update(
                conf.TRACKER_ADDRESS,
                conf.TRACKER_PORT,
                int(self.start_time),
                conf.SERVER_NAME,
                conf.SERVER_DESCRIPTION,
                conf.SERVER_PORTS[0],
                len(self.userlist),
                conf.TRACKER_PASSWORD
            )
        except:
            logging.exception('error pinging tracker')
        self.loop.call_later(conf.TRACKER_INTERVAL, self.ping_tracker)
