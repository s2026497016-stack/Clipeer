from .base import Publisher


class InstagramPublisher(Publisher):
    platform = "instagram"

    def publish(self, account, path, **kwargs):
        from .. import accounts
        return accounts.instagram_upload(account, path, kwargs["caption"], kwargs.get("job_id", ""))

    def refresh(self, account):
        from ..accounts import _ig_token
        _ig_token(account)
        return account
