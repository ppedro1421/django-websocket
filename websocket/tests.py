from asgiref.sync import async_to_sync
from channels.auth import AuthMiddlewareStack
from channels.routing import URLRouter
from channels.testing import WebsocketCommunicator
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from config.asgi import application
from websocket.routing import websocket_urlpatterns


TEST_CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class GroupChatConsumerTests(TransactionTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.maria = user_model.objects.create_user("maria", password="secret123")
        self.joao = user_model.objects.create_user("joao", password="secret123")
        self.ana = user_model.objects.create_user("ana", password="secret123")

    @staticmethod
    def communicator(user):
        token = str(AccessToken.for_user(user))
        return WebsocketCommunicator(
            application,
            "/ws/group-text/",
            headers=[(b"authorization", f"Bearer {token}".encode())],
        )

    def test_message_is_sent_to_every_connected_user(self):
        async_to_sync(self._test_message_is_sent_to_every_connected_user)()

    async def _test_message_is_sent_to_every_connected_user(self):
        first_user = self.communicator(self.maria)
        second_user = self.communicator(self.joao)

        try:
            first_connected, _ = await first_user.connect()
            second_connected, _ = await second_user.connect()

            self.assertTrue(first_connected)
            self.assertTrue(second_connected)

            connection = await first_user.receive_json_from()
            await second_user.receive_json_from()

            await first_user.send_json_to({
                "username": "nome-falso",
                "message": "   /\\\n  /__\\",
            })

            expected_message = {
                "group_id": connection["groups"][0],
                "type": "message",
                "username": "maria",
                "message": "   /\\\n  /__\\",
                "group": "geral",
            }

            self.assertEqual(await first_user.receive_json_from(), expected_message)
            self.assertEqual(await second_user.receive_json_from(), expected_message)
        finally:
            await first_user.disconnect()
            await second_user.disconnect()

    def test_one_connection_can_join_multiple_groups(self):
        async_to_sync(self._test_one_connection_can_join_multiple_groups)()

    async def _test_one_connection_can_join_multiple_groups(self):
        multi_group_user = self.communicator(self.maria)
        dev_user = self.communicator(self.joao)
        news_user = self.communicator(self.ana)

        try:
            for communicator in (multi_group_user, dev_user, news_user):
                connected, _ = await communicator.connect()
                self.assertTrue(connected)
                await communicator.receive_json_from()

            for communicator, group in (
                (multi_group_user, "dev"),
                (multi_group_user, "news"),
                (dev_user, "dev"),
                (news_user, "news"),
            ):
                await communicator.send_json_to({"action": "join", "group": group})
                response = await communicator.receive_json_from()
                self.assertEqual(response["status"], "joined")
                if group == "dev":
                    dev_group_id = response["group_id"]

            await multi_group_user.send_json_to({
                "action": "message",
                "group": "dev",
                "username": "nome-falso",
                "message": "Mensagem para dev",
            })

            expected = {
                "group_id": dev_group_id,
                "type": "message",
                "group": "dev",
                "username": "maria",
                "message": "Mensagem para dev",
            }
            self.assertEqual(await multi_group_user.receive_json_from(), expected)
            self.assertEqual(await dev_user.receive_json_from(), expected)
            self.assertTrue(await news_user.receive_nothing(timeout=0.1))

            await multi_group_user.send_json_to({"action": "leave", "group": "dev"})
            response = await multi_group_user.receive_json_from()
            self.assertEqual(response["status"], "left")

            await dev_user.send_json_to({
                "group": "dev",
                "username": "João",
                "message": "Ainda no grupo",
            })
            self.assertTrue(await multi_group_user.receive_nothing(timeout=0.1))
        finally:
            await multi_group_user.disconnect()
            await dev_user.disconnect()
            await news_user.disconnect()


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class PrivateChatConsumerTests(TransactionTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.maria = user_model.objects.create_user("maria", password="secret123")
        self.joao = user_model.objects.create_user("joao", password="secret123")
        self.ana = user_model.objects.create_user("ana", password="secret123")
        self.private_application = AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )

    def communicator(self, user, recipient):
        communicator = WebsocketCommunicator(
            self.private_application,
            f"/ws/private/{recipient}/",
        )
        communicator.scope["user"] = user
        return communicator

    def test_message_is_received_only_by_the_private_room(self):
        async_to_sync(self._test_message_is_received_only_by_the_private_room)()

    async def _test_message_is_received_only_by_the_private_room(self):
        maria = self.communicator(self.maria, "joao")
        joao = self.communicator(self.joao, "maria")
        ana = self.communicator(self.ana, "maria")

        try:
            for communicator in (maria, joao, ana):
                connected, _ = await communicator.connect()
                self.assertTrue(connected)
                await communicator.receive_json_from()

            await maria.send_json_to({
                "message": "   /\\\n  /__\\",
                "username": "ana",
            })

            expected = {
                "type": "private_message",
                "sender": "maria",
                "recipient": "joao",
                "message": "   /\\\n  /__\\",
            }
            self.assertEqual(await maria.receive_json_from(), expected)
            self.assertEqual(await joao.receive_json_from(), expected)
            self.assertTrue(await ana.receive_nothing(timeout=0.1))
        finally:
            await maria.disconnect()
            await joao.disconnect()
            await ana.disconnect()

    def test_anonymous_user_is_rejected(self):
        async_to_sync(self._test_anonymous_user_is_rejected)()

    async def _test_anonymous_user_is_rejected(self):
        communicator = WebsocketCommunicator(
            self.private_application,
            "/ws/private/joao/",
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)

    def test_unknown_recipient_is_rejected(self):
        async_to_sync(self._test_unknown_recipient_is_rejected)()

    async def _test_unknown_recipient_is_rejected(self):
        communicator = self.communicator(self.maria, "inexistente")
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4404)


