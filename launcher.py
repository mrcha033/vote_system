import sys
import os
import subprocess
import webbrowser
import requests
import json
from datetime import datetime
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                           QTextEdit, QFileDialog, QMessageBox, QGroupBox,
                           QTabWidget)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QIcon

class ServerThread(QThread):
    log_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.process = None
        self.is_running = False
        
    def run(self):
        try:
            self.is_running = True
            self.process = subprocess.Popen(
                ["python", "app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            while self.is_running:
                output = self.process.stdout.readline()
                if output:
                    self.log_signal.emit(output.strip())
                error = self.process.stderr.readline()
                if error:
                    self.error_signal.emit(error.strip())
                    
        except Exception as e:
            self.error_signal.emit(f"서버 실행 오류: {str(e)}")
            
    def stop(self):
        self.is_running = False
        if self.process:
            self.process.terminate()
            self.process.wait()

class VoteLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_thread = None
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
        
    def start_server(self):
        try:
            self.server_thread = ServerThread()
            self.server_thread.log_signal.connect(self.log_message)
            self.server_thread.error_signal.connect(self.log_error)
            self.server_thread.start()
            
            self.status_label.setText("서버 상태: 실행 중")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)
            self.admin_button.setEnabled(True)
            self.log_message("서버가 시작되었습니다.")
            
        except Exception as e:
            QMessageBox.critical(self, "오류", f"서버 시작 실패: {str(e)}")
            
    def stop_server(self):
        if self.server_thread:
            self.server_thread.stop()
            self.server_thread.wait()
            self.status_label.setText("서버 상태: 중지됨")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)
            self.admin_button.setEnabled(False)
            self.log_message("서버가 종료되었습니다.")
            
    def generate_qr(self):
        try:
            count = self.token_count.text()
            if not count.isdigit():
                QMessageBox.warning(self, "오류", "토큰 수는 숫자여야 합니다.")
                return
                
            response = requests.post(
                f"http://localhost:5000/admin/generate_tokens",
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
        webbrowser.open("http://localhost:5000/admin")
        
    def log_message(self, message):
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] {message}")
        
    def log_error(self, message):
        self.log_text.append(f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {message}")
        
    def export_logs(self):
        try:
            response = requests.get("http://localhost:5000/admin/export_logs")
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
        
    def closeEvent(self, event):
        if self.server_thread and self.server_thread.is_running:
            self.stop_server()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    launcher = VoteLauncher()
    launcher.show()
    sys.exit(app.exec_()) 