from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_protect
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .access import get_role


def user_data(user):
    return {
        'username': user.get_username(),
        'display_name': user.get_full_name() or user.get_username(),
        'is_staff': user.is_staff,
        'role': get_role(user),
    }


@method_decorator(ensure_csrf_cookie, name='dispatch')
class CSRFTokenView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        return Response({'csrfToken': get_token(request)})


@method_decorator(csrf_protect, name='dispatch')
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'login'

    def post(self, request):
        if not isinstance(request.data, dict):
            return Response({'detail': 'Enter a username and password.'}, status=status.HTTP_400_BAD_REQUEST)
        username = request.data.get('username', '')
        password = request.data.get('password', '')
        if not isinstance(username, str) or not isinstance(password, str) or not username.strip() or not password:
            return Response({'detail': 'Enter a username and password.'}, status=status.HTTP_400_BAD_REQUEST)
        username = username.strip()
        user = authenticate(request=request, username=username, password=password)
        if user is None:
            return Response({'detail': 'Invalid username or password.'}, status=status.HTTP_401_UNAUTHORIZED)
        login(request, user)
        return Response({'user': user_data(user)}, status=status.HTTP_200_OK)


@method_decorator(csrf_protect, name='dispatch')
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordChangeView(APIView):
    """Signed-in users change their own password (audit finding M4).

    Requires the current password; the new one must pass Django's password validators.
    CSRF is enforced by session authentication. Other sessions of the user are signed out
    (their session hash no longer matches); this session stays signed in.
    """
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'password_change'

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        current, new = data.get('current_password'), data.get('new_password')
        if not isinstance(current, str) or not isinstance(new, str) or not current or not new:
            return Response({'detail': 'Enter your current password and a new password.'}, status=status.HTTP_400_BAD_REQUEST)
        user = request.user
        if not user.check_password(current):
            return Response({'current_password': ['Your current password is incorrect.']}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_password(new, user)
        except DjangoValidationError as error:
            return Response({'new_password': list(error.messages)}, status=status.HTTP_400_BAD_REQUEST)
        user.set_password(new)
        user.save(update_fields=['password'])
        update_session_auth_hash(request, user)
        return Response({'detail': 'Password changed.'})


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'user': user_data(request.user)})
