from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PERM_BROADCAST


def handle(server, user, arg, ref):
    if len(arg) > 0 and user.has_perm(PERM_BROADCAST):
        broadcast = HLPacket(HTLS_HDR_BROADCAST)
        broadcast.add_string(DATA_STRING, arg)
        server.send_packet(broadcast)
