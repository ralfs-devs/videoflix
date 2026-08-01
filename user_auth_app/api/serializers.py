"""Serializers for the user authentication app.

This module defines DRF serializers for registration, login,
password reset, and token refresh operations. Each serializer
validates incoming request data before passing it to the service layer.

Classes:
    RegisterSerializer: Validates registration data and creates users.
    LoginSerializer: Extends SimpleJWT TokenObtainPairSerializer with
        email-based authentication and user activity checks.
    PasswordResetRequestSerializer: Validates email for password reset.
    PasswordResetConfirmSerializer: Validates new password confirmation.
    TokenRefreshSerializer: Placeholder serializer for token refresh.
    UserSerializer: Read-only serializer for user representation.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from user_auth_app.services import UserService

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """Serializer for user registration requests.

    Validates that passwords match and that no duplicate email exists,
    then delegates user creation to the UserService.

    Attributes:
        email (EmailField): The user's email address.
        password (CharField): The chosen password (write-only).
        confirmed_password (CharField): Password confirmation (write-only).
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, required=True, min_length=8)
    confirmed_password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        """Validate that passwords match and email is unique.

        Args:
            attrs (dict): The deserialized input data.

        Returns:
            dict: The validated data.

        Raises:
            serializers.ValidationError: If passwords differ or email exists.
        """
        if attrs['password'] != attrs['confirmed_password']:
            raise serializers.ValidationError(
                {'confirmed_password': 'Passwords do not match.'}
            )

        email = attrs.get('email')
        if User.objects.filter(username=email).exists():
            raise serializers.ValidationError(
                {'email': 'A user with this email already exists.'}
            )

        return attrs

    def create(self, validated_data):
        """Create a new inactive user via UserService.

        Args:
            validated_data (dict): The validated registration data.

        Returns:
            User: The newly created inactive user instance.
        """
        password = validated_data.pop('password')
        user = UserService.create_inactive_user(
            validated_data['email'], password)
        return user


class LoginSerializer(serializers.Serializer):
    """Custom login serializer that accepts email and password.

    Unlike SimpleJWT's default TokenObtainPairSerializer, this custom
    serializer allows users to authenticate using their email address
    instead of username. This aligns with our User model where the
    email is stored as the username field.

    After validation, JWT access and refresh tokens are generated
    directly within the serializer for use in the LoginView.

    Attributes:
        email (EmailField): The user's email address for authentication.
        password (CharField): The user's password (write-only).
    """

    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        """Authenticate user using email and password.

        Performs the following validation steps:
        1. Finds the user by email address.
        2. Checks if the account is active.
        3. Verifies the password hash.
        4. Generates JWT access and refresh tokens.

        Args:
            attrs (dict): The deserialized input data containing
                'email' and 'password' fields.

        Returns:
            dict: A dictionary containing:
                - 'access': JWT access token (string)
                - 'refresh': JWT refresh token (string)
                - 'user': User information dict with 'id' and 'username'

        Raises:
            serializers.ValidationError: If user not found, account inactive,
                or password does not match.
        """
        email = attrs.get('email')
        password = attrs.get('password')

        user = UserService.find_user_by_email(email)

        if not user:
            raise serializers.ValidationError(
                {'email': 'Invalid credentials.'})

        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'Please activate your account first.'
            })

        if not user.check_password(password):
            raise serializers.ValidationError({
                'password': 'Invalid credentials.'
            })

        # Generate JWT tokens
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)

        attrs['access'] = str(refresh.access_token)
        attrs['refresh'] = str(refresh)
        attrs['user'] = {
            'id': user.id,
            'username': user.username,
        }

        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Serializer for password reset request emails.

    Validates that a user with the given email exists before
    triggering the reset flow.

    Attributes:
        email (EmailField): The email address to send the reset link to.
    """

    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """Check that a user exists for the given email.

        Args:
            value (str): The email address to validate.

        Returns:
            str: The validated email address.

        Raises:
            serializers.ValidationError: If no user is found.
        """
        user = UserService.find_user_by_email(value)
        if not user:
            raise serializers.ValidationError('No user found with this email.')
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer for confirming a new password during reset.

    Validates that the new password and its confirmation match.

    Attributes:
        new_password (CharField): The new password (write-only).
        confirm_password (CharField): Password confirmation (write-only).
    """

    new_password = serializers.CharField(
        write_only=True, required=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, required=True)

    def validate(self, attrs):
        """Validate that the new passwords match.

        Args:
            attrs (dict): The deserialized input data.

        Returns:
            dict: The validated data.

        Raises:
            serializers.ValidationError: If the passwords do not match.
        """
        if attrs['new_password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Passwords do not match.'}
            )
        return attrs


class TokenRefreshSerializer(serializers.Serializer):
    """Placeholder serializer for token refresh requests.

    The actual refresh token is read from the HTTP-only cookie,
    so no body fields are required.
    """
    pass


class UserSerializer(serializers.ModelSerializer):
    """Read-only serializer for user representation.

    Used in responses where user data is returned without
    exposing sensitive fields.

    Attributes:
        id (int): The user's primary key.
        username (str): The user's username (email address).
        email (str): The user's email address.
    """

    class Meta:
        model = User
        fields = ['id', 'username', 'email']
        read_only_fields = ['id', 'username', 'email']
