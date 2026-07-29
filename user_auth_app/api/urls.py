from django.urls import path
from user_auth_app.api.views import CustomTokenObtainPairView

urlpatterns = [
    path('login/', CustomTokenObtainPairView.as_view(),
         name='token_obtain_pair'),
]
