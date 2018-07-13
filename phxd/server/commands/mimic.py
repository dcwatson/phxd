from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PRIV_MODIFY_USERS


def handle(server, user, args, ref):
    parts = str(args).strip().split()
    try:
        if len(parts) > 1:
            if user.hasPriv(PRIV_MODIFY_USERS):
                user = server.getUser(int(parts[0]))
                sourceUser = server.getUser(int(parts[1]))
            else:
                return
        else:
            sourceUser = server.getUser(int(parts[0]))
        if user is None or sourceUser is None:
            return
        user.gif = sourceUser.gif
        user.color = sourceUser.color
        changeIcon = HLPacket(HTLS_HDR_ICON_CHANGE)
        changeIcon.addNumber(DATA_UID, user.uid)
        server.sendPacket(changeIcon)
        server.sendUserChange(user)
    except ValueError:
        pass
