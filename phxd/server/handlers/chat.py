from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PERM_CREATE_CHATS, PERM_READ_CHAT, PERM_SEND_CHAT
from phxd.server.config import conf
from phxd.server.decorators import packet_handler, require_permission
from phxd.server.signals import client_disconnected
from phxd.types import HLException

import logging
import sys


def install():
    client_disconnected.connect(handle_user_disconnected)


def uninstall():
    client_disconnected.disconnect(handle_user_disconnected)


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


def handle_user_disconnected(conn, server, user):
    deadChats = []
    # go through all the private chats removing this user
    # keep a list of dead chats to remove them all at once
    for chat in server.chats.values():
        if chat.has_invite(user):
            chat.remove_invite(user)
        if chat.has_user(user):
            chat.remove_user(user)
            if len(chat.users) > 0:
                # Send a chat leave to everyone left in the chat.
                leave = HLPacket(HTLS_HDR_CHAT_USER_LEAVE)
                leave.add_number(DATA_CHATID, chat.id, bits=32)
                leave.add_number(DATA_UID, user.uid)
                for u in chat.users:
                    server.send_packet(leave, u)
            else:
                # Otherwise, mark the chat as dead.
                deadChats.append(chat.id)
    # Now we can remove all the dead chats without modifying the list we were iterating through.
    for dead in deadChats:
        server.remove_chat(dead)


@packet_handler(HTLC_HDR_CHAT)
def handleChat(server, user, packet):
    str = packet.string(DATA_STRING, "")
    opt = packet.number(DATA_OPTION, 0)
    ref = packet.number(DATA_CHATID, 0)
    pchat = server.get_chat(ref)

    if user.has_perm(PERM_SEND_CHAT) and (len(str.strip()) > 0):
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
                chat.add_number(DATA_UID, user.uid)
                chat.add_number(DATA_OFFSET, prefix)
                chat.add_string(DATA_STRING, f_str)
                if opt > 0:
                    chat.add_number(DATA_OPTION, opt)
                if pchat is not None:
                    # If this is meant for a private chat, add the chat ID
                    # and send it to everyone in the chat.
                    chat.add_number(DATA_CHATID, pchat.id, bits=32)
                    for u in pchat.users:
                        server.send_packet(chat, u)
                else:
                    # Otherwise, send it to public chat (and log it).
                    server.send_packet(chat, lambda c: c.user.has_perm(PERM_READ_CHAT))


@packet_handler(HTLC_HDR_CHAT_CREATE)
@require_permission(PERM_CREATE_CHATS, "create private chats")
def handleChatCreate(server, user, packet):
    uid = packet.number(DATA_UID, 0)
    who = server.get_user(uid)

    # First, create the new chat, adding the user.
    chat = server.create_chat()
    chat.add_user(user)

    # Send the completed task with user info.
    reply = packet.response()
    reply.add_number(DATA_CHATID, chat.id, bits=32)
    reply.add_number(DATA_UID, user.uid)
    reply.add_string(DATA_NICK, user.nick)
    reply.add_number(DATA_ICON, user.icon)
    reply.add_number(DATA_STATUS, user.status)
    if user.color >= 0:
        reply.add_number(DATA_COLOR, user.color, bits=32)
    server.send_packet(reply, user)

    if who and (who.uid != user.uid):
        # Add the specified user to the invite list.
        chat.add_invite(who)

        # Invite the specified user to the newly created chat.
        invite = HLPacket(HTLS_HDR_CHAT_INVITE)
        invite.add_number(DATA_CHATID, chat.id, bits=32)
        invite.add_number(DATA_UID, user.uid)
        invite.add_string(DATA_NICK, user.nick)
        server.send_packet(invite, who)


