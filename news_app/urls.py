from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    UserRegistrationAPIView,
    UserLoginAPIView,
    UserSearchHistoryAPIView,
    AdvancedNewsSearchAPIView,
    UserListAPIView,
    UserManagementAPIView,
    TopKeywordsAPIView
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
"""
API URL Configuration

This module defines the URL routing for the news search and user management API.
URLs are organized into logical groups: authentication, token management,
search functionality, and user administration.
"""


urlpatterns = [

    # Authentication endpoints
    path('auth/register/', UserRegistrationAPIView.as_view(), name='user-register'),
    path('auth/login/', UserLoginAPIView.as_view(), name='user-login'),

    # JWT token management
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # News search functionality
    path('search/advanced/', AdvancedNewsSearchAPIView.as_view(), name='advanced-search'),
    path('user/search-history/', UserSearchHistoryAPIView.as_view(), name='user-search-history'),

    # User administration (staff only)
    path('user/list/', UserListAPIView.as_view(), name='user-list'),
    path('user/update/', UserManagementAPIView.as_view(), name='user-status-update'),

    # Analytics (staff only)
    path('keywords/top/', TopKeywordsAPIView.as_view(), name='top-keywords'),
] 