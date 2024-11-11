import pyautogui
import time
from PIL import ImageChops, Image, ImageStat, ImageFilter
import os
import pygetwindow as gw
from twilio.rest import Client
from flask import Flask, request, send_from_directory

# Configuration
num_screens = 7
screenshots_dir = os.path.abspath("screenshots")
difference_limit = 100000
delay = 15
whatsapp_number = "whatsapp:+(number)"  # Your number in international format
twilio_number = "whatsapp:+(number)"  # Twilio's WhatsApp number

# Twilio credentials
account_sid = "(sid)"
auth_token = "(token)"
client = Client(account_sid, auth_token)

# Initialize Flask server for webhook
app = Flask(__name__)
should_stop = False
awaiting_response = False
last_detected_screen = None

def is_vscode_window(window):
    return window and ("Visual Studio Code" in window.title or "Code" in window.title)

def refresh_screen():
    pyautogui.press('f5')
    time.sleep(delay)

def switch_screen(current_screen):
    vscode_windows = [window for window in gw.getAllWindows() if is_vscode_window(window)]
    pyautogui.keyDown('alt')
    tabs = 0
    while tabs < current_screen - 1:
        pyautogui.press('tab')
        time.sleep(0.1)
        current_window = gw.getActiveWindow()
        if current_window and any(current_window == window for window in vscode_windows):
            continue
        tabs += 1
    pyautogui.keyUp('alt')
    time.sleep(0.5)

def is_different_from_all_screenshots(current_image):
    current_image = current_image.convert("L").filter(ImageFilter.GaussianBlur(2))
    
    for image_name in os.listdir(screenshots_dir):
        image_path = os.path.join(screenshots_dir, image_name)
        if os.path.isfile(image_path):
            saved_image = Image.open(image_path).convert("L").filter(ImageFilter.GaussianBlur(2))
            
            if saved_image.size != current_image.size:
                saved_image = saved_image.resize(current_image.size)
            
            diff = ImageChops.difference(saved_image, current_image)
            stat = ImageStat.Stat(diff)
            diff_sum = sum(stat.sum)
            
            if diff_sum < difference_limit:
                print(f"Current screen matches saved screenshot: {image_name} (small difference)")
                return False
    return True

def check_for_change(current_screen):
    screenshot = pyautogui.screenshot()
    screenshot_path = "temp_screenshot.png"
    screenshot.save(screenshot_path)
    current_image = Image.open(screenshot_path)
    
    if is_different_from_all_screenshots(current_image):
        send_whatsapp_message("A change was detected on the screen.", screenshot_path)
        return False
    return True

def send_whatsapp_message(message, image_path=None):
    message_data = {
        "body": message,
        "from_": twilio_number,
        "to": whatsapp_number
    }
    if image_path:
        message_data["media_url"] = f"(your ngrok server) /{os.path.basename(image_path)}" #Link ngrok server
    client.messages.create(**message_data)

@app.route("/<filename>")
def serve_file(filename):
    return send_from_directory(os.path.abspath("."), filename)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    global should_stop, awaiting_response, last_detected_screen
    message_body = request.form.get("Body").strip().lower()
    if message_body == "ok":
        should_stop = True
    elif message_body == "errou":
        os.rename("temp_screenshot.png", os.path.join(screenshots_dir, f"screen{int(time.time())}.png"))
        last_detected_screen = None
    elif message_body == "deletar":
        os.remove("temp_screenshot.png")
        print("Screenshot deleted successfully.")
    awaiting_response = False
    return "OK", 200

def main():
    global should_stop, awaiting_response, last_detected_screen
    current_screen = 1
    print("Starting script...")

    while True:
        if should_stop:
            print("Stopping script as per user confirmation.")
            break

        if awaiting_response:
            time.sleep(5)
            continue

        refresh_screen()
        
        if not check_for_change(current_screen):
            if last_detected_screen != current_screen:
                print(f"Different screen detected at screen {current_screen}")
                last_detected_screen = current_screen
                awaiting_response = True

        current_screen += 1
        if current_screen > num_screens:
            current_screen = 1
        switch_screen(current_screen)

if __name__ == "__main__":
    from threading import Thread
    Thread(target=lambda: app.run(port=5000)).start()
    main()
