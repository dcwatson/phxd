from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PRIV_USER_INFO


def handle(server, user, args, ref):
    if user.hasPriv(PRIV_USER_INFO):
        str = ""
        if len(server.fileserver.transfers) == 0:
            str += "\r > No file transfers in progress."
        else:
            str += "\r > File transfers:"
            for xfer in server.fileserver.transfers:
                u = server.getUser(xfer.owner)
                owner = u.nick if u else "<none>"
                str += "\r > (%s) %s" % (owner, xfer)
        chat = HLPacket(HTLS_HDR_CHAT)
        chat.addString(DATA_STRING, str)
        if ref > 0:
            chat.addInt32(DATA_CHATID, ref)
        server.sendPacket(chat, user)
