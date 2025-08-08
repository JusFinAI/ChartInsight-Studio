class KiwoomException(Exception):
    """키움 API 예외의 기본 클래스"""
    pass


class AuthenticationError(KiwoomException):
    """인증 관련 예외"""
    pass


class APIRequestError(KiwoomException):
    """API 요청 실패 예외"""
    def __init__(self, message, status_code=None, response=None):
        self.status_code = status_code
        self.response = response
        super().__init__(message)


class ResponseParsingError(KiwoomException):
    """응답 파싱 실패 예외"""
    pass


class RateLimitError(KiwoomException):
    """요청 제한 초과 예외"""
    pass 