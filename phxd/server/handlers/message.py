from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *


@packet_handler(HTLC_HDR_MSG)
@require_permission(PRIV_SEND_MESSAGES, "send messages")
def handleMessage(server, user, packet):
    uid = packet.getNumber(DATA_UID, 0)
    s = packet.getString(DATA_STRING, "")[:conf.MAX_MSG_LEN]

    if not server.getUser(uid):
        raise HLException("Invalid user.")

    msg = HLPacket(HTLS_HDR_MSG)
    msg.addNumber(DATA_UID, user.uid)
    msg.addString(DATA_NICK, user.nick)
    msg.addString(DATA_STRING, s)
    server.sendPacket(msg, uid)
    server.sendPacket(packet.response(), user)


@packet_handler(HTLC_HDR_BROADCAST)
@require_permission(PRIV_BROADCAST, "broadcast messages")
def handleBroadcast(server, user, packet):
    s = packet.getString(DATA_STRING, "")
    broadcast = HLPacket(HTLS_HDR_BROADCAST)
    broadcast.addString(DATA_STRING, s)
    server.sendPacket(broadcast)
    server.sendPacket(packet.response(), user)
