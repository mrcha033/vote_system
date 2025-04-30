# 투표 시스템

Flask 기반의 간단한 투표 시스템입니다. QR 코드를 통한 토큰 기반 투표와 관리자 대시보드를 제공합니다.

## 주요 기능

- QR 코드 기반 투표 토큰 생성
- 토큰별 단일 투표 제한
- 실시간 투표 현황 모니터링
- 관리자 대시보드
- 투표 시작/종료 제어

## 설치 및 실행

### 1. 필요한 패키지 설치

```bash
pip install flask python-dotenv qrcode
```

### 2. 환경변수 설정

#### 개발 환경
`.env` 파일을 생성하고 다음 내용을 추가합니다:
```
ADMIN_PASSWORD=your_secure_password
```

#### Fly.io 배포 환경
```bash
fly secrets set ADMIN_PASSWORD="your_secure_password"
```

### 3. 데이터베이스 초기화

```bash
python app.py
```
처음 실행 시 자동으로 데이터베이스가 생성됩니다.

### 4. 서버 실행

```bash
python app.py
```

## 사용 방법

### 관리자 페이지
- URL: `/admin`
- 기본 관리자 비밀번호: `.env` 파일에 설정된 값
- 기능:
  - 투표 항목 생성
  - 투표 토큰 생성
  - 투표 시작/종료
  - 투표 결과 확인

### 투표 참여
1. QR 코드 스캔 또는 토큰 입력
2. 투표 항목 선택
3. 투표 제출

## 보안

- 관리자 페이지는 비밀번호로 보호됩니다
- 토큰은 한 번만 사용 가능합니다
- 투표는 활성화된 상태에서만 참여 가능합니다

## 데이터베이스 스키마

### tokens 테이블
- id: 토큰 고유 ID
- token: 토큰 문자열
- created_at: 생성 시간
- is_used: 사용 여부

### vote_items 테이블
- vote_id: 투표 항목 ID
- title: 투표 제목
- created_at: 생성 시간
- options: 투표 옵션
- is_active: 활성화 상태

### votes 테이블
- id: 투표 기록 ID
- vote_id: 투표 항목 ID
- token_id: 사용된 토큰 ID
- choice: 선택한 옵션
- timestamp: 투표 시간
- voter_name: 투표자 이름

## 개발 환경 설정

1. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. 필요한 패키지 설치
```bash
pip install -r requirements.txt
```

3. 환경변수 설정
```bash
# .env 파일 생성
echo ADMIN_PASSWORD=your_secure_password > .env
```

4. 개발 서버 실행
```bash
python app.py
```

## 배포

### Fly.io 배포
1. Fly.io CLI 설치
2. 로그인
3. 앱 생성
4. 환경변수 설정
5. 배포

```bash
fly launch
fly secrets set ADMIN_PASSWORD="your_secure_password"
fly deploy
```

### 도메인 설정 (선택사항)
1. 도메인 추가
```bash
fly domains add your-domain.com
```

2. DNS 설정
- 도메인 공급자의 DNS 설정에서 다음 레코드 추가:
  - A 레코드: `@` → Fly.io IP
  - CNAME 레코드: `www` → your-app.fly.dev

3. SSL 인증서 발급
```bash
fly certs create your-domain.com
```

4. 인증서 상태 확인
```bash
fly certs show your-domain.com
```

## 라이선스

MIT License 