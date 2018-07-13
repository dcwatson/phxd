from phxd.server.signals import *
from phxd.types import HLException


def require_permission(perm, action):
    def _dec(handler_func):
        def _checkperm(signal, sender, *args, **kwargs):
            user = kwargs.get('user', None)
            if user and not user.hasPriv(perm):
                raise HLException("You do not have permission to %s." % action)
            return handler_func(*args, **kwargs)
        return _checkperm
    return _dec


def packet_handler(ptype):
    def _dec(handler_func):
        setattr(handler_func, "_signal_type", (packet_received, ptype))
        return handler_func
    return _dec


def packet_filter(ptype):
    def _dec(filter_func):
        setattr(filter_func, "_signal_type", (packet_outgoing, ptype))
        return filter_func
    return _dec
