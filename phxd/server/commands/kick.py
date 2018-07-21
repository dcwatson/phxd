from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.signals import packet_type_received
from phxd.types import HLException


def handle(server, user, args, ref):
    for uid in str(args).strip().split():
        try:
            kick = HLPacket(HTLC_HDR_KICK)
            kick.add_number(DATA_UID, int(uid))
            packet_type_received.send(str(kick.kind), server=server, user=user, packet=packet)
        except ValueError:
            pass
        except HLException:
            pass
