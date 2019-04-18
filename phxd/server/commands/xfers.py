from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PERM_USER_INFO


def handle(server, user, args, ref):
    if user.has_perm(PERM_USER_INFO):
        s = ""
        if len(server.transfers) == 0:
            s += "\r > No file transfers in progress."
        else:
            s += "\r > File transfers:"
            for xfer in server.transfers:
                s += "\r > (%s) %s" % (xfer.owner.nick, xfer)
        chat = HLPacket(HTLS_HDR_CHAT)
        chat.add_string(DATA_STRING, s)
        if ref > 0:
            chat.add_number(DATA_CHATID, ref, bits=32)
        server.send_packet(chat, user)
