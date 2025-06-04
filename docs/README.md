# Voting System

This project provides a simple token-based voting service built with Flask. It generates QR codes for each token and offers a minimal admin dashboard to manage agendas and view results.

## Basic Usage

1. Install requirements:
```bash
pip install -r requirements.txt
```
2. Set the required environment variables:
```bash
export SECRET_KEY=$(openssl rand -hex 32)
export ADMIN_PASSWORD=your_password
```
3. Run the application:
```bash
gunicorn --preload app:app -k gevent -w 2 -b 0.0.0.0:8080
```

For Fly.io deployments, store the secrets using `fly secrets set` and ensure a volume is mounted at `/data` for persistent storage.

## License

MIT
