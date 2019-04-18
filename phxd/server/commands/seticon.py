from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PERM_MODIFY_USERS
from phxd.server.utils import verify_icon


def gotIcon(data, user, server):
    if user and data and len(data) > 0 and verify_icon(data):
        user.gif = data
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.add_number(DATA_UID, user.uid)
        server.send_packet(change)


def handle(server, user, args, ref):
    parts = str(args).strip().split()
    if len(parts) > 1:
        if user.has_perm(PERM_MODIFY_USERS):
            user = server.get_user(int(parts[0]))
            arg = parts[1]
        else:
            return
    else:
        arg = parts[0]
    try:
        otherUid = int(arg)
        otherUser = server.get_user(otherUid)
        user.gif = otherUser.gif
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.add_number(DATA_UID, user.uid)
        server.send_packet(change)
    except ValueError:
        # TODO: fetch icon in a thread executor
        # getPage(arg).addCallback(gotIcon, user, server)
        pass
