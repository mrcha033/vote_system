from dotenv import load_dotenv
import sys
import os
import subprocess
import platform

sys.path.append(os.path.join(os.path.dirname(__file__), 'scripts'))

import webbrowser
import requests
import sqlite3
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QTextEdit, QFileDialog, QMessageBox, QGroupBox,
                           QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QIcon, QTextCursor
from flask import Flask
from server import app as flask_app
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import time
import socket
import ipaddress
import netifaces

def get_local_ip():
    """실제 유선/무선 인터페이스의 로컬 IP 주소를 가져옵니다."""
    try:
        for iface in netifaces.interfaces():
            if "VirtualBox" in iface or "VMware" in iface or "vEthernet" in iface or "Loopback" in iface:
                continue  # 가상 인터페이스 제외
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for entry in addrs[netifaces.AF_INET]:
                    ip = entry.get('addr')
                    if ip and ipaddress.ip_address(ip).is_private and not ip.startswith("192.168.56."):
                        return ip
    except:
        pass
    return "127.0.0.1"

def is_private_ip(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

def get_network_info():
    """기본 게이트웨이 인터페이스의 IP 및 넷마스크를 반환 (모든 인터페이스에서 시도)"""
    try:
        gws = netifaces.gateways()
        default_iface = gws.get('default', {}).get(netifaces.AF_INET, [None])[1]

        if default_iface:
            addrs = netifaces.ifaddresses(default_iface)
            inet = addrs.get(netifaces.AF_INET)
            if inet:
                for addr in inet:
                    ip = addr.get("addr")
                    netmask = addr.get("netmask")
                    if ip and netmask and ipaddress.ip_address(ip).is_private:
                        return ip, netmask

        # fallback: 모든 인터페이스 순회
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            inet = addrs.get(netifaces.AF_INET)
            if not inet:
                continue
            for addr in inet:
                ip = addr.get("addr")
                netmask = addr.get("netmask")
                if ip and netmask and ipaddress.ip_address(ip).is_private:
                    return ip, netmask
    except Exception as e:
        print(f"[!] 네트워크 정보 가져오기 실패: {e}")
    return None, None

def calculate_network_range(ip, netmask):
    try:
        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        return str(network)
    except Exception as e:
        print(f"[!] 네트워크 대역 계산 실패: {e}")
        return None

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class ServerThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    server_ready = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.is_running = False

    def run(self):
        try:
            self.is_running = True
            self.log_signal.emit("서버를 시작합니다...")

            ip, netmask = get_network_info()
            self.log_signal.emit(f"[네트워크 감지] IP: {ip}, 넷마스크: {netmask}")
            
            if ip and netmask:
                network_range = calculate_network_range(ip, netmask)
                self.log_signal.emit(f"[허용 네트워크] {network_range}")
            else:
                self.log_signal.emit("[경고] 유효한 네트워크 정보를 감지하지 못해 기본값 사용")

            server_url = f"http://{get_local_ip()}:5000"
            self.log_signal.emit(f"[서버 주소] {server_url}")

            if platform.system() == "Windows":
                self.log_signal.emit("Windows 환경: Waitress 서버로 실행합니다.")
                from waitress import serve
                threading.Thread(target=lambda: serve(flask_app, host='0.0.0.0', port=5000), daemon=True).start()
            else:
                gunicorn_cmd = [
                    "gunicorn",
                    "-w", "4",
                    "-k", "gevent",
                    "-b", "0.0.0.0:5000",
                    "server:app"
                ]
                self.gunicorn_proc = subprocess.Popen(gunicorn_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                threading.Thread(target=self.stream_logs, args=(self.gunicorn_proc.stdout,), daemon=True).start()

            # 서버 시작 대기 및 상태 확인
            start_time = time.time()
            server_started = False
            server_url = f"http://{get_local_ip()}:5000"
            self.log_signal.emit(f"서버 주소: {server_url}")
            
            while self.is_running and time.time() - start_time < 10:  # 10초 동안 대기
                try:
                    response = requests.get(server_url)
                    if response.status_code == 200:
                        server_started = True
                        self.log_signal.emit("서버가 정상적으로 시작되었습니다.")
                        self.server_ready.emit()
                        break
                except:
                    pass
                
                time.sleep(0.1)
            
            if not server_started:
                self.error_signal.emit("서버 시작 실패: 10초 내에 서버가 시작되지 않았습니다.")
                self.stop()
                return
            
            # 서버 실행 상태 유지
            while self.is_running:
                time.sleep(0.1)
                    
        except Exception as e:
            self.error_signal.emit(f"서버 실행 오류: {str(e)}")
            import traceback
            self.error_signal.emit(f"상세 오류: {traceback.format_exc()}")
            
    def stop(self):
        self.is_running = False
        try:
            # 서버 종료 요청
            if hasattr(self, 'gunicorn_proc') and self.gunicorn_proc.poll() is None:
                self.gunicorn_proc.terminate()
                self.gunicorn_proc.wait(timeout=5)
                self.log_signal.emit("Gunicorn 서버가 정상적으로 종료되었습니다.")
            else:
                self.error_signal.emit("서버 종료 실패: 서버가 실행 중이지 않습니다.")
        except Exception as e:
            self.error_signal.emit(f"서버 종료 중 오류 발생: {str(e)}")

    def stream_logs(self, pipe):
        for line in iter(pipe.readline, b''):
            decoded = line.decode('utf-8', errors='replace').strip()
            self.log_signal.emit(decoded)

class DotEnvChangeHandler(FileSystemEventHandler):
    def __init__(self, restart_callback):
        self.restart_callback = restart_callback
        self.last_modified = None

    def on_modified(self, event):
        if event.src_path.endswith('.env'):
            now = time.time()
            if not self.last_modified or now - self.last_modified > 1:  # 최소 1초 간격 제한
                self.last_modified = now
                print("[자동감지] .env 변경 감지됨, 서버 재시작")
                self.restart_callback()

class VoteLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.server_log_path = os.path.join('log', 'server_runtime.log')
        self.log_timer = QTimer(self)
        self.log_timer.timeout.connect(self.read_server_log)
        self.env_observer = Observer()
        self.env_handler = DotEnvChangeHandler(self.restart_server_on_env_change)
        self.env_observer.schedule(self.env_handler, path='.', recursive=False)
        self.env_observer.start()
        self.last_log_content = ""
        self.log_timer.start(1000)
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle('로컬 투표 서버 런처')
        self.setGeometry(100, 100, 800, 600)
        
        # 메인 위젯과 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        
        # 탭 위젯 생성
        tabs = QTabWidget()
        
        # 서버 제어 탭
        server_tab = QWidget()
        server_layout = QVBoxLayout(server_tab)
        
        # 서버 제어 그룹
        server_group = QGroupBox("서버 제어")
        server_group_layout = QVBoxLayout()
        
        # 관리자 비밀번호 설정
        password_group = QGroupBox("관리자 비밀번호 설정")
        password_layout = QVBoxLayout()
        
        # 현재 비밀번호 표시
        self.current_password_label = QLabel("현재 비밀번호: ********")
        password_layout.addWidget(self.current_password_label)
        
        # 새 비밀번호 입력
        new_password_layout = QHBoxLayout()
        new_password_layout.addWidget(QLabel("새 비밀번호:"))
        self.new_password_input = QLineEdit()
        self.new_password_input.setEchoMode(QLineEdit.Password)
        new_password_layout.addWidget(self.new_password_input)
        password_layout.addLayout(new_password_layout)
        
        # 비밀번호 변경 버튼
        self.change_password_button = QPushButton("비밀번호 변경")
        self.change_password_button.clicked.connect(self.change_password)
        password_layout.addWidget(self.change_password_button)
        
        password_group.setLayout(password_layout)
        server_group_layout.addWidget(password_group)

        # 회의명 설정
        meeting_title_group = QGroupBox("회의명 설정")
        meeting_title_layout = QVBoxLayout()

        self.meeting_title_input = QLineEdit()
        self.meeting_title_input.setPlaceholderText("예: 2025년 제3차 확대운영위원회")
        meeting_title_layout.addWidget(QLabel("회의명:"))
        meeting_title_layout.addWidget(self.meeting_title_input)

        self.set_meeting_title_button = QPushButton("회의명 저장")
        self.set_meeting_title_button.clicked.connect(self.save_meeting_title)
        meeting_title_layout.addWidget(self.set_meeting_title_button)

        meeting_title_group.setLayout(meeting_title_layout)
        server_group_layout.addWidget(meeting_title_group)

        # 서버 상태 표시
        self.status_label = QLabel("서버 상태: 중지됨")
        server_group_layout.addWidget(self.status_label)
        
        # 서버 시작/종료 버튼
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("서버 시작")
        self.start_button.clicked.connect(self.start_server)
        self.stop_button = QPushButton("서버 종료")
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        server_group_layout.addLayout(button_layout)
        
        server_group.setLayout(server_group_layout)
        server_layout.addWidget(server_group)
        
        # 관리자 페이지 열기 버튼
        self.admin_button = QPushButton("관리자 페이지 열기")
        self.admin_button.clicked.connect(self.open_admin)
        self.admin_button.setEnabled(False)
        server_layout.addWidget(self.admin_button)
        
        # 로그 출력
        log_group = QGroupBox("서버 로그")
        log_layout = QVBoxLayout()
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        log_group.setLayout(log_layout)
        server_layout.addWidget(log_group)
        
        # 토큰 관리 탭
        token_tab = QWidget()
        token_layout = QVBoxLayout(token_tab)
        
        # 토큰 수 입력
        token_input_layout = QHBoxLayout()
        token_input_layout.addWidget(QLabel("생성할 토큰 수:"))
        self.token_count = QLineEdit()
        self.token_count.setPlaceholderText("숫자를 입력하세요")
        token_input_layout.addWidget(self.token_count)
        token_layout.addLayout(token_input_layout)
        
        # QR 코드 생성 버튼
        self.generate_button = QPushButton("QR 코드 생성")
        self.generate_button.clicked.connect(self.generate_qr)
        token_layout.addWidget(self.generate_button)
        
        # 로그 관리 탭
        log_management_tab = QWidget()
        log_management_layout = QVBoxLayout(log_management_tab)
        
        # 로그 내보내기 버튼
        self.export_logs_button = QPushButton("투표 로그 내보내기")
        self.export_logs_button.clicked.connect(self.export_logs)
        log_management_layout.addWidget(self.export_logs_button)
        
        # 탭 추가
        tabs.addTab(server_tab, "서버 제어")
        tabs.addTab(token_tab, "토큰 관리")
        tabs.addTab(log_management_tab, "로그 관리")
        
        layout.addWidget(tabs)
        self.load_current_password
        
    def start_server(self):
        try:
            if self.server_thread and self.server_thread.is_running:
                QMessageBox.warning(self, "경고", "서버가 이미 실행 중입니다.")
                return
                
            self.server_thread = ServerThread()
            self.server_thread.log_signal.connect(self.log_message)
            self.server_thread.error_signal.connect(self.log_error)
            self.server_thread.server_ready.connect(self.on_server_ready)
            self.server_thread.start()
            
            self.status_label.setText("서버 상태: 시작 중...")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.admin_button.setEnabled(False)
            self.log_message("서버를 시작합니다...")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"서버 시작 실패: {str(e)}")
            
    def on_server_ready(self):
        self.status_label.setText("서버 상태: 실행 중")
        self.admin_button.setEnabled(True)
        self.log_message("서버가 준비되었습니다.")
        QTimer.singleShot(500, self.load_current_password)
        
    def stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait()
            self.status_label.setText("서버 상태: 중지됨")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.admin_button.setEnabled(False)
            self.log_message("서버가 종료되었습니다.")

    def restart_server_on_env_change(self):
        self.log_message("`.env` 변경 감지됨, 서버를 재시작합니다...")
        self.stop_server()
        QTimer.singleShot(1000, self.start_server)  # 잠시 후 서버 재시작

    def closeEvent(self, event):
        if self.server_thread and self.server_thread.is_running:
            self.stop_server()
        self.env_observer.stop()
        self.env_observer.join()
        event.accept()

    def read_server_log(self):
        try:
            if os.path.exists(self.server_log_path):
                with open(self.server_log_path, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                    content = "".join(lines[-50:])
                    if content != self.last_log_content:
                        self.log_text.setPlainText(content)
                        self.log_text.moveCursor(QTextCursor.End)
                        self.last_log_content = content
        except Exception as e:
            self.log_error(f"로그 파일 읽기 실패: {str(e)}")
            
    def generate_qr(self):
        try:
            count = self.token_count.text()
            if not count.isdigit():
                QMessageBox.warning(self, "오류", "토큰 수는 숫자여야 합니다.")
                return
                
            server_ip = get_local_ip()
            response = requests.post(
                f"http://{server_ip}:5000/admin/generate_tokens",
                data={"count": count},
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            
            if response.status_code == 200:
                # ZIP 파일 저장 위치 선택
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "QR 코드 ZIP 파일 저장",
                    f"voting_tokens_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    "ZIP Files (*.zip)"
                )
                
                if file_path:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    QMessageBox.information(self, "성공", f"QR 코드가 {file_path}에 저장되었습니다.")
            else:
                QMessageBox.critical(self, "오류", "QR 코드 생성 실패")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"QR 코드 생성 중 오류 발생: {str(e)}")
            
    def open_admin(self):
        webbrowser.open(f"http://{get_local_ip()}:5000/admin")
        
    def log_message(self, message):
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def log_error(self, message):
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {message}")

    def export_logs(self):
        try:
            response = requests.get(f"http://{get_local_ip()}:5000/admin/export_logs")
            if response.status_code == 200:
                # ZIP 파일 저장 위치 선택
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "로그 ZIP 파일 저장",
                    f"vote_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    "ZIP Files (*.zip)"
                )
                
                if file_path:
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    QMessageBox.information(self, "성공", f"로그가 {file_path}에 저장되었습니다.")
            else:
                QMessageBox.critical(self, "오류", "로그 내보내기 실패")
                
        except Exception as e:
            QMessageBox.critical(self, "오류", f"로그 내보내기 중 오류 발생: {str(e)}")
        
    def change_password(self):
        try:
            new_password = self.new_password_input.text()
            if not new_password:
                QMessageBox.warning(self, "오류", "새 비밀번호를 입력하세요.")
                return
                
            # .env 파일 경로 설정
            if getattr(sys, 'frozen', False):
                env_path = os.path.join(os.getcwd, '.env')
            else:
                env_path = '.env'
                
            # .env 파일 읽기 및 수정
            with open(env_path, 'r') as f:
                lines = f.readlines()
                
            with open(env_path, 'w') as f:
                for line in lines:
                    if line.startswith('ADMIN_PASSWORD='):
                        f.write(f'ADMIN_PASSWORD={new_password}\n')
                    else:
                        f.write(line)
                        
            self.new_password_input.clear()
            QMessageBox.information(self, "성공", "비밀번호가 변경되었습니다.")
            self.log_message("관리자 비밀번호가 변경되었습니다.")
            self.log_message("관리자 비밀번호가 변경되어 서버를 재시작합니다.")
            self.stop_server()
            QTimer.singleShot(1000, self.start_server)  # 1초 후 서버 재시작

        except Exception as e:
            QMessageBox.critical(self, "오류", f"비밀번호 변경 실패: {str(e)}")
    
    def load_current_password(self):
        env_path = os.path.join(os.getcwd(), '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r', encoding="utf-8") as f:
                for line in f:
                    if line.startswith("ADMIN_PASSWORD="):
                        pw = line.strip().split("=", 1)[1]
                        self.current_password_label.setText(f"현재 비밀번호: {pw}")

    def closeEvent(self, event):
        if self.server_thread and self.server_thread.is_running:
            self.stop_server()
        event.accept()

    def save_meeting_title(self):
        new_title = self.meeting_title_input.text().strip()
        DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')
        if not new_title:
            QMessageBox.warning(self, "오류", "회의명을 입력하세요.")
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
            cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", ('meeting_title', new_title))
            conn.commit()
            conn.close()

            self.log_message(f"회의명이 저장되었습니다: {new_title}")
            QMessageBox.information(self, "성공", "회의명이 저장되었습니다. 새로고침 시 바로 적용됩니다.")

        except Exception as e:
            QMessageBox.critical(self, "오류", f"회의명 저장 실패: {str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 아이콘 설정
    try:
        icon_path = get_resource_path('static/favicon.ico')
        if os.path.exists(icon_path):
            app.setWindowIcon(QIcon(icon_path))
            
        launcher = VoteLauncher()
        launcher.show()
        
    except Exception as e:
        print(f"아이콘 로드 실패: {str(e)}")
    
    launcher.show()
    sys.exit(app.exec_()) 