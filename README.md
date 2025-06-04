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
python -m app
```

## Fly.io 배포

`fly launch` 후 다음과 같이 비밀값을 저장합니다.
```bash
fly secrets set SECRET_KEY=$(openssl rand -hex 32) ADMIN_PASSWORD=your_password
```
볼륨 마운트를 통해 `/data` 경로가 애플리케이션의 `DATA_DIR`로 사용됩니다. 데이터베이스와 로그가 이 위치에 저장됩니다.

## 라이선스

MIT License

