from django.urls import path
from user_auth_app.api.views import (
    LoginView,
    RegisterView,
    ActivationView,
    LogoutView,
    TokenRefreshView,
    PasswordResetRequestView,
    PasswordResetConfirmView
)

urlpatterns = [
    path('register/', RegisterView.as_view(),
         name='Registration'),
    path('activate/<uidb64>/<token>/', ActivationView.as_view(),
         name='Activation'),
    path('login/', LoginView.as_view(),
         name='Login'),
    path('logout/', LogoutView.as_view(),
         name='Logout'),
    path('token/refresh/', TokenRefreshView.as_view(),
         name='Token_Refresh'),
    path('password_reset/', PasswordResetRequestView.as_view(),
         name='PW_Reset_Request'),
    path('password_confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(),
         name='PW_Reset_Confirm'),
]
