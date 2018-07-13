from phxd.permissions import PRIV_MODIFY_USERS


def handle(server, user, args, ref):
    parts = str(args).strip().split()
    rgb = parts[0]
    uid = user.uid
    if len(parts) > 1 and user.hasPriv(PRIV_MODIFY_USERS):
        rgb = parts[1]
        uid = int(parts[0])
    u = server.getUser(uid)
    if not u:
        return
    if rgb[0] == "#":
        rgb = rgb[1:]
    if len(rgb) != 6:
        return
    r, g, b = rgb[:2], rgb[2:4], rgb[4:]
    r, g, b = [int(n, 16) for n in (r, g, b)]
    u.color = 0 | (r << 16) | (g << 8) | b
    server.sendUserChange(u)
