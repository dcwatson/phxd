from phxd.permissions import PERM_MODIFY_USERS
from phxd.server.utils import verify_icon


def gotIcon(data, server):
    if data and len(data) > 0 and verify_icon(data):
        server.default_icon = data


def handle(server, user, args, ref):
    if user.has_perm(PERM_MODIFY_USERS):
        # TODO: fetch icon in a thread executor
        # getPage(args).addCallback(gotIcon, server)
        pass
