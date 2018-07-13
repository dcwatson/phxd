from phxd.constants import *
from phxd.packet import HLContainer
from phxd.permissions import *
from phxd.server.decorators import *
from phxd.server.signals import *
from phxd.types import HLAccount, HLException
from phxd.utils import *

import hashlib
import logging


@packet_handler(HTLC_HDR_ACCOUNT_READ)
@require_permission(PRIV_READ_USERS, "view accounts")
def handleAccountRead(server, user, packet):
    login = packet.getString(DATA_LOGIN, "")

    acct = server.database.loadAccount(login)
    if not acct:
        raise HLException("Error loading account.")

    reply = packet.response()
    reply.addBinary(DATA_LOGIN, HLEncode(acct.login))
    reply.addBinary(DATA_PASSWORD, HLEncode(acct.password))
    reply.addString(DATA_NICK, acct.name)
    reply.addInt64(DATA_PRIVS, acct.privs)
    server.sendPacket(reply, user)


@packet_handler(HTLC_HDR_ACCOUNT_MODIFY)
@require_permission(PRIV_MODIFY_USERS, "modify accounts")
def handleAccountModify(server, user, packet):
    login = HLDecode(packet.getBinary(DATA_LOGIN, b""))
    pw_data = packet.getBinary(DATA_PASSWORD, b"")
    name = packet.getString(DATA_NICK, "")
    privs = packet.getNumber(DATA_PRIVS, 0)

    acct = server.database.loadAccount(login)
    if not acct:
        raise HLException("Invalid account.")

    acct.name = name
    acct.privs = privs
    if pw_data != "\x00":
        acct.password = hashlib.md5(HLDecode(pw_data).encode('utf-8')).hexdigest()
    server.database.saveAccount(acct)
    server.sendPacket(packet.response(), user)
    # server.updateAccounts( acct )
    logging.info("[account] %s modified by %s", login, user)


@packet_handler(HTLC_HDR_ACCOUNT_CREATE)
@require_permission(PRIV_CREATE_USERS, "create accounts")
def handleAccountCreate(server, user, packet):
    login = HLDecode(packet.getBinary(DATA_LOGIN, b""))
    passwd = HLDecode(packet.getBinary(DATA_PASSWORD, b""))
    name = packet.getString(DATA_NICK, "")
    privs = packet.getNumber(DATA_PRIVS, 0)

    if server.database.loadAccount(login):
        raise HLException("Login already exists.")

    acct = HLAccount(login)
    acct.password = hashlib.md5(passwd.encode('utf-8')).hexdigest()
    acct.name = name
    acct.privs = privs

    server.database.saveAccount(acct)
    server.sendPacket(packet.response(), user)
    logging.info("[account] %s created by %s", login, user)


@packet_handler(HTLC_HDR_ACCOUNT_DELETE)
@require_permission(PRIV_DELETE_USERS, "delete accounts")
def handleAccountDelete(server, user, packet):
    login = HLDecode(packet.getBinary(DATA_LOGIN, b""))
    acct = server.database.loadAccount(login)
    if not acct:
        raise HLException("Invalid account.")
    server.database.deleteAccount(acct)
    server.sendPacket(packet.response(), user)
    logging.info("[account] %s deleted by %s", login, user)

# Avaraline extensions


@packet_handler(HTLC_HDR_ACCOUNT_SELFMODIFY)
@require_permission(PRIV_CHANGE_PASSWORD, "modify your account")
def handleAccountSelfModify(server, user, packet):
    profile = packet.getString(DATA_STRING, None)
    passwd = packet.getBinary(DATA_PASSWORD, None)
    if profile is not None:
        user.account.profile = profile
    if passwd is not None and passwd != "\x00":
        user.account.password = hashlib.md5(HLDecode(passwd).encode('utf-8')).hexdigest()
    server.database.saveAccount(user.account)
    server.sendPacket(packet.response(), user)
    logging.info("[account] self-modify %s", user)


@packet_handler(HTLC_HDR_PERMISSION_LIST)
def handlePermissionList(server, user, packet):
    resp = packet.response()
    for group in permission_groups:
        gc = HLContainer()
        gc.addString(DATA_STRING, group.name)
        for perm in group:
            pc = HLContainer()
            pc.addString(DATA_STRING, perm.name)
            pc.addNumber(DATA_PRIVS, perm.mask)
            gc.addContainer(DATA_PERM, pc)
        resp.addContainer(DATA_PERMGROUP, gc)
    server.sendPacket(resp, user)
