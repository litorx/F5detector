import pyautogui 
import time
from PIL import ImageChops, Image, ImageStat, ImageFilter
import os
import pygetwindow as gw
from twilio.rest import Client
from flask import Flask, request, send_from_directory

# Configuration
num_screens = 3
screenshots_dir = os.path.abspath("screenshots")
correct_screenshots_dir = os.path.abspath("CorrectScreenshots")
if not os.path.exists(correct_screenshots_dir):
    os.makedirs(correct_screenshots_dir)

difference_limit = 70000
delay = 20
whatsapp_number = "whatsapp:+"  # Your number in international format
twilio_number = "whatsapp:+14155238886"  # Twilio's WhatsApp number

# Twilio credentials
account_sid = "(your here)"
auth_token = "(your here)"
client = Client(account_sid, auth_token)

# Initialize Flask server for webhoo
app = Flask(__name__)
should_stop = False
awaiting_response = False
last_detected_screen = None
paused = False

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
        message_data["media_url"] = f"https://1cf6-2804-7f0-20-1fc1-2d13-5b11-2b82-1265.ngrok-free.app/{os.path.basename(image_path)}"
    client.messages.create(**message_data)

@app.route("/<filename>")
def serve_file(filename):
    return send_from_directory(os.path.abspath("."), filename)

@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    global should_stop, awaiting_response, last_detected_screen, paused
    message_body = request.form.get("Body").strip().lower()
    if message_body == "ok":
        screenshot = pyautogui.screenshot()
        screenshot_path = os.path.join(correct_screenshots_dir, f"correct_screen_{int(time.time())}.png")
        screenshot.save(screenshot_path)
        print(f"Screenshot saved to CorrectScreenshots: {screenshot_path}")
        paused = True
    elif message_body in ["errou"]:
        os.rename("temp_screenshot.png", os.path.join(screenshots_dir, f"screen{int(time.time())}.png"))
        last_detected_screen = None
        paused = False
        print("Resuming the program and saving the screenshot.")
    elif message_body == "pausar":
        paused = True
        print("Program paused.")
    elif message_body == "voltar":
        paused = False
        print("Program on-line.")
    elif message_body == "deletar":
        os.remove("temp_screenshot.png")
        print("Screenshot deleted successfully.")
    awaiting_response = False
    return "OK", 200

def main():
    global should_stop, awaiting_response, last_detected_screen, paused
    current_screen = 1
    print("Starting script...")

    while True:
        if should_stop:
            print("Stopping script as per user confirmation.")
            break

        if awaiting_response or paused:
            print("Program is paused. Waiting for 'voltar' or 'errou' command...")
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
