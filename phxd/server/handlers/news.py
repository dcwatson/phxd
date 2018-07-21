from phxd.constants import *
from phxd.packet import HLContainer, HLPacket
from phxd.permissions import *
from phxd.server.config import conf
from phxd.server.decorators import *
from phxd.server.signals import *
from phxd.types import HLNewsPost
from phxd.utils import HLEncodeDate


def formatPost(post):
    # TODO: configurable date formatting
    return conf.NEWS_FORMAT % (post.nick, post.login, post.date, post.body)


@packet_handler(HTLC_HDR_NEWS_GET)
@require_permission(PERM_READ_NEWS, "read the news")
def handleNewsGet(server, user, packet):
    limit = packet.number(DATA_LIMIT, conf.DEFAULT_NEWS_LIMIT)
    offset = packet.number(DATA_OFFSET, 0)
    search = packet.string(DATA_SEARCH, None)
    (posts, count) = server.database.loadNewsPosts(limit, offset, search)
    s = "".join([formatPost(p) for p in posts])
    s = s[0:65535]
    news = packet.response()
    news.add_string(DATA_STRING, s)
    news.add_number(DATA_LIMIT, limit)
    news.add_number(DATA_OFFSET, offset)
    news.add_number(DATA_COUNT, count)
    server.send_packet(news, user)


@packet_handler(HTLC_HDR_NEWS_POST)
@require_permission(PERM_POST_NEWS, "post news")
def handleNewsPost(server, user, packet):
    s = packet.string(DATA_STRING, "")
    par = packet.number(DATA_POSTID)
    if len(s) > 0:
        post = HLNewsPost(user.nick, user.account.login, s)
        post.parent_id = par
        server.database.saveNewsPost(post)
        notify = HLPacket(HTLS_HDR_NEWS_POST)
        notify.add_string(DATA_STRING, formatPost(post))
        server.send_packet(notify, lambda c: c.user.has_perm(PERM_READ_NEWS))
        server.send_packet(packet.response(), user)

# Avaraline extensions


@packet_handler(HTLC_HDR_NEWS_GET_UNFORMATTED)
@require_permission(PERM_READ_NEWS, "read the news")
def handleNewsGetUnformatted(server, user, packet):
    limit = packet.number(DATA_LIMIT, conf.DEFAULT_NEWS_LIMIT)
    offset = packet.number(DATA_OFFSET, 0)
    search = packet.string(DATA_SEARCH, None)
    (posts, count) = server.database.loadNewsPosts(limit, offset, search)
    news = packet.response()
    news.add_number(DATA_LIMIT, limit)
    news.add_number(DATA_OFFSET, offset)
    news.add_number(DATA_COUNT, count)
    for p in posts:
        post = HLContainer()
        post.add_number(DATA_POSTID, p.id)
        post.add_string(DATA_NICK, p.nick)
        post.add_string(DATA_LOGIN, p.login)
        post.add(DATA_DATECREATED, HLEncodeDate(p.date))
        post.add_string(DATA_STRING, p.body)
        news.add_container(DATA_POST, post)
    server.send_packet(news, user)
