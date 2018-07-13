from phxd.constants import *


def handle(server, user, args, ref):
    user.away = not user.away
    oldStatus = user.status
    if user.away:
        user.status |= STATUS_AWAY
    else:
        user.status &= ~STATUS_AWAY
    if user.status != oldStatus:
        server.sendUserChange(user)
