from django.urls import path

from .consumers import GroupChatConsumer, PrivateChatConsumer


websocket_urlpatterns = [
    path("ws/group-text/", GroupChatConsumer.as_asgi()),
    path("ws/private/<str:username>/", PrivateChatConsumer.as_asgi()),
]
