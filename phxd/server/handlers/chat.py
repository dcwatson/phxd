from pydispatch import dispatcher

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *
from phxd.types import HLException

import logging
import sys


def install():
    dispatcher.connect(handleUserDisconnected, signal=client_disconnected)


def uninstall():
    dispatcher.disconnect(handleUserDisconnected, signal=client_disconnected)


def _dispatchCommand(server, user, line, ref):
    """ Dispatch a line of chat to the appropriate chat command handler. """
    if line[0] == '/':
        parts = line.split(None, 1)
        cmd = parts[0][1:]
        args = ""
        if len(parts) > 1:
            args = parts[1]
        mod_path = "phxd.server.commands.%s" % cmd
        try:
            if mod_path in sys.modules:
                del sys.modules[mod_path]
            mod = __import__(mod_path, None, None, "phxd.server.commands")
            handler = getattr(mod, "handle")
            handler(server, user, args, ref)
        except Exception as e:
            logging.error("%s: %s", mod_path, e)
        return True
    return False


def handleUserDisconnected(server, user):
    deadChats = []
    # go through all the private chats removing this user
    # keep a list of dead chats to remove them all at once
    for chat in server.chats.values():
        if chat.hasInvite(user):
            chat.removeInvite(user)
        if chat.hasUser(user):
            chat.removeUser(user)
            if len(chat.users) > 0:
                # Send a chat leave to everyone left in the chat.
                leave = HLPacket(HTLS_HDR_CHAT_USER_LEAVE)
                leave.addInt32(DATA_CHATID, chat.id)
                leave.addNumber(DATA_UID, user.uid)
                for u in chat.users:
                    server.sendPacket(leave, u)
            else:
                # Otherwise, mark the chat as dead.
                deadChats.append(chat.id)
    # Now we can remove all the dead chats without modifying the list we were iterating through.
    for dead in deadChats:
        server.removeChat(dead)


@packet_handler(HTLC_HDR_CHAT)
def handleChat(server, user, packet):
    str = packet.getString(DATA_STRING, "")
    opt = packet.getNumber(DATA_OPTION, 0)
    ref = packet.getNumber(DATA_CHATID, 0)
    pchat = server.getChat(ref)

    if user.hasPriv(PRIV_SEND_CHAT) and (len(str.strip()) > 0):
        str = str.replace("\n", "\r")
        lines = str.split("\r")
        format = conf.CHAT_FORMAT
        prefix = conf.CHAT_PREFIX_LEN
        if conf.CHAT_PREFIX_ADD_NICK_LEN:
            prefix = prefix + len(user.nick)
        if opt > 0:
            format = conf.EMOTE_FORMAT
            prefix = conf.EMOTE_PREFIX_LEN + len(user.nick)
        for lineStr in lines:
            line = lineStr[:conf.MAX_CHAT_LEN]
            if (len(line.strip()) > 0) and (not _dispatchCommand(server, user, line, ref)):
                f_str = format % (user.nick, line)
                chat = HLPacket(HTLS_HDR_CHAT)
                chat.addNumber(DATA_UID, user.uid)
                chat.addNumber(DATA_OFFSET, prefix)
                chat.addString(DATA_STRING, f_str)
                if opt > 0:
                    chat.addNumber(DATA_OPTION, opt)
                if pchat is not None:
                    # If this is meant for a private chat, add the chat ID
                    # and send it to everyone in the chat.
                    chat.addInt32(DATA_CHATID, pchat.id)
                    for u in pchat.users:
                        server.sendPacket(chat, u)
                else:
                    # Otherwise, send it to public chat (and log it).
                    server.sendPacket(chat, lambda c: c.context.hasPriv(PRIV_READ_CHAT))


@packet_handler(HTLC_HDR_CHAT_CREATE)
@require_permission(PRIV_CREATE_CHATS, "create private chats")
def handleChatCreate(server, user, packet):
    uid = packet.getNumber(DATA_UID, 0)
    who = server.getUser(uid)

    # First, create the new chat, adding the user.
    chat = server.createChat()
    chat.addUser(user)

    # Send the completed task with user info.
    reply = packet.response()
    reply.addInt32(DATA_CHATID, chat.id)
    reply.addNumber(DATA_UID, user.uid)
    reply.addString(DATA_NICK, user.nick)
    reply.addNumber(DATA_ICON, user.icon)
    reply.addNumber(DATA_STATUS, user.status)
    if user.color >= 0:
        reply.addInt32(DATA_COLOR, user.color)
    server.sendPacket(reply, user)

    if who and (who.uid != user.uid):
        # Add the specified user to the invite list.
        chat.addInvite(who)

        # Invite the specified user to the newly created chat.
        invite = HLPacket(HTLS_HDR_CHAT_INVITE)
        invite.addInt32(DATA_CHATID, chat.id)
        invite.addNumber(DATA_UID, user.uid)
        invite.addString(DATA_NICK, user.nick)
        server.sendPacket(invite, who)


