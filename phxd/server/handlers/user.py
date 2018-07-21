from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import packet_handler, require_permission
from phxd.server.signals import client_disconnected, user_change, user_leave, user_login
from phxd.types import HLException
from phxd.utils import *

from datetime import datetime
import hashlib
import logging


def install():
    client_disconnected.connect(handle_user_disconnected)


def uninstall():
    client_disconnected.disconnect(handle_user_disconnected)


def handle_user_disconnected(sender, server, user):
    if user.valid:
        user.valid = False
        leave = HLPacket(HTLS_HDR_USER_LEAVE)
        leave.add_number(DATA_UID, user.uid)
        server.send_packet(leave)
        user_leave.send(user, server=server)


@packet_handler(HTLC_HDR_LOGIN)
def handleLogin(server, user, packet):
    login = HLDecode(packet.binary(DATA_LOGIN, HLEncode("guest")))
    password = HLDecode(packet.binary(DATA_PASSWORD, b""))

    # Check for temporary and permanent bans.
    reason = server.checkForBan(user.ip)
    if reason:
        raise HLException("You are banned: %s" % reason, True)

    # Load and configure the account information.
    user.account = server.database.loadAccount(login)
    if not user.account:
        raise HLException("Login is incorrect.", True)
    if user.account.password != hashlib.md5(password.encode('utf-8')).hexdigest():
        raise HLException("Password is incorrect.", True)

    # Handle the nickname/icon/color stuff, broadcast the join packet.
    handleUserChange(HTLC_HDR_LOGIN, server, user, packet)
    user.valid = True
    user.account.lastLogin = datetime.now()

    user_login.send(user, server=server)

    info = packet.response()
    info.add_string(DATA_SERVERNAME, conf.SERVER_NAME)
    info.add_number(DATA_OPTION, CAPABILITY_NEWS)
    info.add_number(DATA_UID, user.uid)
    server.send_packet(info, user)
    logging.info("[login] successful login for %s", user)


@packet_handler(HTLC_HDR_USER_CHANGE)
def handleUserChange(server, user, packet):
    old_nick = user.nick
    user.nick = packet.string(DATA_NICK, user.nick)[:conf.MAX_NICK_LEN]
    user.icon = packet.number(DATA_ICON, user.icon)
    user.color = packet.number(DATA_COLOR, user.color)

    # Set their admin status according to their kick priv.
    if user.has_perm(PERM_KICK_USERS):
        user.status |= STATUS_ADMIN
    else:
        user.status &= ~STATUS_ADMIN

    # Check to see if they can use any name; if not, set their nickname to their account name.
    if not user.has_perm(PERM_USE_ANY_NAME):
        user.nick = user.account.name

    server.send_user_change(user)

    # If the user is already logged in, this was a user change event.
    if user.valid:
        user_change.send(user, server=server, old_nick=old_nick)


@packet_handler(HTLC_HDR_USER_LIST)
def handleUserList(server, user, packet):
    reply = packet.response()
    for u in server.userlist:
        reply.add(DATA_USER, u.flatten())
    server.send_packet(reply, user)


@packet_handler(HTLC_HDR_USER_INFO)
@require_permission(PERM_USER_INFO, "view user information")
def handleUserInfo(server, user, packet):
    uid = packet.number(DATA_UID, 0)
    who = server.get_user(uid)

    if not who:
        raise HLException("Invalid user.")

    fmt = "nickname: %s\r     uid: %s\r   login: %s\rrealname: %s\r address: %s\r    idle: %s\r"
    idle = formatElapsedTime(time.time() - who.last_packet_time)
    info = fmt % (who.nick, who.uid, who.account.login, who.account.name, who.ip, idle)
    info += "--------------------------------\r"
    num = 0
    for xfer in server.transfers:
        if xfer.owner == who:
            info += str(xfer) + "\r"
            num += 1
    if num < 1:
        info += "No file transfers.\r"
    info += "--------------------------------\r"

    reply = packet.response()
    reply.add_number(DATA_UID, who.uid)
    reply.add_string(DATA_NICK, who.nick)
    reply.add_string(DATA_STRING, info)
    server.send_packet(reply, user)


@packet_handler(HTLC_HDR_KICK)
def handleUserKick(server, user, packet):
    uid = packet.number(DATA_UID, 0)
    ban = packet.number(DATA_BAN, 0)
    who = server.get_user(uid)

    if not who:
        raise HLException("Invalid user.")

    me_login = user.account.login.lower()
    you_login = who.account.login.lower()

    if not user.has_perm(PERM_KICK_USERS):
        # users without kick privs can disconnect themselves or their ghosts as long as they are not guests
        if (me_login != you_login) or (me_login == "guest"):
            raise HLException("You do not have permission to disconnect users.")
    if (me_login != you_login) and who.has_perm(PERM_KICK_PROTECT):
        raise HLException("%s cannot be disconnected." % who.nick)

    if ban:
        server.addTempBan(who.ip, "Temporary ban.")

    server.disconnect_user(who)
    server.send_packet(packet.response(), user)
    logging.info("[kick] %s disconnected by %s", who, user)


@packet_handler(HTLC_HDR_PING)
def handlePing(server, user, packet):
    server.send_packet(packet.response(), user)

# Avaraline extensions


@packet_handler(HTLC_HDR_USER_INFO_UNFORMATTED)
@require_permission(PERM_USER_INFO, "view user information")
def handleUserInfoUnformatted(server, user, packet):
    uid = packet.number(DATA_UID, 0)
    who = server.get_user(uid)

    if not who:
        raise HLException("Invalid user.")

    reply = packet.response()
    reply.add_number(DATA_UID, who.uid)
    reply.add_string(DATA_NICK, who.nick)
    reply.add_string(DATA_LOGIN, who.account.login)
    reply.add_string(DATA_STRING, who.account.name)
    reply.add_string(DATA_IP, who.ip)
    server.send_packet(reply, user)
