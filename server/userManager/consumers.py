import json
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from kokoroko.ws_protection import ProtectedConsumer

User = get_user_model()


class UserConsumer(ProtectedConsumer):
    async def on_connect(self):
        self.user = self.scope["user"]
        self.group_name = f"user_{self.user.id}_wallet"
        await self.channel_layer.group_add(self.group_name, self.channel_name)

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

    async def on_disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def send_wallet_update(self, event):
        await self.send(text_data=json.dumps({
            'type': 'wallet_update',
            'balance': event['balance'],
            'bonusDebt': event['bonusDebt'],
            'updated_at': event['updated_at'],
        }))
