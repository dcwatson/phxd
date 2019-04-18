from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import require_permission

from .base import ServerHandler


@require_permission(PERM_SEND_MESSAGES, "send messages")
def handleMessage(server, user, packet):
    uid = packet.number(DATA_UID, 0)
    s = packet.string(DATA_STRING, "")[:conf.MAX_MSG_LEN]

    if not server.get_user(uid):
        raise HLException("Invalid user.")

    msg = HLPacket(HTLS_HDR_MSG)
    msg.add_number(DATA_UID, user.uid)
    msg.add_string(DATA_NICK, user.nick)
    msg.add_string(DATA_STRING, s)
    server.send_packet(msg, uid)
    server.send_packet(packet.response(), user)


@require_permission(PERM_BROADCAST, "broadcast messages")
def handleBroadcast(server, user, packet):
    s = packet.string(DATA_STRING, "")
    broadcast = HLPacket(HTLS_HDR_BROADCAST)
    broadcast.add_string(DATA_STRING, s)
    server.send_packet(broadcast)
    server.send_packet(packet.response(), user)


class MessageHandler (ServerHandler):
    packet_handlers = {
        HTLC_HDR_MSG: handleMessage,
        HTLC_HDR_BROADCAST: handleBroadcast,
    }
