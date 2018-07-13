from pydispatch import dispatcher
from twisted.internet import reactor

from phxd.constants import *
from phxd.packet import HLPacket
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *
from phxd.server.utils import certifyIcon
from phxd.types import HLException

from struct import pack


def install():
    dispatcher.connect(handleStartGifTimer, signal=user_login)


def uninstall():
    dispatcher.disconnect(handleStartGifTimer, signal=user_login)


def lastChanceAsshole(server, user):
    if len(user.gif) == 0 and len(server.defaultIcon) > 0:
        user.gif = server.defaultIcon
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.addNumber(DATA_UID, user.uid)
        server.sendPacket(change)


def handleStartGifTimer(server, user):
    if conf.ENABLE_GIF_ICONS:
        reactor.callLater(conf.DEFAULT_ICON_TIME, lastChanceAsshole, server, user)


@packet_handler(HTLC_HDR_ICON_LIST)
def handleIconList(server, user, packet):
    list = packet.response()
    for u in server.userlist:
        data = pack("!2H", u.uid, len(u.gif)) + u.gif
        list.addBinary(DATA_GIFLIST, data)
    server.sendPacket(list, user)


@packet_handler(HTLC_HDR_ICON_SET)
def handleIconSet(server, user, packet):
    iconData = packet.getBinary(DATA_GIFICON, b"")

    if certifyIcon(iconData):
        user.gif = iconData
        server.sendPacket(packet.response(), user)
        change = HLPacket(HTLS_HDR_ICON_CHANGE)
        change.addNumber(DATA_UID, user.uid)
        server.sendPacket(change)


@packet_handler(HTLC_HDR_ICON_GET)
def handleIconGet(server, user, packet):
    uid = packet.getNumber(DATA_UID, 0)
    info = server.getUser(uid)
    if not info:
        raise HLException("Invalid user.")
    icon = packet.response()
    icon.addNumber(DATA_UID, info.uid)
    icon.addBinary(DATA_GIFICON, info.gif)
    server.sendPacket(icon, user)
