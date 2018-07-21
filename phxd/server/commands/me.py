from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.signals import packet_type_received


def handle(server, user, args, ref):
    chat = HLPacket(HTLC_HDR_CHAT)
    chat.add_string(DATA_STRING, args)
    chat.add_number(DATA_OPTION, 1)
    if ref > 0:
        chat.add_number(DATA_CHATID, ref, bits=32)
    packet_type_received.send(str(chat.kind), server=server, user=user, packet=packet)
