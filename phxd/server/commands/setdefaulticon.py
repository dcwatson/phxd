from twisted.web.client import getPage

from phxd.permissions import PRIV_MODIFY_USERS
from phxd.server.utils import certifyIcon


def gotIcon(data, server):
    if data and len(data) > 0 and certifyIcon(data):
        server.defaultIcon = data


def handle(server, user, args, ref):
    parts = str(args).strip().split()
    url = parts[0]
    if user.hasPriv(PRIV_MODIFY_USERS):
        getPage(url).addCallback(gotIcon, server)