@packet_handler(HTLC_HDR_CHAT_INVITE)
def handleChatInvite(server, user, packet):
    ref = packet.getNumber(DATA_CHATID, 0)
    uid = packet.getNumber(DATA_UID, 0)
    chat = server.getChat(ref)
    who = server.getUser(uid)

    if not who:
        raise HLException("Invalid user.")
    if not chat:
        raise HLException("Invalid chat.")
    if uid == user.uid:
        # Ignore self invitations.
        return
    if chat.hasInvite(who):
        # Ignore all invitations after the first.
        return
    if not chat.hasUser(user):
        raise HLException("You are not in this chat.")
    if chat.hasUser(who):
        # The specified user is already in the chat.
        return

    chat.addInvite(who)

    # Send the invitation to the specified user.
    invite = HLPacket(HTLS_HDR_CHAT_INVITE)
    invite.addInt32(DATA_CHATID, chat.id)
    invite.addNumber(DATA_UID, user.uid)
    invite.addString(DATA_NICK, user.nick)
    server.sendPacket(invite, who)


@packet_handler(HTLC_HDR_CHAT_DECLINE)
def handleChatDecline(server, user, packet):
    ref = packet.getNumber(DATA_CHATID, 0)
    chat = server.getChat(ref)
    if chat and chat.hasInvite(user):
        chat.removeInvite(user)
        s = "\r< %s has declined the invitation to chat >" % user.nick
        decline = HLPacket(HTLS_HDR_CHAT)
        decline.addInt32(DATA_CHATID, chat.id)
        decline.addString(DATA_STRING, s)
        for u in chat.users:
            server.sendPacket(decline, u)


@packet_handler(HTLC_HDR_CHAT_JOIN)
def handleChatJoin(server, user, packet):
    ref = packet.getNumber(DATA_CHATID, 0)
    chat = server.getChat(ref)

    if not chat:
        raise HLException("Invalid chat.")
    if not chat.hasInvite(user):
        raise HLException("You were not invited to this chat.")

    # Send a join packet to everyone in the chat.
    join = HLPacket(HTLS_HDR_CHAT_USER_CHANGE)
    join.addInt32(DATA_CHATID, chat.id)
    join.addNumber(DATA_UID, user.uid)
    join.addString(DATA_NICK, user.nick)
    join.addNumber(DATA_ICON, user.icon)
    join.addNumber(DATA_STATUS, user.status)
    if user.color >= 0:
        join.addInt32(DATA_COLOR, user.color)
    for u in chat.users:
        server.sendPacket(join, u)

    # Add the joiner to the chat.
    chat.addUser(user)
    chat.removeInvite(user)

    # Send the userlist back to the joiner.
    list = packet.response()
    for u in chat.users:
        list.addBinary(DATA_USER, u.flatten())
    list.addString(DATA_SUBJECT, chat.subject)
    server.sendPacket(list, user)


@packet_handler(HTLC_HDR_CHAT_LEAVE)
def handleChatLeave(server, user, packet):
    ref = packet.getNumber(DATA_CHATID, 0)
    chat = server.getChat(ref)

    if not chat or not chat.hasUser(user):
        return

    chat.removeUser(user)
    if len(chat.users) > 0:
        leave = HLPacket(HTLS_HDR_CHAT_USER_LEAVE)
        leave.addInt32(DATA_CHATID, chat.id)
        leave.addNumber(DATA_UID, user.uid)
        for u in chat.users:
            server.sendPacket(leave, u)
    else:
        server.removeChat(chat.id)


@packet_handler(HTLC_HDR_CHAT_SUBJECT)
def handleChatSubject(server, user, packet):
    ref = packet.getNumber(DATA_CHATID, 0)
    sub = packet.getString(DATA_SUBJECT, "")
    chat = server.getChat(ref)

    if not chat:
        return

    subject = HLPacket(HTLS_HDR_CHAT_SUBJECT)
    subject.addInt32(DATA_CHATID, ref)
    subject.addString(DATA_SUBJECT, sub)
    for u in chat.users:
        server.sendPacket(subject, u)
