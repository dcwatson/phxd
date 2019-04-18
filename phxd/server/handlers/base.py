class ServerHandler:
    packet_handlers = {}

    def packet_received(self, server, user, packet):
        handler = self.packet_handlers.get(packet.kind)
        if handler:
            handler(server, user, packet)

    def packet_filter(self, server, users, packet):
        pass

    def user_connected(self, server, user):
        pass

    def user_login(self, server, user):
        pass

    def user_change(self, server, user, old_nick):
        pass

    def user_leave(self, server, user):
        pass

    def user_disconnected(self, server, user):
        pass

    def transfer_started(self, server, transfer):
        pass

    def transfer_completed(self, server, transfer):
        pass

    def transfer_aborted(self, server, transfer):
        pass
