class UserCancelledError(BaseException):
    def __init__(self, *args):
        super().__init__(*args)

class DownloadError(BaseException):
    def __init__(self, *args):
        super().__init__(*args)