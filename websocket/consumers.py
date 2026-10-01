import json
import re

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import ChatGroup


class GroupChatConsumer(AsyncWebsocketConsumer):
    default_group = "geral"
    max_groups = 20
    valid_group_name = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")

    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        self.joined_groups = {}
        await self.accept()
        group = await self.get_default_group()
        self.default_group_id = group.pk
        await self.join_group(group)
        await self.send_json({
            "type": "connection",
            "message": "WebSocket conectado com sucesso!",
            "groups": sorted(self.joined_groups),
        })

    async def receive(self, text_data=None, bytes_data=None):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send_error("Envie uma mensagem em JSON válido.")
            return

        if not isinstance(data, dict):
            await self.send_error("Envie um objeto JSON válido.")
            return

        action = data.get("action", "message")
        if action == "list":
            await self.send_json({"type": "group_list", "groups": await self.saved_groups()})
            return
        group = data.get("group", self.default_group)

        if "group_id" not in data and not self.is_valid_group(group):
            await self.send_error(
                "O grupo deve ter de 1 a 80 caracteres: letras, números, '.', '_' ou '-'."
            )
            return

        if action == "create":
            if not self.is_valid_group(group):
                await self.send_error("Nome de grupo inválido.")
                return
            group = await self.create_group(group)
            await self.send_group_status("created", group)
            return

        if action not in ("join", "leave", "message"):
            await self.send_error("A ação deve ser 'create', 'list', 'join', 'leave' ou 'message'.")
            return
        try:
            group = await self.resolve_group(data, create_missing=action == "join")
        except ValueError as error:
            await self.send_error(str(error))
            return

        if action == "join":
            if group.pk not in self.joined_groups:
                if len(self.joined_groups) >= self.max_groups:
                    await self.send_error(
                        f"Cada conexão pode participar de no máximo {self.max_groups} grupos."
                    )
                    return
                await self.join_group(group)
            await self.send_group_status("joined", group)
            return

        if action == "leave":
            if group.pk not in self.joined_groups:
                await self.send_error(f"Você não participa do grupo '{group}'.")
                return
            await self.remove_membership(group)
            await self.leave_group(group.pk)
            await self.send_group_status("left", group)
            return

        if group.pk not in self.joined_groups:
            await self.send_error(f"Entre no grupo '{group}' antes de enviar mensagens.")
            return

        message = data.get("message")
        username = self.user.get_username()

        if not isinstance(message, str) or not message.strip():
            await self.send_error("O campo 'message' é obrigatório.")
            return

        await self.channel_layer.group_send(
            self.channel_group_name(group.pk),
            {
                "type": "chat.message",
                "message": message,
                "username": username,
                "group": group.name,
                "group_id": group.pk,
            },
        )

    async def chat_message(self, event):
        await self.send_json({
            "type": "message",
            "message": event["message"],
            "username": event["username"],
            "group": event["group"],
            "group_id": event["group_id"],
        })

    async def disconnect(self, close_code):
        for group in tuple(getattr(self, "joined_groups", ())):
            await self.leave_group(group)

    async def join_group(self, group):
        await self.add_membership(group)
        await self.channel_layer.group_add(
            self.channel_group_name(group.pk),
            self.channel_name,
        )
        self.joined_groups[group.pk] = group.name

    async def leave_group(self, group):
        await self.channel_layer.group_discard(
            self.channel_group_name(group),
            self.channel_name,
        )
        self.joined_groups.pop(group, None)

    @database_sync_to_async
    def create_group(self, name):
        with transaction.atomic():
            group = ChatGroup.objects.create(name=name, created_by=self.user)
            group.users.add(self.user)
        return group

    @database_sync_to_async
    def get_default_group(self):
        group = ChatGroup.objects.filter(name=self.default_group).order_by("pk").first()
        if group is None:
            group = ChatGroup.objects.create(name=self.default_group, created_by=self.user)
        return group

    @database_sync_to_async
    def resolve_group(self, data, create_missing=False):
        if "group_id" not in data and "group" not in data:
            data = {"group_id": self.default_group_id}
        if "group_id" in data:
            group_id = data["group_id"]
            if type(group_id) is not int or group_id <= 0:
                raise ValueError("group_id deve ser um inteiro positivo.")
            group = ChatGroup.objects.filter(pk=group_id).first()
        else:
            name = data.get("group", self.default_group)
            matches = list(ChatGroup.objects.filter(name=name)[:2])
            if len(matches) > 1:
                raise ValueError("Há grupos com este nome. Informe group_id.")
            group = matches[0] if matches else None
            if group is None and create_missing:
                group = ChatGroup.objects.create(name=name, created_by=self.user)
        if group is None:
            raise ValueError("Grupo não encontrado.")
        return group

    @database_sync_to_async
    def add_membership(self, group):
        group.users.add(self.user)

    @database_sync_to_async
    def remove_membership(self, group):
        group.users.remove(self.user)

    @database_sync_to_async
    def saved_groups(self):
        return list(ChatGroup.objects.values("id", "name"))

    async def send_group_status(self, status, group):
        await self.send_json({
            "type": "group_status",
            "status": status,
            "group": group.name,
            "group_id": group.pk,
            "groups": sorted(self.joined_groups),
        })

    async def send_error(self, message):
        await self.send_json({"type": "error", "message": message})

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content))

    @classmethod
    def is_valid_group(cls, group):
        return isinstance(group, str) and cls.valid_group_name.fullmatch(group) is not None

    @staticmethod
    def channel_group_name(group):
        return f"group_chat_{group}"


class PrivateChatConsumer(AsyncWebsocketConsumer):
    """Canal privado entre o usuário autenticado e o usuário da URL."""

    async def connect(self):
        self.user = self.scope["user"]

        if not self.user.is_authenticated:
            await self.close(code=4401)
            return

        username = self.scope["url_route"]["kwargs"]["username"]
        self.recipient = await self.get_user(username)

        if self.recipient is None:
            await self.close(code=4404)
            return

        # Ordenar os ids faz os dois lados entrarem exatamente na mesma sala.
        first_id, second_id = sorted((self.user.pk, self.recipient.pk))
        self.room_group_name = f"private_chat_{first_id}_{second_id}"

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )
        await self.accept()
        await self.send_json({
            "type": "connection",
            "message": "Conversa privada conectada com sucesso!",
            "with": self.recipient.get_username(),
        })

    async def receive(self, text_data=None, bytes_data=None):
        if text_data is None:
            await self.send_error("Envie uma mensagem em JSON válido.")
            return

        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            await self.send_error("Envie uma mensagem em JSON válido.")
            return

        message = data.get("message")
        if not isinstance(message, str) or not message.strip():
            await self.send_error("O campo 'message' é obrigatório.")
            return

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "private.message",
                "message": message,
                "sender": self.user.get_username(),
                "recipient": self.recipient.get_username(),
            },
        )

    async def private_message(self, event):
        await self.send_json({
            "type": "private_message",
            "message": event["message"],
            "sender": event["sender"],
            "recipient": event["recipient"],
        })

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )

    async def send_json(self, content):
        await self.send(text_data=json.dumps(content))

    async def send_error(self, message):
        await self.send_json({"type": "error", "message": message})

    @database_sync_to_async
    def get_user(self, username):
        user_model = get_user_model()
        try:
            return user_model.objects.get(username=username)
        except user_model.DoesNotExist:
            return None
