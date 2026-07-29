from user_auth_app.models import User
from rest_framework_simplejwt.views import TokenObtainPairView
from user_auth_app.api.serializers import CustomTokenObtainPairSerializer


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
