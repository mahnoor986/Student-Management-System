from rest_framework.authentication import SessionAuthentication


class SessionAuthenticationWithChallenge(SessionAuthentication):
    """Use a 401 response for anonymous API requests while retaining CSRF checks."""

    def authenticate_header(self, request):
        return 'Session'
