# 1. Python 이미지를 베이스로 사용
FROM python:3.12-slim

# 2. 작업 디렉토리 설정
WORKDIR /app

# 3. 시스템 패키지 설치 (mysqlclient를 위한 libmariadb-dev 추가)
RUN apt update && apt install -y libmariadb-dev gcc pkg-config && rm -rf /var/lib/apt/lists/*

# 4. 필요한 패키지들을 복사
COPY requirements.txt /app/

# 5. 의존성 패키지 설치
RUN pip install --no-cache-dir -r requirements.txt

# 6. 애플리케이션 파일 복사
COPY . /app/

# 7. Flask 애플리케이션 포트 설정
EXPOSE 5000

# 8. Flask 애플리케이션 실행
CMD ["python", "app.py"]