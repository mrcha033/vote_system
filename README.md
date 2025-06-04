# 투표 시스템

간단한 토큰 기반 웹 투표 서비스입니다. QR 코드로 생성한 토큰을 사용하여 각 안건에 한 번만 투표할 수 있습니다. 관리자는 웹 대시보드에서 표결 항목을 관리하고 결과를 실시간으로 확인할 수 있습니다.

## 주요 기능

- QR 코드로 투표 토큰 생성 및 ZIP 다운로드
- 토큰 사용 여부 검증으로 단일 투표 보장
- 표결 항목 활성화/종료 제어
- 결과 통계와 최근 투표 기록 확인
- CSV 로그 파일 내보내기

## 설치

### 의존 패키지 설치
```bash
pip install -r requirements.txt
```

### 환경 변수 설정
`SECRET_KEY`와 `ADMIN_PASSWORD`를 반드시 지정해야 합니다. `.env` 파일을 사용하거나 환경 변수로 설정하세요.
```bash
export SECRET_KEY=$(openssl rand -hex 32)
export ADMIN_PASSWORD=your_password
```

### 애플리케이션 실행
```bash
gunicorn --preload app:app -k gevent -w 2 -b 0.0.0.0:8080
```

## Fly.io 배포

Fly.io CLI인 `flyctl`을 먼저 설치해야 합니다. [설치 안내](https://fly.io/docs/flyctl/install/)를 참고하세요.
`fly auth login` 명령으로 로그인하거나 `FLY_API_TOKEN` 환경 변수를 설정해 인증을 완료합니다.

애플리케이션 초기화는 `fly launch`로 수행합니다. 배포 전에 다음과 같이 비밀값을 등록합니다.
```bash
fly secrets set SECRET_KEY=$(openssl rand -hex 32) ADMIN_PASSWORD=your_password
```
비밀값을 등록한 뒤 `flyctl deploy` 명령으로 배포를 진행합니다.
볼륨 마운트를 통해 `/data` 경로가 애플리케이션의 `DATA_DIR`로 사용됩니다. 데이터베이스와 로그가 이 위치에 저장됩니다.

## 라이선스

MIT License

