from phxd.server.signals import packet_outgoing, packet_type_received
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


def packet_handler(packet_type):
    def _dec(handler_func):
        def _handler(packet_type, server, user, packet):
            return handler_func(server, user, packet)
        packet_type_received.connect(_handler, sender=str(packet_type))
        return _handler
    return _dec


def packet_filter(packet_type):
    def _dec(filter_func):
        def _handler(packet_type, server, packet, users):
            return filter_func(server, packet, users)
        packet_outgoing.connect(_handler, sender=str(packet_type))
        return _handler
    return _dec
