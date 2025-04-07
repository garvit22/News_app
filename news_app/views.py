
from django.utils import timezone
from datetime import timedelta, datetime
import requests
import traceback
from django.conf import settings
from .models import SearchKeyword, Article, UserQuota
from rest_framework import  status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Count
from django.utils import timezone
from .serializers import (
    ArticleSerializer, NewsSearchSerializer, UserRegistrationSerializer, UserListSerializer, UserStatusUpdateSerializer, TopKeywordsSerializer
)
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.contrib.auth.models import User

class AdvancedNewsSearchAPIView(APIView):

    """
    API view for searching news articles 
    This endpoint allows authenticated users to search for news articles
    using keywords and multiple filters. It implements quota tracking,
    caching of recent searches, and refresh capabilities for updated results.
    Request Body:
        - keyword (str): Required search term
        - source_name (str, optional): Filter by news source (e.g., 'BBC News')
        - language (str, optional): Filter by language code (e.g., 'en')
        - start_date (date, optional): Filter for articles published on or after this date
        - end_date (date, optional): Filter for articles published on or before this date
    Responses:
        - 200 OK: Successful search, returns articles matching criteria
        - 400 BAD REQUEST: Invalid search parameters or API error
        - 403 FORBIDDEN: User has reached their quota limit
    Notes:
        - Searches are cached for 15 minutes to prevent redundant API calls
        - Each successful search increments the user's quota usage
        - Results are ordered by published date (newest first)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        quota_obj = UserQuota.objects.get(user=request.user)
        if not quota_obj.has_quota_remaining():
            return Response({
                'success': False,
                'message': 'Quota limit reached',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = NewsSearchSerializer(data=request.data)
       

        if serializer.is_valid():
            keyword = serializer.validated_data['keyword']
            source_name = serializer.validated_data.get('source_name')
            language = serializer.validated_data.get('language')
            start_date = serializer.validated_data.get('start_date')
            end_date = serializer.validated_data.get('end_date')
            refresh=serializer.validated_data.get('refresh')
        
        
            search_keyword = SearchKeyword.objects.filter(
                keyword=keyword,
                user=request.user
            ).first()
       
            if search_keyword and not refresh:
                time_diff = timezone.now() - search_keyword.last_searched
                if time_diff < timedelta(minutes=15):
                   
                    articles = Article.objects.filter(search_keyword=search_keyword).order_by('-published_at')
                    
             
                    if source_name:
                        articles = articles.filter(source_name=source_name)
                    if language:
                        articles = articles.filter(language=language)
                    if start_date:
                        articles = articles.filter(published_at__date__gte=start_date)
                    if end_date:
                        articles = articles.filter(published_at__date__lte=end_date)

                 
                    existing_keyword = SearchKeyword.objects.filter(keyword=keyword, user=request.user).first()
                    existing_keyword.last_searched = timezone.now()
                    existing_keyword.save()
                    return Response({
                        'success': True,
                        'message': 'Using cached data',
                        'data': {
                            'keyword': keyword,
                            'articles': ArticleSerializer(articles, many=True).data
                        }
                    })
            
          
            is_search_keyword_created = False
            if not search_keyword:
                search_keyword = SearchKeyword.objects.create(
                    keyword=keyword,
                    user=request.user
                )
                is_search_keyword_created = True
            else:
                search_keyword.last_searched = timezone.now()
                search_keyword.save()
            
  
            url = f'https://newsapi.org/v2/everything?q={keyword}&apiKey={settings.NEWS_API_KEY}&sortBy=publishedAt'
           

            if refresh or (is_search_keyword_created == False):
                articles = Article.objects.order_by('-published_at').filter(search_keyword=search_keyword).first()
              
                url += f"&from={articles.published_at.isoformat()}Z"
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                articles_data = data.get('articles', [])
                articles_to_create = []
                for article_data in articles_data:
                    
                    published_at = datetime.strptime(article_data['publishedAt'], '%Y-%m-%dT%H:%M:%SZ')
                    published_at = timezone.make_aware(published_at)
                    try:
                        exists=Article.objects.filter(published_at=published_at,title=article_data['title'], search_keyword=search_keyword).exists()
                        if exists:
                            continue
                    except Exception as e:
                        print(f'\n\n{e=}\n\n')
                        traceback.print_exc()

                    try:
                        article = Article(
                            title=article_data['title'],
                            description=article_data['description'],
                            url=article_data['url'],
                            urlToImage=article_data['urlToImage'],
                            published_at=article_data['publishedAt'],
                            source_name=article_data['source']['name'],
                            source_category=article_data.get('source', {}).get('category'),
                            language=article_data.get('language', 'en'),
                            search_keyword=search_keyword  # Direct relationship
                        )
                        articles_to_create.append(article)
                    except Exception as e:
                        print(f'\n\n{e=}\n\n')
                        traceback.print_exc()
                
        
                created_articles = Article.objects.bulk_create(
                    articles_to_create,
                    ignore_conflicts=True
                )
                
                articles = Article.objects.filter(search_keyword=search_keyword).order_by('-published_at')
                
         
                if source_name:
                    articles = articles.filter(source_name=source_name)
                if language:
                    articles = articles.filter(language=language)
                if start_date:
                    articles = articles.filter(published_at__date__gte=start_date)
                if end_date:
                    articles = articles.filter(published_at__date__lte=end_date)
               
                quota_obj.increment_quota()
                
                return Response({
                    'success': True,
                    'message': 'Data fetched from API',
                    'data': {
                        'keyword': keyword,
                        'articles': ArticleSerializer(articles, many=True).data
                    }
                })
                
                
            
            return Response({
                'success': False,
                'message': 'Error fetching news from API',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'message': 'Invalid search parameters',
            'errors': serializer.errors,
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)


class UserRegistrationAPIView(APIView):
    
    """
    API view for user registration.
    This endpoint allows anyone to register a new user account. On successful
    registration, it creates a user quota record and returns access/refresh tokens
    for authentication.
    Request Body:
        - username (str): User's chosen username
        - email (str): User's email address
        - password (str): User's password
    Responses:
        - 201 CREATED: Registration successful, returns user details and authentication tokens
        - 400 BAD REQUEST: Registration failed due to validation errors
    Notes:
        - Default quota of 10 is assigned to new users
        - JWT tokens (access and refresh) are generated for immediate authentication
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            
           
            UserQuota.objects.create(user=user, quota_limit=10, used_quota=0)
            
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Registration successful',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_staff': user.is_staff
                    },
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }
                }
            }, status=status.HTTP_201_CREATED)
        
        return Response({
            'success': False,
            'message': 'Registration failed',
            'errors': serializer.errors,
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

class UserLoginAPIView(APIView):

    """
    API view for user authentication.
    This endpoint allows users to log in by providing their username and password.
    On successful authentication, it returns user details and JWT tokens.
    Request Body:
        - username (str): User's username
        - password (str): User's password
    Responses:
        - 200 OK: Login successful, returns user details and authentication tokens
        - 400 BAD REQUEST: Missing username or password
        - 401 UNAUTHORIZED: Invalid credentials or inactive user
    Notes:
        - Validates that the user account is active before authentication
        - Returns both access and refresh JWT tokens for authentication
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            return Response({
                'success': False,
                'message': 'Please provide both username and password',
                'data': None
            }, status=status.HTTP_400_BAD_REQUEST)

        user = authenticate(username=username, password=password)
        
        if user and user.is_active:
            refresh = RefreshToken.for_user(user)
            return Response({
                'success': True,
                'message': 'Login successful',
                'data': {
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_staff': user.is_staff
                    },
                    'tokens': {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh)
                    }
                }
            })
        
        return Response({
            'success': False,
            'message': 'Invalid credentials',
            'data': None
        }, status=status.HTTP_401_UNAUTHORIZED)


class UserSearchHistoryAPIView(APIView):

    """
    API view for retrieving a user's search history.
    This endpoint allows authenticated users to access their previous search keywords
    and when they were last searched, ordered by most recent first.
    Request Parameters:
        - None
    Responses:
        - 200 OK: Returns the user's search history with keywords and timestamps
    Returns:
        - List of dictionaries containing:
            - keyword (str): The search term used
            - last_searched (datetime): When the keyword was last searched
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get user's search history (keywords only)
        """
       
        search_keywords = SearchKeyword.objects.filter(
            user=request.user
        ).order_by('-last_searched')

       
        search_history = [
            {
                'keyword': keyword.keyword,
                'last_searched': keyword.last_searched
            }
            for keyword in search_keywords
        ]

        return Response({
            'success': True,
            'message': 'Search history retrieved successfully',
            'data': {
                'search_history': search_history
            }
        })

class UserListAPIView(APIView):

    """
    API view for retrieving a list of all non-staff users.
    This endpoint allows staff users to view all regular users and their quota information.
    The data is optimized with select_related to minimize database queries.
    Request Parameters:
        - None
    Responses:
        - 200 OK: Returns list of users with their details and quota information
        - 403 FORBIDDEN: Access denied for non-staff users
    Returns:
        - List of user objects serialized by UserListSerializer
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        List all non-staff users with their quota information (only accessible by staff users)
        """
    
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Only staff users can access this endpoint',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        users = User.objects.filter(is_staff=False).select_related('quota')
        
  
        serializer = UserListSerializer(users, many=True)

        return Response({
            'success': True,
            'message': 'Users retrieved successfully',
            'data': {
                'users': serializer.data
            }
        })

class UserManagementAPIView(APIView):

    """
    API view for managing user status and quota.
    This endpoint allows staff users to update a user's active status and
    quota limit. Changes can be made independently (only active status or only quota).
    Request Body:
        - user_id (int): Required - ID of the user to update
        - is_active (bool, optional): User's active status
        - user_quota (int, optional): New quota limit for the user
    Responses:
        - 200 OK: User updated successfully
        - 400 BAD REQUEST: Invalid request data
        - 403 FORBIDDEN: Access denied for non-staff users
        - 404 NOT FOUND: User with provided ID does not exist
    Notes:
        - Will create a quota object if one doesn't exist
        - Returns only the fields that were updated
    """
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        """
        Update user status and quota (only accessible by staff users)
        """
    
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Only staff users can access this endpoint',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = UserStatusUpdateSerializer(data=request.data)
        if serializer.is_valid():
            user_id = serializer.validated_data['user_id']
            is_active = serializer.validated_data.get('is_active')
            user_quota = serializer.validated_data.get('user_quota')

            try:
                user = User.objects.get(id=user_id)
                response_data = {}

               
                if is_active is not None:
                    user.is_active = is_active
                    user.save()
                    response_data['is_active'] = is_active

                if user_quota is not None:
                    user_quota_obj, created = UserQuota.objects.get_or_create(user=user)
                    user_quota_obj.quota_limit = user_quota
                    user_quota_obj.save()
                    response_data['quota_limit'] = user_quota

                return Response({
                    'success': True,
                    'message': 'User updated successfully',
                    'data': response_data
                })
            except User.DoesNotExist:
                return Response({
                    'success': False,
                    'message': 'User not found',
                    'data': None
                }, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'success': False,
            'message': 'Invalid data',
            'errors': serializer.errors,
            'data': None
        }, status=status.HTTP_400_BAD_REQUEST)

class TopKeywordsAPIView(APIView):

    """
    API view for retrieving the most popular search keywords.
    This endpoint provides analytics on the top 5 most frequently searched keywords
    across all users, accessible only to staff users.
    Request Parameters:
        - None
    Responses:
        - 200 OK: Returns the top 5 keywords with their search counts
        - 403 FORBIDDEN: Access denied for non-staff users
    Returns:
        - List of dictionaries containing:
            - keyword (str): The search term
            - count (int): Number of times the keyword has been searched
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """
        Get top 5 most searched keywords with their counts (only accessible by staff users)
        """
     
        if not request.user.is_staff:
            return Response({
                'success': False,
                'message': 'Only staff users can access this endpoint',
                'data': None
            }, status=status.HTTP_403_FORBIDDEN)

      
        top_keywords = SearchKeyword.objects.values('keyword').annotate(
            count=Count('keyword')
        ).order_by('-count')[:5]


        serializer = TopKeywordsSerializer(top_keywords, many=True)

        return Response({
            'success': True,
            'message': 'Top keywords retrieved successfully',
            'data': {
                'top_keywords': serializer.data
            }
        })

