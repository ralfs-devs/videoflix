"""Service layer for user authentication and token management.

This module provides business logic for user registration, activation,
login, logout, password reset, and JWT token operations. It separates
the application logic from the views and serializers to keep them slim.

Classes:
    UserService: Handles user-related operations like creation, activation,
        credential verification, and password reset.
    TokenService: Handles JWT token operations like refreshing and validation.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.conf import settings

from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from user_auth_app.email_templates import activation, password_reset

from email.mime.image import MIMEImage
import os

LOGO_PATH = os.path.join(
    settings.BASE_DIR,
    'user_auth_app',
    'email_templates',
    'logo.svg'
)
User = get_user_model()


class UserService:
    """Provides user-related business logic.

    This class encapsulates all operations related to user creation,
    activation, credential verification, and password management.
    """

    @staticmethod
    def create_inactive_user(email, password):
        """Create a new inactive user account.

        Args:
            email (str): The email address used as username.
            password (str): The plain-text password for the account.

        Returns:
            User: The newly created inactive user instance.
        """
        user = User.objects.create_user(username=email, password=password)
        user.is_active = False
        user.save()
        return user

    @staticmethod
    def find_user_by_email(email):
        """Retrieve a user by email (stored as username).

        Args:
            email (str): The email address to search for.

        Returns:
            User or None: The matching user instance, or None if not found.
        """
        try:
            return User.objects.get(username=email)
        except User.DoesNotExist:
            return None

    @staticmethod
    def generate_activation_token(user):
        """Generate an activation token and base64-encoded user ID.

        Args:
            user (User): The user instance to generate a token for.

        Returns:
            tuple: A tuple containing (uidb64, token) as strings.
        """
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uidb64, token

    @staticmethod
    def send_activation_email(user, uidb64, token):
        activation_url = f"http://localhost:8000/api/activate/{uidb64}/{token}"

        html = activation.render_activation_html(
            user_email=user.username,
            activation_url=activation_url
        )

        email = EmailMultiAlternatives(
            subject='Activate your account',
            body='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.username],
        )
        email.attach_alternative(html, "text/html")

        with open(LOGO_PATH, 'rb') as img:
            logo = MIMEImage(img.read(), _subtype='svg+xml')
            logo.add_header('Content-ID', '<logo_cid>')
            email.attach(logo)

        email.send(fail_silently=False)

    @staticmethod
    def activate_user(user):
        """Activate a user account by setting is_active to True.

        Args:
            user (User): The user instance to activate.

        Returns:
            bool: Always returns True after activation.
        """
        user.is_active = True
        user.save()
        return True

    @staticmethod
    def generate_jwt_tokens(user):
        """Generate JWT access and refresh tokens for a user.

        Args:
            user (User): The authenticated user instance.

        Returns:
            tuple: A tuple containing (access_token, refresh_token) as strings.
        """
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token), str(refresh)

    @staticmethod
    def verify_credentials(user, password):
        """Verify a user's password against the stored hash.

        Args:
            user (User): The user instance to check.
            password (str): The plain-text password to verify.

        Returns:
            bool: True if the password matches, False otherwise.
        """
        return user.check_password(password)

    @staticmethod
    def blacklist_refresh_token(refresh_token_string):
        """Blacklist a refresh token to invalidate it.

        Args:
            refresh_token_string (str): The refresh token to blacklist.

        Returns:
            bool: True if blacklisting succeeded, False if the token is invalid.
        """
        try:
            token = RefreshToken(refresh_token_string)
            token.blacklist()
            return True
        except TokenError:
            return False

    @staticmethod
    def generate_password_reset_token(user):
        """Generate a password reset token and base64-encoded user ID.

        Args:
            user (User): The user instance to generate a reset token for.

        Returns:
            tuple: A tuple containing (uidb64, token) as strings.
        """
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        return uidb64, token

    @staticmethod
    def send_password_reset_email(user, uidb64, token):
        reset_url = f"http://localhost:8000/api/reset-password/{uidb64}/{token}"

        html = password_reset.render_password_reset_html(
            reset_url=reset_url
        )

        email = EmailMultiAlternatives(
            subject='Reset your password',
            body='',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.username],
        )
        email.attach_alternative(html, "text/html")

        with open(LOGO_PATH, 'rb') as img:
            logo = MIMEImage(img.read(), _subtype='svg+xml')
            logo.add_header('Content-ID', '<logo_cid>')
            email.attach(logo)

        email.send(fail_silently=False)

    @staticmethod
    def decode_uidb64(uidb64):
        """Decode a base64-encoded user ID and retrieve the user.

        Args:
            uidb64 (str): The base64-encoded user ID.

        Returns:
            User or None: The matching user instance, or None if decoding
                fails or the user does not exist.
        """
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            return User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None


class TokenService:
    """Provides JWT token-related operations.

    This class handles token refreshing and validation,
    separating token logic from user management.
    """

    @staticmethod
    def refresh_access_token(refresh_token_string):
        """Generate a new access token from a valid refresh token.

        Args:
            refresh_token_string (str): A valid refresh token.

        Returns:
            str: A new access token as a string.

        Raises:
            TokenError: If the refresh token is invalid or expired.
        """
        token = RefreshToken(refresh_token_string)
        return str(token.access_token)

    @staticmethod
    def validate_refresh_token(refresh_token_string):
        """Validate whether a refresh token is still usable.

        Args:
            refresh_token_string (str): The refresh token to validate.

        Returns:
            bool: True if the token is valid, False otherwise.
        """
        try:
            RefreshToken(refresh_token_string)
            return True
        except TokenError:
            return False
