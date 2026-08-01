from django.urls import path
from user_auth_app.api.views import LoginView, RegisterView

urlpatterns = [
    path('register/', RegisterView.as_view(),
         name='Registration'),
    path('login/', LoginView.as_view(),
         name='Login'),
]
