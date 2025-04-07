News Search Application

A Django-based web application for searching news articles with user authentication, quota management, and search history tracking.

Prerequisites

- Python 3.8 or higher
- MySQL Server
- pip (Python package manager)

Setup Instructions

1. Clone the Repository

git clone <repository-url>
cd news_search_project


2. Create and Activate Virtual Environment

# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate


3. Install Dependencies

pip install -r requirements.txt


4. Configure Environment Variables
Create a `.env` file in the project root with the following variables:
env
DEBUG=True
SECRET_KEY=your_secret_key_here
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=localhost
DB_PORT=3306
NEWS_API_KEY=your_news_api_key


5. Database Setup

1. Create a MySQL database
2. Update the database settings in `.env` file
3. Run migrations:

python manage.py makemigrations
python manage.py migrate


6. Create Superuser

python manage.py createsuperuser


7. Run the Development Server

python manage.py runserver


API Endpoints

Authentication
- `POST /api/auth/register/` - User registration
- `POST /api/auth/login/` - User login

News Search
- `GET /api/search/advanced/` - Search news articles with filters

User Management (Staff Only)
- `GET /api/user/list/` - List all users with their quotas
- `PATCH /api/user/update/` - Update user status and quota
- `GET /api/keywords/top/` - Get top 5 searched keywords

User Features
- `GET /api/user/search-history/` - Get user's search history




