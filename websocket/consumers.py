import json

from channels.generic.websocket import AsyncWebsocketConsumer


class TestConsumer(AsyncWebsocketConsumer):

    group_name = "test_room"

    async def connect(self):
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send(
            text_data=json.dumps({
                "type": "connection",
                "message": "WebSocket conectado com sucesso!",
            })
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Envie uma mensagem em JSON válido.",
            }))
            return

        message = data.get("message")
        username = data.get("username", "Anônimo")

        if not isinstance(message, str) or not message.strip():
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "O campo 'message' é obrigatório.",
            }))
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "chat.message",
                "message": message.strip(),
                "username": username,
            },
        )

    async def chat_message(self, event):
        await self.send(
            text_data=json.dumps({
                "type": "message",
                "message": event["message"],
                "username": event["username"],
            })
        )

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

        print(f"WebSocket desconectado: {close_code}")
