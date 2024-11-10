from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.clock import Clock
from kivy.uix.popup import Popup
from datetime import datetime
import sqlite3
import os
from plyer import notification
import threading
import time
from kivy.utils import platform

# Mock classes for hardware control when running on Android
class MockGPIO:
    BCM = 'BCM'
    OUT = 'OUT'
    IN = 'IN'
    
    @staticmethod
    def setmode(mode):
        pass
    
    @staticmethod
    def setup(pin, mode):
        pass
    
    @staticmethod
    def output(pin, value):
        pass
    
    @staticmethod
    def input(pin):
        return 0
    
    @staticmethod
    def cleanup():
        pass

class MockPWM:
    def __init__(self, pin, freq):
        self.pin = pin
        self.freq = freq
    
    def start(self, dc):
        pass
    
    def ChangeDutyCycle(self, dc):
        pass
    
    def stop(self):
        pass

class MockDHT:
    @staticmethod
    def read_retry(sensor, pin):
        return 50, 25  # Mock humidity and temperature values

# Use real or mock hardware based on platform
if platform == 'android':
    GPIO = MockGPIO()
    DHT_SENSOR = None
    DHT_MODULE = MockDHT()
else:
    import RPi.GPIO as GPIO
    import Adafruit_DHT as DHT_MODULE
    DHT_SENSOR = DHT_MODULE.DHT22

# Pin definitions
SERVO_PIN = 18
DHT_PIN = 4
TRIG_PIN = 23
ECHO_PIN = 24

# Initialize GPIO if not on Android
if platform != 'android':
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(SERVO_PIN, GPIO.OUT)
    servo = GPIO.PWM(SERVO_PIN, 50)
    servo.start(0)
    GPIO.setup(TRIG_PIN, GPIO.OUT)
    GPIO.setup(ECHO_PIN, GPIO.IN)
else:
    servo = MockPWM(SERVO_PIN, 50)

class Database:
    def __init__(self):
        db_path = os.path.join(App.get_running_app().user_data_dir, 'pill_dispenser.db')
        self.conn = sqlite3.connect(db_path)
        self.create_tables()
    
    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                password TEXT,
                name TEXT,
                age INTEGER,
                birthday TEXT,
                address TEXT,
                blood_type TEXT,
                symptoms TEXT
            )
        ''')
        
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS pill_schedule (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                time TEXT,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        self.conn.commit()

[Previous screens remain the same: LoginScreen, RegisterScreen, MainScreen, ProfileScreen]

class ScheduleScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        self.time_input = TextInput(hint_text='Time (HH:MM)', multiline=False)
        self.date_input = TextInput(hint_text='Date (YYYY-MM-DD)', multiline=False)
        
        schedule_btn = Button(text='Set Schedule', size_hint_y=None, height=50)
        schedule_btn.bind(on_press=self.set_schedule)
        
        back_btn = Button(text='Back to Main', size_hint_y=None, height=50)
        back_btn.bind(on_press=self.goto_main)
        
        layout.add_widget(Label(text='Schedule Pills'))
        layout.add_widget(self.time_input)
        layout.add_widget(self.date_input)
        layout.add_widget(schedule_btn)
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
    
    def set_schedule(self, instance):
        try:
            user_id = App.get_running_app().current_user_id
            db = Database()
            db.conn.execute('''
                INSERT INTO pill_schedule (user_id, time, date)
                VALUES (?, ?, ?)
            ''', (user_id, self.time_input.text, self.date_input.text))
            db.conn.commit()
            self.show_popup('Success', 'Schedule set successfully!')
            
            # Schedule notification
            schedule_time = datetime.strptime(f"{self.date_input.text} {self.time_input.text}", 
                                           "%Y-%m-%d %H:%M")
            
            if platform == 'android':
                notification.schedule(
                    title='Pill Reminder',
                    message='Time to take your medication!',
                    ticker='Pill Reminder',
                    date=schedule_time
                )
        except Exception as e:
            self.show_popup('Error', str(e))
    
    def goto_main(self, instance):
        self.manager.current = 'main'
    
    def show_popup(self, title, content):
        popup = Popup(title=title, content=Label(text=content),
                     size_hint=(None, None), size=(400, 200))
        popup.open()

class StatusScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        self.temp_label = Label(text='Temperature: --°C')
        self.humidity_label = Label(text='Humidity: --%')
        self.container_label = Label(text='Container Status: --')
        
        back_btn = Button(text='Back to Main', size_hint_y=None, height=50)
        back_btn.bind(on_press=self.goto_main)
        
        layout.add_widget(Label(text='System Status'))
        layout.add_widget(self.temp_label)
        layout.add_widget(self.humidity_label)
        layout.add_widget(self.container_label)
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
        
        # Start sensor update schedule
        Clock.schedule_interval(self.update_sensors, 2)
    
    def measure_distance(self):
        if platform == 'android':
            return 10  # Mock distance value
        
        GPIO.output(TRIG_PIN, True)
        time.sleep(0.00001)
        GPIO.output(TRIG_PIN, False)
        
        start_time = time.time()
        stop_time = time.time()
        
        while GPIO.input(ECHO_PIN) == 0:
            start_time = time.time()
        
        while GPIO.input(ECHO_PIN) == 1:
            stop_time = time.time()
        
        time_elapsed = stop_time - start_time
        distance = (time_elapsed * 34300) / 2
        return distance
    
    def get_container_status(self, distance):
        if distance < 5:
            return "Full"
        elif distance < 15:
            return "Half-full"
        else:
            return "Empty"
    
    def update_sensors(self, dt):
        if platform == 'android':
            humidity, temperature = 50, 25  # Mock values
        else:
            humidity, temperature = DHT_MODULE.read_retry(DHT_SENSOR, DHT_PIN)
            
        if humidity is not None and temperature is not None:
            self.temp_label.text = f'Temperature: {temperature:.1f}°C'
            self.humidity_label.text = f'Humidity: {humidity:.1f}%'
        
        distance = self.measure_distance()
        container_status = self.get_container_status(distance)
        self.container_label.text = f'Container Status: {container_status}'
    
    def goto_main(self, instance):
        self.manager.current = 'main'

[PillDispenserApp class remains largely the same, with modified dispense_pill method]

if __name__ == '__main__':
    try:
        app = PillDispenserApp()
        app.run()
    except Exception as e:
        print(f"Error: {e}")
        if platform != 'android':
            servo.stop()
            GPIO.cleanup()
