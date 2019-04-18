from phxd.constants import *
from phxd.packet import HLPacket
from phxd.permissions import PERM_MODIFY_USERS
from phxd.server import handlers


def handle(server, user, arg, ref):
    if len(arg) > 0 and user.has_perm(PERM_MODIFY_USERS):
        bits = arg.split()
        cmd = bits[0]
        mod = ""
        if len(bits) > 1:
            mod = bits[1]
        if cmd == "list":
            chat = HLPacket(HTLS_HDR_CHAT)
            chat.add_string(DATA_STRING, ", ".join(handlers.__all__))
            server.send_packet(chat, user)
        elif cmd == "reload":
            # call next time through the event loop to avoid problems
            server.loop.call_later(0, handlers.reload, "phxd.server.handlers", mod)
