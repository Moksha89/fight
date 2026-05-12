import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()

class UserConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        self.user = user
        self.group_name = f"user_{self.user.id}_wallet"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Optional: send initial wallet data on connect
        wallet = await self.get_wallet_data()
        await self.send(text_data=json.dumps({
            'type': 'wallet_update',
            **wallet
        }))

    @database_sync_to_async
    def get_wallet_data(self):
        wallet = self.user.wallet
        return {
            'balance': str(wallet.balance),
            'bonusDebt': str(wallet.bonusDebt),
            'updated_at': wallet.updated_at.isoformat(),
        }

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)


    async def send_wallet_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'wallet_update',
            'balance': event['balance'],
            'bonusDebt': event['bonusDebt'],
            'updated_at': event['updated_at'],
        }))
