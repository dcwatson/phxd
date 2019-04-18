from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.config import conf
from phxd.server.utils import verify_icon
from phxd.types import HLException

from .base import ServerHandler

from struct import pack


def set_default_icon(server, user):
    if len(server.default_icon) > 0 and not user.gif:
        user.gif = server.default_icon
        change = HLPacket(HTLS_HDR_ICON_CHANGE).add_number(DATA_UID, user.uid)
        server.send_packet(change)


def handleIconList(server, user, packet):
    list = packet.response()
    for u in server.userlist:
        data = pack("!2H", u.uid, len(u.gif)) + u.gif
        list.add(DATA_GIFLIST, data)
    server.send_packet(list, user)


def handleIconSet(server, user, packet):
    iconData = packet.binary(DATA_GIFICON, b"")

    if verify_icon(iconData):
        user.gif = iconData
        server.send_packet(packet.response(), user)
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.add_number(DATA_UID, user.uid)
        server.send_packet(change)


def handleIconGet(server, user, packet):
    uid = packet.number(DATA_UID, 0)
    info = server.get_user(uid)
    if not info:
        raise HLException("Invalid user.")
    icon = packet.response()
    icon.add_number(DATA_UID, info.uid)
    icon.add(DATA_GIFICON, info.gif)
    server.send_packet(icon, user)


class IconHandler (ServerHandler):
    packet_handlers = {
        HTLC_HDR_ICON_LIST: handleIconList,
        HTLC_HDR_ICON_SET: handleIconSet,
        HTLC_HDR_ICON_GET: handleIconGet,
    }

    def user_login(self, server, user):
        if conf.ENABLE_GIF_ICONS:
            server.loop.call_later(conf.DEFAULT_ICON_TIME, set_default_icon, server, user)
