"""Views for the user authentication app.

This module defines API views for registration, account activation,
login, logout, token refresh, and password reset. All views use
DRF's APIView and delegate business logic to the service layer.

Classes:
    RegisterView: Handles user registration and activation email.
    ActivateView: Handles account activation via email link.
    LoginView: Authenticates users using SimpleJWT and sets JWT cookies.
    LogoutView: Blacklists refresh token and clears cookies.
    TokenRefreshView: Issues a new access token from a refresh cookie.
    PasswordResetRequestView: Sends a password reset email.
    PasswordResetConfirmView: Confirms and applies a new password.
"""

from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from user_auth_app.api.serializers import (
    LoginSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
)
from user_auth_app.services import UserService


class RegisterView(APIView):
    """API view for user registration.

    Accepts email and password, creates an inactive user,
    and sends an activation email.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Handle POST request for user registration.

        Args:
            request (Request): The HTTP request containing registration data.

        Returns:
            Response: 201 with user info on success, 400 on validation error.
        """
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        uidb64, token = UserService.generate_activation_token(user)
        UserService.send_activation_email(user, uidb64, token)

        return Response({
            'user': {'id': user.id, 'email': user.email},
            'message': 'Registration successful. Please check your email.'
        }, status=status.HTTP_201_CREATED)


class ActivationView(APIView):
    """API view for account activation.

    Activates a user account using the UID and token from the
    activation email link.
    """

    permission_classes = [AllowAny]

    def get(self, request, uidb64, token):
        """Handle GET request for account activation.

        Args:
            request (Request): The HTTP request.
            uidb64 (str): Base64-encoded user ID from the URL.
            token (str): Activation token from the URL.

        Returns:
            Response: 200 on success, 400 on invalid or expired token.
        """
        try:
            user = UserService.decode_uidb64(uidb64)
        except ObjectDoesNotExist:
            return Response(
                {'detail': 'Activation failed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user and default_token_generator.check_token(user, token):
            UserService.activate_user(user)
            return Response(
                {'detail': 'Account successfully activated.'},
                status=status.HTTP_200_OK
            )

        return Response(
            {'detail': 'Activation failed.'},
            status=status.HTTP_400_BAD_REQUEST
        )


class LoginView(APIView):
    """API view for user login using SimpleJWT.

    Authenticates a user using the LoginSerializer (which extends
    TokenObtainPairSerializer) and sets HttpOnly cookies containing
    the JWT access and refresh tokens.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Handle POST request for user login.

        Uses SimpleJWT's TokenObtainPairSerializer internally via our custom
        LoginSerializer. Sets access and refresh tokens as HttpOnly cookies.
        The response body includes user information but not the raw tokens.

        Args:
            request (Request): The HTTP request containing credentials.

        Returns:
            Response: 200 with user info and cookies on success,
                400 on invalid credentials or inactive account.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data
        access_token = validated_data['access']
        refresh_token = validated_data['refresh']
        user_info = validated_data['user']

        response = Response({
            'detail': 'Login successful',
            'user': user_info
        }, status=status.HTTP_200_OK)

        response.set_cookie(
            'access_token', access_token, httponly=True, max_age=900
        )
        response.set_cookie(
            'refresh_token', refresh_token, httponly=True, max_age=604800
        )

        return response


class LogoutView(APIView):
    """API view for user logout.

    Blacklists the refresh token and deletes both JWT cookies.
    Requires a valid refresh token cookie.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Handle POST request for user logout.

        Args:
            request (Request): The HTTP request with refresh cookie.

        Returns:
            Response: 200 on success, 400 if refresh token is missing.
        """
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token missing.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()

            response = Response(
                {'detail': 'Logout successful! All tokens will be deleted.'},
                status=status.HTTP_200_OK
            )
            response.delete_cookie('access_token')
            response.delete_cookie('refresh_token')

            return response
        except TokenError:
            return Response(
                {'detail': 'Logout failed.'},
                status=status.HTTP_400_BAD_REQUEST
            )


class TokenRefreshView(APIView):
    """API view for refreshing access tokens.

    Reads the refresh token from the HttpOnly cookie and
    issues a new access token if the refresh token is valid.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Handle POST request for token refresh.

        Args:
            request (Request): The HTTP request with refresh cookie.

        Returns:
            Response: 200 with new access cookie on success,
                400 if cookie missing, 401 on invalid token.
        """
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token missing.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            token = RefreshToken(refresh_token)
            new_access_token = str(token.access_token)

            response = Response(
                {'detail': 'Token refreshed'},
                status=status.HTTP_200_OK
            )
            response.set_cookie(
                'access_token', new_access_token, httponly=True, max_age=900
            )

            return response
        except TokenError:
            return Response(
                {'detail': 'Invalid refresh token.'},
                status=status.HTTP_401_UNAUTHORIZED
            )


class PasswordResetRequestView(APIView):
    """API view for requesting a password reset email.

    Validates the email and sends a password reset link
    if the user exists.
    """

    permission_classes = [AllowAny]

    def post(self, request):
        """Handle POST request for password reset email.

        Args:
            request (Request): The HTTP request containing the email.

        Returns:
            Response: 200 with confirmation message regardless of whether
                the email exists (prevents user enumeration).
        """
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.find_user_by_email(
            serializer.validated_data['email'])
        if user:
            uidb64, token = UserService.generate_password_reset_token(user)
            UserService.send_password_reset_email(user, uidb64, token)

        return Response(
            {'detail': 'An email has been sent to reset your password.'},
            status=status.HTTP_200_OK
        )


class PasswordResetConfirmView(APIView):
    """API view for confirming a password reset.

    Validates the reset token and applies the new password
    if the token is valid.
    """

    permission_classes = [AllowAny]

    def post(self, request, uidb64, token):
        """Handle POST request for password reset confirmation.

        Args:
            request (Request): The HTTP request containing new passwords.
            uidb64 (str): Base64-encoded user ID from the URL.
            token (str): Password reset token from the URL.

        Returns:
            Response: 200 on success, 400 on invalid token or mismatched passwords.
        """
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = UserService.decode_uidb64(uidb64)

        if not user or not default_token_generator.check_token(user, token):
            return Response(
                {'detail': 'Password reset failed.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        UserService.reset_user_password(
            user, serializer.validated_data['new_password']
        )

        return Response(
            {'detail': 'Your Password has been successfully reset.'},
            status=status.HTTP_200_OK
        )