@packet_handler(HTLC_HDR_CHAT_INVITE)
def handleChatInvite(server, user, packet):
    ref = packet.number(DATA_CHATID, 0)
    uid = packet.number(DATA_UID, 0)
    chat = server.get_chat(ref)
    who = server.get_user(uid)

    if not who:
        raise HLException("Invalid user.")
    if not chat:
        raise HLException("Invalid chat.")
    if uid == user.uid:
        # Ignore self invitations.
        return
    if chat.has_invite(who):
        # Ignore all invitations after the first.
        return
    if not chat.has_user(user):
        raise HLException("You are not in this chat.")
    if chat.has_user(who):
        # The specified user is already in the chat.
        return

    chat.add_invite(who)

    # Send the invitation to the specified user.
    invite = HLPacket(HTLS_HDR_CHAT_INVITE)
    invite.add_number(DATA_CHATID, chat.id, bits=32)
    invite.add_number(DATA_UID, user.uid)
    invite.add_string(DATA_NICK, user.nick)
    server.send_packet(invite, who)


@packet_handler(HTLC_HDR_CHAT_DECLINE)
def handleChatDecline(server, user, packet):
    ref = packet.number(DATA_CHATID, 0)
    chat = server.get_chat(ref)
    if chat and chat.has_invite(user):
        chat.remove_invite(user)
        s = "\r< %s has declined the invitation to chat >" % user.nick
        decline = HLPacket(HTLS_HDR_CHAT)
        decline.add_number(DATA_CHATID, chat.id, bits=32)
        decline.add_string(DATA_STRING, s)
        for u in chat.users:
            server.send_packet(decline, u)


@packet_handler(HTLC_HDR_CHAT_JOIN)
def handleChatJoin(server, user, packet):
    ref = packet.number(DATA_CHATID, 0)
    chat = server.get_chat(ref)

    if not chat:
        raise HLException("Invalid chat.")
    if not chat.has_invite(user):
        raise HLException("You were not invited to this chat.")

    # Send a join packet to everyone in the chat.
    join = HLPacket(HTLS_HDR_CHAT_USER_CHANGE)
    join.add_number(DATA_CHATID, chat.id, bits=32)
    join.add_number(DATA_UID, user.uid)
    join.add_string(DATA_NICK, user.nick)
    join.add_number(DATA_ICON, user.icon)
    join.add_number(DATA_STATUS, user.status)
    if user.color >= 0:
        join.add_number(DATA_COLOR, user.color, bits=32)
    for u in chat.users:
        server.send_packet(join, u)

    # Add the joiner to the chat.
    chat.add_user(user)
    chat.remove_invite(user)

    # Send the userlist back to the joiner.
    list = packet.response()
    for u in chat.users:
        list.add(DATA_USER, u.flatten())
    list.add_string(DATA_SUBJECT, chat.subject)
    server.send_packet(list, user)


@packet_handler(HTLC_HDR_CHAT_LEAVE)
def handleChatLeave(server, user, packet):
    ref = packet.number(DATA_CHATID, 0)
    chat = server.get_chat(ref)

    if not chat or not chat.has_user(user):
        return

    chat.remove_user(user)
    if len(chat.users) > 0:
        leave = HLPacket(HTLS_HDR_CHAT_USER_LEAVE)
        leave.add_number(DATA_CHATID, chat.id, bits=32)
        leave.add_number(DATA_UID, user.uid)
        for u in chat.users:
            server.send_packet(leave, u)
    else:
        server.remove_chat(chat.id)


@packet_handler(HTLC_HDR_CHAT_SUBJECT)
def handleChatSubject(server, user, packet):
    ref = packet.number(DATA_CHATID, 0)
    sub = packet.string(DATA_SUBJECT, "")
    chat = server.get_chat(ref)

    if not chat:
        return

    subject = HLPacket(HTLS_HDR_CHAT_SUBJECT)
    subject.add_number(DATA_CHATID, ref, bits=32)
    subject.add_string(DATA_SUBJECT, sub)
    for u in chat.users:
        server.send_packet(subject, u)
