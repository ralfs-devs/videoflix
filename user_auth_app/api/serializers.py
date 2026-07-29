from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['user'] = {'id': self.user.id, 'username': self.user.username}
        return data
