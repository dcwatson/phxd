def instance(typ, arg):
    """ Takes the name of the module to import and the arg to pass to its constructor, returns a HLDatabase subclass. """
    mod = __import__("phxd.server.database.%s" % typ, None, None, "phxd.server.database")
    return mod.instance(arg)


class HLDatabase:
    """ Base class for phxd database implementations. Should be overridden by classes in the database directory. """

    def __init__(self, arg):
        pass

    def isConfigured(self):
        """ Returns whether the database has been configured or not. Should return True after the first call to setup. """
        return False

    def setup(self):
        """ Called when isConfigured returns False. Should perform any first-run configuration. """
        pass

    def loadAccount(self, login):
        """ Creates a new HLAccount object and loads information for the specified login into it. Returns None if unsuccessful. """
        return None

    def saveAccount(self, acct):
        """ Saves the specified HLAccount object to the database. If the HLAccount has a non-zero ID, the information is updated, otherwise a new account is inserted. """
        pass

    def deleteAccount(self, acct):
        """ Deletes the specified account from the database. """
        pass

    def loadNewsPosts(self, limit=0, offset=0, search=None):
        """ Loads and returns a tuple containing a list of HLNewsPost objects from the database and the total count of posts. """
        return ([], 0)

    def saveNewsPost(self, post):
        """ Saves a HLNewsPost object to the database. """
        pass

    def checkBanlist(self, addr):
        """ Checks the banlist table, returns a reason, or None if no entry was found. """
        return None
