class UserCancelledError(BaseException):
    def __init__(self, *args):
        super().__init__(*args)

class DownloadError(BaseException):
    def __init__(self, *args):
        super().__init__(*args)

class ServerStateError(BaseException):
    def __init__(self, *args):
        super().__init__(*args)

class NoVersionFoundError(BaseException):
    def __init__(self, *args):
        super().__init__(*args)