from phxd.server.database import HLDatabase
from phxd.types import HLAccount, HLNewsPost

import sqlite3


SQL_SCHEMA = ("""
    CREATE TABLE accounts (
        id integer NOT NULL PRIMARY KEY,
        login varchar(50) NOT NULL UNIQUE,
        password varchar(50) NOT NULL,
        name varchar(100) NOT NULL,
        privs varchar(20) NOT NULL,
        profile text NOT NULL DEFAULT '',
        last_login datetime
    );
""", """
    CREATE TABLE news (
        id integer NOT NULL PRIMARY KEY,
        nick varchar(50) NOT NULL,
        login varchar(50) NOT NULL,
        body text NOT NULL,
        post_date datetime NOT NULL
    );
""")


def instance(arg):
    return SQLDatabase(arg)


class SQLDatabase (HLDatabase):
    """ SQL-based implementation of HLDatabase. """

    def __init__(self, arg):
        self.db = sqlite3.connect(arg)

    def _select(self, sql, *params, **opts):
        c = self.db.cursor()
        try:
            c.execute(sql, params)
            return c.fetchone() if opts.get('first', False) else c.fetchall()
        finally:
            c.close()

    def _execute(self, sql, *params):
        c = self.db.cursor()
        try:
            res = c.execute(sql, params)
            self.db.commit()
            return res
        finally:
            c.close()

    def isConfigured(self):
        try:
            row = self._select('select count(*) from accounts', first=True)
            return row[0] > 0
        except Exception as ex:
            return False

    def setup(self):
        for sql in SQL_SCHEMA:
            try:
                self._execute(sql)
            except Exception as ex:
                pass

    def loadAccount(self, login):
        row = self._select('select id,login,password,name,privs,profile from accounts where login=?', login, first=True)
        acct = None
        if row:
            acct = HLAccount(row[1])
            acct.id = row[0]
            acct.password = row[2]
            acct.name = row[3]
            acct.privs = int(row[4])
            acct.profile = row[5]
        return acct

    def saveAccount(self, acct):
        if acct.id:
            params = (acct.login, acct.password, acct.name, str(acct.privs), acct.profile, acct.id)
            self._execute('update accounts set login=?, password=?, name=?, privs=?, profile=? where id=?', *params)
        else:
            params = (acct.login, acct.password, acct.name, str(acct.privs), acct.profile)
            self._execute('insert into accounts (login,password,name,privs,profile) values (?,?,?,?,?)', *params)

    def deleteAccount(self, acct):
        self._execute('delete from accounts where id=?', acct.id)

    def loadNewsPosts(self, limit=0, offset=0, search=None):
        sql = 'select id,nick,login,body,post_date from news order by post_date desc'
        if limit > 0:
            sql += ' limit %d' % limit
        if offset > 0:
            sql += ' offset %d' % offset
        rows = self._select(sql)
        posts = []
        for row in rows:
            post = HLNewsPost(row[1], row[2], row[3])
            post.id = row[0]
            post.date = row[4]
            posts.append(post)
        return (posts, len(posts))

    def saveNewsPost(self, post):
        sql = 'insert into news (nick,login,body,post_date) values (?,?,?,?)'
        self._execute(sql, post.nick, post.login, post.body, post.date)

    def checkBanlist(self, addr):
        return None
