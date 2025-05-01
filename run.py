from server import app, init_db, get_local_ip, ALLOWED_NETWORK

if __name__ == '__main__':
    init_db()
    local_ip = get_local_ip()
    print(f"서버가 시작되었습니다. 로컬 IP: {local_ip}")
    print(f"허용된 네트워크: {ALLOWED_NETWORK}")
    app.run(host='0.0.0.0', port=5000, debug=True)
