from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.config import conf
from phxd.types import HLAccount

from .constants import RPL

import asyncio
import logging


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
            handler = getattr(self, 'handle_{}'.format(cmd.upper()), None)
            if handler:
                handler(*params, prefix=prefix)
            else:
                logging.debug('Unknown IRC command "%s" with params: %s', cmd, params)

    def send(self, code, *params, prefix=None):
        start = ':{}'.format(prefix or conf.IRC_SERVER_NAME)
        line = '{} {} {}\r\n'.format(start, code, ' '.join(escape(p) for p in params))
        self.transport.write(line.encode('utf-8'))

    def write_packet(self, packet):
        if packet.kind == HTLS_HDR_CHAT:
            user = self.server.get_user(packet.number(DATA_UID))
            if user == self.user:
                # Don't write back messages from the user.
                return
            chat = self.server.get_chat(packet.number(DATA_CHATID, 0))
            prefix = packet.number(DATA_OFFSET, 0)
            message = packet.string(DATA_STRING, '')[prefix:]
            if chat.channel:
                self.send('PRIVMSG', chat.channel, message, prefix=user.ident)
        elif packet.kind == HTLS_HDR_USER_CHANGE:
            join = packet.number(DATA_JOIN)
            if join:
                user = self.server.get_user(packet.number(DATA_UID))
                chat = self.server.get_chat(0)
                self.send('JOIN', chat.channel, prefix=user.ident)
        elif packet.kind == HTLS_HDR_CHAT_USER_LEAVE:
            user = self.server.get_user(packet.number(DATA_UID))
            chat = self.server.get_chat(packet.number(DATA_CHATID, 0))
            if chat.channel:
                self.send('PART', chat.channel, prefix=user.ident)

    def handle_PING(self, *params, prefix=None):
        self.send('PONG', conf.IRC_SERVER_NAME, ' '.join(params))

    def handle_PASS(self, *params, prefix=None):
        pass

    def handle_USER(self, *params, prefix=None):
        pass

    def handle_NICK(self, *params, prefix=None):
        self.user.nick = params[0]
        self.user.account = HLAccount.query(login=conf.IRC_DEFAULT_ACCOUNT).get()
        self.user.valid = True
        self.server.send_user_change(self.user)
        self.send(RPL.WELCOME, self.user.nick, 'The public chat room for this server is {}'.format(conf.IRC_DEFAULT_CHANNEL))
        user_login.send(self.user, server=self.server)

    def handle_JOIN(self, *params, prefix=None):
        chat = self.server.get_channel(params[0]) or self.server.create_chat(params[0])
        if self.user in chat.users:
            return
        chat.add_user(self.user)
        self.send('JOIN', chat.channel, prefix=self.user.ident)
        if chat.subject:
            self.send(RPL.TOPIC, self.user.nick, chat.channel, chat.subject)
        else:
            self.send(RPL.NOTOPIC, self.user.nick, chat.channel)
        # Channels: = for public, * for private, @ for secret
        # Users: @ for ops, + for voiced
        self.send(RPL.NAMREPLY, self.user.nick, '=', chat.channel, ' '.join(user.nick for user in chat.users))
        self.send(RPL.ENDOFNAMES, self.user.nick, chat.channel, 'End of NAMES list')

    def handle_PRIVMSG(self, *params, prefix=None):
        if params[0].startswith('#'):
            chat = self.server.get_channel(params[0])
            if chat:
                packet = HLPacket(HTLC_HDR_CHAT)
                packet.add_number(DATA_CHATID, chat.id)
                packet.add_string(DATA_STRING, params[1])
                self.server.notify_packet(self, packet)

    def handle_MODE(self, *params, prefix=None):
        pass

    def handle_WHO(self, *params, prefix=None):
        if params and params[0].startswith('#'):
            chat = self.server.get_channel(params[0])
            if chat:
                for user in chat.users:
                    self.send(RPL.WHOREPLY, self.user.nick, chat.channel, user.account.login, user.ip, conf.IRC_SERVER_NAME, user.nick, 'H', '0 ' + user.account.name)
                self.send(RPL.ENDOFWHO, self.user.nick, params[0], 'End of WHO list')
