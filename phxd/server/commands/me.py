from pydispatch import dispatcher

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.signals import *


def handle(server, user, args, ref):
    chat = HLPacket(HTLC_HDR_CHAT)
    chat.addString(DATA_STRING, args)
    chat.addNumber(DATA_OPTION, 1)
    if ref > 0:
        chat.addInt32(DATA_CHATID, ref)
    dispatcher.send(signal=(packet_received, chat.type), sender=server, server=server, user=user, packet=chat)