@override_settings(CHANNEL_LAYERS=TEST_CHANNEL_LAYERS)
class JWTAuthenticationTests(TransactionTestCase):
    def setUp(self):
        user_model = get_user_model()
        self.maria = user_model.objects.create_user("maria", password="secret123")
        self.joao = user_model.objects.create_user("joao", password="secret123")

    def test_token_obtain_refresh_and_verify(self):
        client = APIClient()
        response = client.post(
            "/api/token/",
            {"username": "maria", "password": "secret123"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        verify_response = client.post(
            "/api/token/verify/",
            {"token": response.data["access"]},
            format="json",
        )
        self.assertEqual(verify_response.status_code, 200)

        refresh_response = client.post(
            "/api/token/refresh/",
            {"refresh": response.data["refresh"]},
            format="json",
        )
        self.assertEqual(refresh_response.status_code, 200)
        self.assertIn("access", refresh_response.data)

    def test_private_websocket_accepts_bearer_token(self):
        async_to_sync(self._test_private_websocket_accepts_bearer_token)()

    async def _test_private_websocket_accepts_bearer_token(self):
        token = str(AccessToken.for_user(self.maria))
        communicator = WebsocketCommunicator(
            application,
            "/ws/private/joao/",
            headers=[(b"authorization", f"Bearer {token}".encode())],
        )
        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            response = await communicator.receive_json_from()
            self.assertEqual(response["with"], "joao")
        finally:
            await communicator.disconnect()

    def test_private_websocket_accepts_query_string_token(self):
        async_to_sync(self._test_private_websocket_accepts_query_string_token)()

    async def _test_private_websocket_accepts_query_string_token(self):
        token = str(AccessToken.for_user(self.maria))
        communicator = WebsocketCommunicator(
            application,
            f"/ws/private/joao/?access_token={token}",
        )
        try:
            connected, _ = await communicator.connect()
            self.assertTrue(connected)
            response = await communicator.receive_json_from()
            self.assertEqual(response["with"], "joao")
        finally:
            await communicator.disconnect()

    def test_private_websocket_rejects_invalid_token(self):
        async_to_sync(self._test_private_websocket_rejects_invalid_token)()

    async def _test_private_websocket_rejects_invalid_token(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/private/joao/?access_token=invalid-token",
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4401)
