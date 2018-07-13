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
@require_permission(PRIV_READ_NEWS, "read the news")
def handleNewsGet(server, user, packet):
    limit = packet.getNumber(DATA_LIMIT, conf.DEFAULT_NEWS_LIMIT)
    offset = packet.getNumber(DATA_OFFSET, 0)
    search = packet.getString(DATA_SEARCH, None)
    (posts, count) = server.database.loadNewsPosts(limit, offset, search)
    s = "".join([formatPost(p) for p in posts])
    s = s[0:65535]
    news = packet.response()
    news.addString(DATA_STRING, s)
    news.addNumber(DATA_LIMIT, limit)
    news.addNumber(DATA_OFFSET, offset)
    news.addNumber(DATA_COUNT, count)
    server.sendPacket(news, user)


@packet_handler(HTLC_HDR_NEWS_POST)
@require_permission(PRIV_POST_NEWS, "post news")
def handleNewsPost(server, user, packet):
    s = packet.getString(DATA_STRING, "")
    par = packet.getNumber(DATA_POSTID)
    if len(s) > 0:
        post = HLNewsPost(user.nick, user.account.login, s)
        post.parent_id = par
        server.database.saveNewsPost(post)
        notify = HLPacket(HTLS_HDR_NEWS_POST)
        notify.addString(DATA_STRING, formatPost(post))
        server.sendPacket(notify, lambda c: c.context.hasPriv(PRIV_READ_NEWS))
        server.sendPacket(packet.response(), user)

# Avaraline extensions


@packet_handler(HTLC_HDR_NEWS_GET_UNFORMATTED)
@require_permission(PRIV_READ_NEWS, "read the news")
def handleNewsGetUnformatted(server, user, packet):
    limit = packet.getNumber(DATA_LIMIT, conf.DEFAULT_NEWS_LIMIT)
    offset = packet.getNumber(DATA_OFFSET, 0)
    search = packet.getString(DATA_SEARCH, None)
    (posts, count) = server.database.loadNewsPosts(limit, offset, search)
    news = packet.response()
    news.addNumber(DATA_LIMIT, limit)
    news.addNumber(DATA_OFFSET, offset)
    news.addNumber(DATA_COUNT, count)
    for p in posts:
        post = HLContainer()
        post.addNumber(DATA_POSTID, p.id)
        post.addString(DATA_NICK, p.nick)
        post.addString(DATA_LOGIN, p.login)
        post.addBinary(DATA_DATECREATED, HLEncodeDate(p.date))
        post.addString(DATA_STRING, p.body)
        news.addContainer(DATA_POST, post)
    server.sendPacket(news, user)
