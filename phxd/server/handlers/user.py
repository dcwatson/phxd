from pydispatch import dispatcher

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *
from phxd.types import HLException
from phxd.utils import *

from datetime import datetime
import hashlib
import logging


def install():
    dispatcher.connect(handleUserDisconnected, signal=client_disconnected)


def uninstall():
    dispatcher.disconnect(handleUserDisconnected, signal=client_disconnected)


def handleUserDisconnected(server, user):
    if user.valid:
        user.valid = False
        leave = HLPacket(HTLS_HDR_USER_LEAVE)
        leave.addNumber(DATA_UID, user.uid)
        server.sendPacket(leave)
        dispatcher.send(signal=user_leave, sender=server, server=server, user=user)


@packet_handler(HTLC_HDR_LOGIN)
def handleLogin(server, user, packet):
    login = HLDecode(packet.getBinary(DATA_LOGIN, HLEncode("guest")))
    password = HLDecode(packet.getBinary(DATA_PASSWORD, b""))

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
    handleUserChange(server, user, packet)
    user.valid = True
    user.account.lastLogin = datetime.now()

    dispatcher.send(signal=user_login, sender=server, server=server, user=user)

    info = packet.response()
    info.addString(DATA_SERVERNAME, conf.SERVER_NAME)
    info.addNumber(DATA_OPTION, CAPABILITY_NEWS)
    info.addNumber(DATA_UID, user.uid)
    server.sendPacket(info, user)
    logging.info("[login] successful login for %s", user)


@packet_handler(HTLC_HDR_USER_CHANGE)
def handleUserChange(server, user, packet):
    oldNick = user.nick
    user.nick = packet.getString(DATA_NICK, user.nick)[:conf.MAX_NICK_LEN]
    user.icon = packet.getNumber(DATA_ICON, user.icon)
    user.color = packet.getNumber(DATA_COLOR, user.color)

    # Set their admin status according to their kick priv.
    if user.hasPriv(PRIV_KICK_USERS):
        user.status |= STATUS_ADMIN
    else:
        user.status &= ~STATUS_ADMIN

    # Check to see if they can use any name; if not, set their nickname to their account name.
    if not user.hasPriv(PRIV_USE_ANY_NAME):
        user.nick = user.account.name

    server.sendUserChange(user)

    # If the user is already logged in, this was a user change event.
    if user.valid:
        dispatcher.send(signal=user_change, sender=server, server=server, user=user, oldNick=oldNick)


@packet_handler(HTLC_HDR_USER_LIST)
def handleUserList(server, user, packet):
    list = packet.response()
    for u in server.userlist:
        list.addBinary(DATA_USER, u.flatten())
    server.sendPacket(list, user)


@packet_handler(HTLC_HDR_USER_INFO)
@require_permission(PRIV_USER_INFO, "view user information")
def handleUserInfo(server, user, packet):
    uid = packet.getNumber(DATA_UID, 0)
    who = server.getUser(uid)

    if not who:
        raise HLException("Invalid user.")

    fmt = "nickname: %s\r     uid: %s\r   login: %s\rrealname: %s\r address: %s\r    idle: %s\r"
    idle = formatElapsedTime(time.time() - who.lastPacketTime)
    info = fmt % (who.nick, who.uid, who.account.login, who.account.name, who.ip, idle)
    info += "--------------------------------\r"
    num = 0
    for xfer in server.fileserver.transfers:
        if xfer.owner == uid:
            info += str(xfer) + "\r"
            num += 1
    if num < 1:
        info += "No file transfers.\r"
    info += "--------------------------------\r"

    reply = packet.response()
    reply.addNumber(DATA_UID, who.uid)
    reply.addString(DATA_NICK, who.nick)
    reply.addString(DATA_STRING, info)
    server.sendPacket(reply, user)


@packet_handler(HTLC_HDR_KICK)
def handleUserKick(server, user, packet):
    uid = packet.getNumber(DATA_UID, 0)
    ban = packet.getNumber(DATA_BAN, 0)
    who = server.getUser(uid)

    if not who:
        raise HLException("Invalid user.")

    me_login = user.account.login.lower()
    you_login = who.account.login.lower()

    if not user.hasPriv(PRIV_KICK_USERS):
        # users without kick privs can disconnect themselves or their ghosts as long as they are not guests
        if (me_login != you_login) or (me_login == "guest"):
            raise HLException("You do not have permission to disconnect users.")
    if (me_login != you_login) and who.hasPriv(PRIV_KICK_PROTECT):
        raise HLException("%s cannot be disconnected." % who.nick)

    if ban:
        server.addTempBan(who.ip, "Temporary ban.")

    server.disconnectUser(who)
    server.sendPacket(packet.response(), user)
    logging.info("[kick] %s disconnected by %s", who, user)


@packet_handler(HTLC_HDR_PING)
def handlePing(server, user, packet):
    server.sendPacket(packet.response(), user)

# Avaraline extensions


@packet_handler(HTLC_HDR_USER_INFO_UNFORMATTED)
@require_permission(PRIV_USER_INFO, "view user information")
def handleUserInfoUnformatted(server, user, packet):
    uid = packet.getNumber(DATA_UID, 0)
    who = server.getUser(uid)

    if not who:
        raise HLException("Invalid user.")

    reply = packet.response()
    reply.addNumber(DATA_UID, who.uid)
    reply.addString(DATA_NICK, who.nick)
    reply.addString(DATA_LOGIN, who.account.login)
    reply.addString(DATA_STRING, who.account.name)
    reply.addString(DATA_IP, who.ip)
    server.sendPacket(reply, user)
