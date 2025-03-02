from kivy.core.window import Window
Window.title = "Meeting Assistant"  # Set the window title

from kivy.app import App
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.clock import Clock

import os
import requests
import threading
import sounddevice as sd
import numpy as np
import wave

API_URL = "http://127.0.0.1:5000"       
# backend_meeting_assistant.railway.internal       backendmeetingassistant-production.up.railway.app
# API_URL = "railway link -p 3fe3c4f0-bd20-4658-955c-eeabb52c98ca"

def show_alert(message):
    """Simple popup alert with message."""
    content = BoxLayout(orientation='vertical', padding=10)
    label = Label(text=message)
    btn = Button(text="OK", size_hint_y=0.3)
    content.add_widget(label)
    content.add_widget(btn)
    popup = Popup(title="Notification", content=content, size_hint=(0.6, 0.4))
    btn.bind(on_press=popup.dismiss)
    popup.open()

def show_success(message):
    """Large, centered success message popup with OK button."""
    content = BoxLayout(orientation='vertical', padding=20)
    label = Label(text=message, font_size=32, halign='center')
    btn = Button(text="OK", size_hint=(None, None), size=(150, 50))
    content.add_widget(label)
    content.add_widget(btn)
    popup = Popup(title="Success", content=content, size_hint=(0.8, 0.6), auto_dismiss=False)
    btn.bind(on_press=popup.dismiss)
    popup.open()

