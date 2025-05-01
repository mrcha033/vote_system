import os
import sys

def setup_flask_env():
    # PyInstaller로 패키징된 경우
    if getattr(sys, 'frozen', False):
        # MEIPASS 경로 설정
        base_path = sys._MEIPASS
        
        # Flask 템플릿 경로 설정
        template_path = os.path.join(base_path, 'templates')
        if os.path.exists(template_path):
            os.environ['FLASK_TEMPLATE_FOLDER'] = template_path
            os.environ['TEMPLATE_FOLDER'] = template_path
            
        # Flask 정적 파일 경로 설정
        static_path = os.path.join(base_path, 'static')
        if os.path.exists(static_path):
            os.environ['FLASK_STATIC_FOLDER'] = static_path
            os.environ['STATIC_FOLDER'] = static_path
            
        # 데이터베이스 경로 설정
        db_path = os.path.join(base_path, 'data.db')
        if os.path.exists(db_path):
            os.environ['DATABASE_PATH'] = db_path
            os.environ['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
            
        # 로그 디렉토리 설정
        log_path = os.path.join(base_path, 'log')
        if not os.path.exists(log_path):
            os.makedirs(log_path)
        os.environ['LOG_PATH'] = log_path
        
        # 환경 변수 파일 경로 설정
        env_path = os.path.join(base_path, '.env')
        if os.path.exists(env_path):
            os.environ['ENV_PATH'] = env_path
            
        # Flask 앱 설정
        os.environ['FLASK_APP'] = os.path.join(base_path, 'app.py')
        os.environ['FLASK_ENV'] = 'production'
        os.environ['FLASK_DEBUG'] = '0'

# Flask 환경 설정 실행
setup_flask_env()

# Python 경로 설정
sys.path.insert(0, os.path.join(sys._MEIPASS, 'static'))
sys.path.insert(0, os.path.join(sys._MEIPASS, 'templates')) 