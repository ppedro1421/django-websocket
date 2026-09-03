from django.urls import path

from .consumers import TestConsumer


websocket_urlpatterns = [
    path("ws/group-text/", TestConsumer.as_asgi()),
]
