client_connected = object()
client_disconnected = object()

login_received = object()
chat_received = object()
message_received = object()

# fallback signal for unknown server packets
packet_received = object()
