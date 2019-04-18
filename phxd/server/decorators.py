from phxd.types import HLException


def require_permission(perm, action):
    def _dec(handler_func):
        def _checkperm(*args, **kwargs):
            user = kwargs.get('user')
            if user and not user.has_perm(perm):
                raise HLException("You do not have permission to %s." % action)
            return handler_func(*args, **kwargs)
        return _checkperm
    return _dec
