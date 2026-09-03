from asgiref.sync import async_to_sync
from channels.testing import WebsocketCommunicator
from django.test import SimpleTestCase

from config.asgi import application


class TestConsumerTests(SimpleTestCase):

    def test_message_is_sent_to_every_connected_user(self):
        async_to_sync(self._test_message_is_sent_to_every_connected_user)()

    async def _test_message_is_sent_to_every_connected_user(self):
        first_user = WebsocketCommunicator(application, "/ws/test/")
        second_user = WebsocketCommunicator(application, "/ws/test/")

        try:
            first_connected, _ = await first_user.connect()
            second_connected, _ = await second_user.connect()

            self.assertTrue(first_connected)
            self.assertTrue(second_connected)

            await first_user.receive_json_from()
            await second_user.receive_json_from()

            await first_user.send_json_to({
                "username": "Maria",
                "message": "Olá, pessoal!",
            })

            expected_message = {
                "type": "message",
                "username": "Maria",
                "message": "Olá, pessoal!",
            }

            self.assertEqual(await first_user.receive_json_from(), expected_message)
            self.assertEqual(await second_user.receive_json_from(), expected_message)
        finally:
            await first_user.disconnect()
            await second_user.disconnect()
