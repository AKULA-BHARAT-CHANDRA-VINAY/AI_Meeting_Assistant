import os
import threading
import time
def run_flask():
    os.system("python app.py")

def run_kivy():
    os.system("python MeetingAssistant.py")

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()
    time.sleep(5)  # Wait 5 seconds for the backend to start
    kivy_thread = threading.Thread(target=run_kivy)
    kivy_thread.start()