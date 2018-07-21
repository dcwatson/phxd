from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PERM_MODIFY_USERS


def handle(server, user, args, ref):
    parts = str(args).strip().split()
    try:
        if len(parts) > 1:
            if user.has_perm(PERM_MODIFY_USERS):
                user = server.get_user(int(parts[0]))
                sourceUser = server.get_user(int(parts[1]))
            else:
                return
        else:
            sourceUser = server.get_user(int(parts[0]))
        if user is None or sourceUser is None:
            return
        user.gif = sourceUser.gif
        user.color = sourceUser.color
        changeIcon = HLPacket(HTLS_HDR_ICON_CHANGE)
        changeIcon.add_number(DATA_UID, user.uid)
        server.send_packet(changeIcon)
        server.send_user_change(user)
    except ValueError:
        pass
