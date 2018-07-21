from blinker import signal


packet_received = signal('packet-received')
packet_outgoing = signal('packet-outgoing')

# Specific signal where the sender is the packet type, not the server.
packet_type_received = signal('packet-type-received')

client_connected = signal('client-connected')
client_disconnected = signal('client-disconnected')

transfer_started = signal('transfer-started')
transfer_completed = signal('transfer-completed')
transfer_aborted = signal('transfer-aborted')

user_login = signal('user-login')
user_change = signal('user-change')
user_leave = signal('user-leave')

signal_reload = signal('reload')
