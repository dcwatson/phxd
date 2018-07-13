from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PRIV_BROADCAST


def handle(server, user, arg, ref):
    if len(arg) > 0 and user.hasPriv(PRIV_BROADCAST):
        broadcast = HLPacket(HTLS_HDR_BROADCAST)
        broadcast.addString(DATA_STRING, arg)
        server.sendPacket(broadcast)
