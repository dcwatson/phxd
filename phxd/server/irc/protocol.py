from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.config import conf

from .constants import RPL

import asyncio


def escape(text):
    # TODO: escape stuff
    if ' ' in text:
        return ':' + text
    return text


class IRCProtocol (asyncio.Protocol):

    # Mostly for the server to associate a HLUser with this connection.
    user = None

    def __init__(self, server):
        self.server = server
        self.transport = None
        self.address = None
        self.port = None
        self.buffer = b''

    def connection_made(self, transport):
        self.transport = transport
        self.address, self.port = transport.get_extra_info('peername')
        self.server.irc_connect(self)

    def connection_lost(self, exc):
        self.server.irc_disconnect(self)

    def data_received(self, data):
        self.buffer += data
        *lines, self.buffer = self.buffer.split(b'\r\n')
        for line in lines:
            parts = line.decode('utf-8').split(':', 2)
            if parts[0]:
                prefix = None
                cmd, *params = parts[0].strip().split(' ')
                params.extend(parts[1:])
            else:
                prefix, cmd, *params = parts[1].strip().split(' ')
                params.extend(parts[2:])
            if cmd == 'NICK':
                self.user.nick = params[0]
                self.user.account = self.server.database.loadAccount(conf.IRC_DEFAULT_ACCOUNT)
                self.user.valid = True
                self.server.send_user_change(self.user)
                self.send(RPL.WELCOME, self.user.nick, 'Hello world!')
            elif cmd == 'JOIN':
                self.send('JOIN', params[0], prefix=self.user.ident)
                self.send(RPL.TOPIC, self.user.nick, params[0], 'interesting channel topic')
                nicknames = ' '.join(user.nick for user in self.server.userlist)
                self.send(RPL.NAMREPLY, self.user.nick, '=', params[0], nicknames)
            elif cmd == 'PRIVMSG':
                packet = HLPacket(HTLC_HDR_CHAT).add_string(DATA_STRING, params[1])
                self.server.notify_packet(self, packet)

    def send(self, code, *params, prefix=None):
        start = ':' + prefix if prefix else ':localhost'
        line = '{} {} {}\r\n'.format(start, code, ' '.join(escape(p) for p in params))
        self.transport.write(line.encode('utf-8'))

    def write_packet(self, packet):
        if packet.kind == HTLS_HDR_CHAT:
            user = self.server.get_user(packet.number(DATA_UID))
            if user == self.user:
                return
            prefix = packet.number(DATA_OFFSET, 0)
            chat = packet.string(DATA_STRING, '')[prefix:]
            self.send('PRIVMSG', '#test', chat, prefix=user.ident)
