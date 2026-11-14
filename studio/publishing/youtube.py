from .base import Publisher


class YouTubePublisher(Publisher):
    platform = "youtube"

    def publish(self, account, path, **kwargs):
        from .. import accounts
        return accounts.youtube_upload(account, path, kwargs["title"], kwargs["description"],
                                      kwargs.get("tags", []), kwargs.get("privacy", "private"))

    def refresh(self, account):
        from ..accounts import _yt_token
        _yt_token(account)
        return account
