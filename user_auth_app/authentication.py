
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed


class JWTCookieAuthentication(JWTAuthentication):
    """
    Reads JWT from 'Authorization' header OR 'access_token' cookie.
    """

    def get_raw_token(self, header):
        # 1. Erst Header prüfen (Standard-Verhalten)
        if header is not None:
            return super().get_raw_token(header)

        # 2. Dann Cookie prüfen
        access_token = self.request.COOKIES.get('access_token')
        if not access_token:
            return None

        return access_token

    def authenticate(self, request):
        # Setze self.request für die Dauer der Authentifizierung
        self.request = request

        # Header-first, dann Cookie
        header_value = self.get_header(request)

        # Erst im Header suchen
        if header_value is not None:
            raw_token = self.get_raw_token(header_value)
            if raw_token:
                try:
                    validated_token = self.get_validated_token(raw_token)
                    user = self.get_user(validated_token)
                    return (user, validated_token)
                except Exception as exc:
                    raise AuthenticationFailed(str(exc))

        # Dann im Cookie suchen
        access_token = request.COOKIES.get('access_token')
        if not access_token:
            return None

        try:
            validated_token = self.get_validated_token(access_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except Exception as exc:
            raise AuthenticationFailed(str(exc))
