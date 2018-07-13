from pydispatch import dispatcher

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.signals import *
from phxd.types import HLException


def handle(server, user, args, ref):
    ids = str(args).strip().split()
    for id in ids:
        try:
            kick = HLPacket(HTLC_HDR_KICK)
            kick.addNumber(DATA_UID, int(id))
            dispatcher.send(signal=(packet_received, kick.type), sender=server, server=server, user=user, packet=kick)
        except ValueError:
            pass
        except HLException:
            pass
