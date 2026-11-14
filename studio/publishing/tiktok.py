from .base import Publisher


class TikTokPublisher(Publisher):
    platform = "tiktok"

    def publish(self, account, path, **kwargs):
        from .. import accounts
        return accounts.tiktok_upload(account, path, kwargs["caption"], kwargs.get("privacy", "public"))

    def refresh(self, account):
        from ..accounts import _tt_token
        _tt_token(account)
        return account
