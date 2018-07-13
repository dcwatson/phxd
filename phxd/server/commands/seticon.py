from twisted.web.client import getPage

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PRIV_MODIFY_USERS
from phxd.server.utils import certifyIcon


def gotIcon(data, user, server):
    if user and data and len(data) > 0 and certifyIcon(data):
        user.gif = data
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.addNumber(DATA_UID, user.uid)
        server.sendPacket(change)


def handle(server, user, args, ref):
    parts = str(args).strip().split()
    if len(parts) > 1:
        if user.hasPriv(PRIV_MODIFY_USERS):
            user = server.getUser(int(parts[0]))
            arg = parts[1]
        else:
            return
    else:
        arg = parts[0]
    try:
        otherUid = int(arg)
        otherUser = server.getUser(otherUid)
        user.gif = otherUser.gif
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.addNumber(DATA_UID, user.uid)
        server.sendPacket(change)
    except ValueError:
        getPage(arg).addCallback(gotIcon, user, server)
