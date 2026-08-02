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
from django.core.mail import send_mail
from django.conf import settings

from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

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
        """Send an account activation email to the user.

        Args:
            user (User): The user instance to send the email to.
            uidb64 (str): The base64-encoded user ID.
            token (str): The activation token.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        activation_link = (
            f"{settings.CSRF_TRUSTED_ORIGINS[0]}"
            f"/api/activate/{uidb64}/{token}/"
        )
        try:
            send_mail(
                subject='Activate your account',
                message=(
                    f'Click the link to activate your account: '
                    f'{activation_link}'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.username],
                fail_silently=False,
            )
            return True
        except Exception:
            return False

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
        """Send a password reset email to the user.

        Args:
            user (User): The user instance to send the email to.
            uidb64 (str): The base64-encoded user ID.
            token (str): The password reset token.

        Returns:
            bool: True if the email was sent successfully, False otherwise.
        """
        reset_link = (
            f"{settings.CSRF_TRUSTED_ORIGINS[0]}"
            f"/api/password_confirm/{uidb64}/{token}/"
        )
        try:
            send_mail(
                subject='Reset your password',
                message=(
                    f'Click the link to reset your password: '
                    f'{reset_link}'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.username],
                fail_silently=False,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def reset_user_password(user, new_password):
        """Set a new password for a user 
           and confirm the change of the Password via E-Mail

        Args:
            user (User): The user instance to update.
            new_password (str): The new plain-text password.

        Returns:
            bool: Always returns True after the password is set.
        """
        user.set_password(new_password)
        user.save()

        try:
            send_mail(
                subject='Password Changed Successfully',
                message=(
                    f'Hello,\n\n'
                    f'Your password for the Videoflix account '
                    f'(email: {user.username}) was successfully reset on '
                    f'{timezone.now().strftime("%d.%m.%Y at %H:%M UTC")}.\n\n'
                    f'If this was not you, please contact support immediately.\n\n'
                    f'The Videoflix Team'
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.username],
                fail_silently=False,
            )
            return True
        except Exception:
            return False

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