class VoiceInputInterface(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # --- History List (for storing messages) ---
        self.history_list = []
        
        # Add background image (mic integrated)
        self.bg_image = Image(
            source="background.png",
            allow_stretch=True,
            keep_ratio=False,
            pos_hint={'x': 0, 'y': 0},
            size_hint=(1, 1)
        )
        self.add_widget(self.bg_image, index=0)
        
        # History button
        self.history_button = Button(
            text="History",
            size_hint=(None, None),
            size=(200, 50),
            pos_hint={'right': 1, 'top': 1}
        )
        self.history_button.bind(on_press=self.open_history_popup)
        self.add_widget(self.history_button)
        
        # Timer label
        self.timer_label = Label(
            text='00:00',
            font_size=50,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            pos_hint={'center_x': 0.5, 'center_y': 0.35}
        )
        self.add_widget(self.timer_label)
        
        # Bottom panel: text input + horizontal button panel
        self.bottom_panel = BoxLayout(orientation='vertical', size_hint=(1, 0.25),
                                      pos_hint={'x': 0, 'y': 0})
        self.text_input = TextInput(
            hint_text='Enter text...',
            multiline=True,
            size_hint_y=None,
            height=150
        )
        self.bottom_panel.add_widget(self.text_input)
        
        self.button_panel = BoxLayout(orientation='horizontal', size_hint_y=None, height=80,
                                      spacing=10, padding=[10, 0, 10, 0])
        self.upload_button = Button(text='File Upload', size_hint_x=None, width=200)
        self.upload_button.bind(on_press=self.open_file_chooser)
        self.button_panel.add_widget(self.upload_button)
        
        self.send_button = Button(text='Send', size_hint_x=None, width=200)
        self.send_button.bind(on_press=self.send_text)
        self.button_panel.add_widget(self.send_button)
        
        self.bottom_panel.add_widget(self.button_panel)
        self.add_widget(self.bottom_panel)
        
        # Audio recording variables
        self.timer = 0
        self.recording = False
        self.audio_data = []

    def add_history(self, message):
        self.history_list.append(message)
    
    def on_touch_down(self, touch):
        """Detect if user taps on the mic region of the background image."""
        # If the touch isn't inside this layout, ignore
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        
        # Convert screen coords to local coords
        local_x = touch.x - self.x
        local_y = touch.y - self.y
        
        # bounding box for the mic region in normalized coords
        mic_xmin = 0.3
        mic_xmax = 0.7
        mic_ymin = 0.4
        mic_ymax = 0.8
        
        w, h = self.width, self.height
        mic_left   = w * mic_xmin
        mic_right  = w * mic_xmax
        mic_bottom = h * mic_ymin
        mic_top    = h * mic_ymax
        
        if mic_left <= local_x <= mic_right and mic_bottom <= local_y <= mic_top:
            # user tapped mic area => toggle recording
            self.toggle_recording(None)
        
        return super().on_touch_down(touch)
    
    def open_history_popup(self, instance):
        """Open a popup showing the entire history, with multiline support."""
        content = BoxLayout(orientation='vertical', padding=10)
        scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False, do_scroll_y=True)
        history_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=5)
        history_box.bind(minimum_height=history_box.setter('height'))
        for msg in self.history_list:
            lbl = Label(
                text=msg,
                size_hint_y=None,
                halign='left',
                valign='top'
            )
            lbl.bind(
                texture_size=lambda inst, size: setattr(inst, 'size', size),
                width=lambda inst, value: setattr(inst, 'text_size', (value, None))
            )
            lbl.padding = (10, 10)
            history_box.add_widget(lbl)
        
        scroll.add_widget(history_box)
        content.add_widget(scroll)
        
        close_button = Button(text="Close", size_hint_y=None, height=50)
        content.add_widget(close_button)
        
        popup = Popup(title="History", content=content, size_hint=(0.9, 0.9))
        close_button.bind(on_press=popup.dismiss)
        popup.open()
        
        # Scroll to newest entry
        if history_box.children:
            newest_label = history_box.children[0]  # top child
            Clock.schedule_once(lambda dt: scroll.scroll_to(newest_label), 0)
    
    def toggle_recording(self, instance):
        if not self.recording:
            self.recording = True
            self.timer = 0
            self.audio_data = []
            self.timer_event = Clock.schedule_interval(self.update_timer, 1)
            threading.Thread(target=self.record_audio).start()
        else:
            self.recording = False
            Clock.unschedule(self.timer_event)
            threading.Thread(target=self.save_audio_and_upload).start()
    
    def update_timer(self, dt):
        self.timer += 1
        minutes = self.timer // 60
        seconds = self.timer % 60
        self.timer_label.text = f"{minutes:02}:{seconds:02}"
    
    def record_audio(self):
        with sd.InputStream(samplerate=16000, channels=1, callback=self.audio_callback):
            while self.recording:
                sd.sleep(100)
    
    def audio_callback(self, indata, frames, time, status):
        if status:
            print(status)
        self.audio_data.append(indata.copy())
    
    def save_audio_and_upload(self):
        filename = "recorded_audio.wav"
        np_audio = np.concatenate(self.audio_data, axis=0)
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes((np_audio * 32767).astype(np.int16).tobytes())
        try:
            with open(filename, 'rb') as f:
                files = {'audio_file': f}
                response = requests.post(f"{API_URL}/api/upload_audio", files=files)
            if response.status_code == 200:
                result = response.json()
                print(result)
                self.add_history("Audio processed: " + filename)
                Clock.schedule_once(lambda dt: show_success("Process Completed and File Saved successfully"), 0)
            else:
                Clock.schedule_once(lambda dt: show_alert("Upload completed, but unexpected response"), 0)
        except Exception as e:
            print("Error decoding JSON response:", e)
            Clock.schedule_once(lambda dt: show_alert(f"Upload failed: {e}"), 0)
    
    def send_text(self, instance):
        text = self.text_input.text.strip()
        if text:
            try:
                response = requests.post(f"{API_URL}/api/process_text", json={"text": text})
                if response.status_code == 200:
                    result = response.json()
                    print(result)
                    self.add_history("Text processed. Summary: " + result.get("summary", ""))
                    Clock.schedule_once(lambda dt: show_success("Process Completed and File Saved successfully"), 0)
                else:
                    Clock.schedule_once(lambda dt: show_alert("Text processed, but unexpected response"), 0)
            except requests.exceptions.ConnectionError:
                print("Backend server is not ready. Please try again shortly.")
                Clock.schedule_once(lambda dt: show_alert("Backend server is not ready. Please try again shortly."), 0)
            self.text_input.text = ""
    
    def open_file_chooser(self, instance):
        if os.name == 'nt':
            drives = []
            for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
            default_path = drives[0] if drives else "C:\\"
        else:
            default_path = "/storage/emulated/0"
        
        content = BoxLayout(orientation='vertical')
        top_bar = BoxLayout(orientation='horizontal', size_hint_y=0.15, padding=[5,5,5,5], spacing=5)
        back_button = Button(text="Back", size_hint_x=None, width=100)
        top_bar.add_widget(back_button)
        filechooser = FileChooserListView(path=default_path, filters=["*.wav", "*.mp3"])
        if os.name == 'nt':
            drive_spinner = Spinner(
                text=default_path,
                values=tuple(drives),
                size_hint_x=None,
                width=150
            )
            drive_spinner.bind(text=lambda spinner, text: setattr(filechooser, 'path', text))
            top_bar.add_widget(drive_spinner)
        else:
            top_bar.add_widget(Label(text="", size_hint_x=1))
        content.add_widget(top_bar)
        content.add_widget(filechooser)
        bottom_bar = BoxLayout(orientation='horizontal', size_hint_y=0.15, padding=[5,5,5,5])
        select_button = Button(text="Select", size_hint_x=None, width=100)
        bottom_bar.add_widget(select_button)
        bottom_bar.add_widget(Label(text="", size_hint_x=1))
        content.add_widget(bottom_bar)
        popup = Popup(title="Select an audio file", content=content, size_hint=(0.9, 0.9))
        back_button.bind(on_press=lambda inst: popup.dismiss())
        
        def on_select(inst):
            if filechooser.selection:
                file_path = filechooser.selection[0]
                threading.Thread(target=self.upload_file, args=(file_path,)).start()
                self.add_history("File uploaded: " + os.path.basename(file_path))
                popup.dismiss()
        select_button.bind(on_press=on_select)
        popup.open()
    
    def upload_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                files = {'audio_file': f}
                response = requests.post(f"{API_URL}/api/upload_audio", files=files)
            if response.status_code == 200:
                result = response.json()
                print(result)
                Clock.schedule_once(lambda dt: show_success("Process Completed and File Saved successfully"), 0)
            else:
                Clock.schedule_once(lambda dt: show_alert("File upload completed, but unexpected response"), 0)
        except Exception as e:
            print("Error uploading file:", e)
            Clock.schedule_once(lambda dt: show_alert(f"Upload failed: {e}"), 0)

class MeetingAssistantApp(App):
    def build(self):
        return VoiceInputInterface()

if __name__ == '__main__':
    MeetingAssistantApp().run()