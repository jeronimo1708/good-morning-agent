import requests
from PIL import Image, ImageDraw, ImageFont
import os
import schedule
import time
from dotenv import load_dotenv
import random # For choosing different image search terms
import telegram
from telegram.error import TelegramError
import asyncio


#TODO:
# 1. Replace prints with logging for better traceability.
# 2. Replace whatsapp with telegram bots.
load_dotenv()
# --- Configuration ---
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY")
WHATSAPP_RECIPIENT_NUMBER = os.getenv("WHATSAPP_RECIPIENT_NUMBER")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Time to send the message daily (24-hour format, HH:MM)
SEND_TIME = os.getenv("SEND_TIME") # Example: 7:30 AM

# Path to save temporary images
TEMP_IMAGE_PATH = "good_morning_temp_image.png"
FINAL_IMAGE_PATH = "final_good_morning_quote.png"

# Font settings
# Common paths for Arial:
# Windows: "C:/Windows/Fonts/arial.ttf"
# macOS: "/Library/Fonts/Arial.ttf" or "/System/Library/Fonts/Arial.ttf"
# Linux: "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" (or a similar path)
# This is Pillow's Pillow's default:
# font = ImageFont.load_default()
try:
    # Try a common path for Arial font
    FONT_PATH = "C:/Windows/Fonts/arial.ttf"  # Default for Windows
    if os.name == 'posix': # For macOS/Linux
        if os.path.exists("/Library/Fonts/Arial Unicode.ttf"):
            FONT_PATH = "/Library/Fonts/Arial Unicode.ttf"
        elif os.path.exists("/System/Library/Fonts/NewYork.ttf"):
            FONT_PATH = "/System/Library/Fonts/NewYork.ttf"
        else: # Fallback for Linux or if Arial is not found
            FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
except Exception:
    FONT_PATH = None # Will fall back to default if path not found

# --- Functions ---

def get_quote():
    """Fetches a random quote from ZenQuotes API."""
    try:
        response = requests.get("https://zenquotes.io/api/random")
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        data = response.json()[0]
        return {
            "q": data["q"], # Quote
            "a": data["a"]  # Author
        }
    except requests.exceptions.RequestException as e:
        print(f"Error fetching quote: {e}")
        return {"q": "Stay positive and happy.", "a": "A well-wisher"} # Fallback quote

def download_unsplash_image(query="nature landscape sunrise", count=1):
    """Downloads a random image from Unsplash based on query."""
    search_terms = [
        "nature landscape", "sunrise", "beautiful morning", "peaceful scenery",
        "good morning light", "calm ocean", "mountain view", "forest path",
        "flowers dew", "coffee morning"
    ]
    chosen_query = random.choice(search_terms)

    url = f"https://api.unsplash.com/photos/random?query={chosen_query}&count={count}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        if data and isinstance(data, list) and len(data) > 0:
            image_url = data[0]["urls"]["small"]
            image_response = requests.get(image_url, stream=True)
            image_response.raise_for_status()
            with open(TEMP_IMAGE_PATH, 'wb') as f:
                for chunk in image_response.iter_content(1024):
                    f.write(chunk)
            print(f"Downloaded image from Unsplash (query: '{chosen_query}').")
            return TEMP_IMAGE_PATH
        else:
            print("No image found for the query on Unsplash.")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error downloading image from Unsplash: {e}")
        return None
    except IndexError:
        print("Unsplash API returned empty data for image.")
        return None

def add_text_to_image(image_path, quote, author, output_path, good_morning_text="Good Morning!"):
    """Adds 'Good Morning!', a quote, and author to an image."""
    try:
        img = Image.open(image_path).convert("RGBA") # Ensure it's RGBA for transparency
        draw = ImageDraw.Draw(img)
        width, height = img.size

        # --- Define fonts ---
        # Good Morning text font
        try:
            gm_font_size = int(height * 0.08)
            gm_font = ImageFont.truetype(FONT_PATH, gm_font_size) if FONT_PATH else ImageFont.load_default(gm_font_size)
        except Exception:
            gm_font = ImageFont.load_default(int(height * 0.08)) # Fallback if font path fails

        # Quote text font
        try:
            quote_font_size = int(height * 0.05)
            quote_font = ImageFont.truetype(FONT_PATH, quote_font_size) if FONT_PATH else ImageFont.load_default(quote_font_size)
        except Exception:
            quote_font = ImageFont.load_default(int(height * 0.05)) # Fallback if font path fails

        # Author text font
        try:
            author_font_size = int(height * 0.03)
            author_font = ImageFont.truetype(FONT_PATH, author_font_size) if FONT_PATH else ImageFont.load_default(int(height * 0.03))
        except Exception:
            author_font = ImageFont.load_default(int(height * 0.03)) # Fallback if font path fails

        text_color = "white" # White text for contrast

        # --- Add 'Good Morning!' text ---
        # Calculate text bounding box to center
        try:
            bbox_gm = draw.textbbox((0,0), good_morning_text, font=gm_font)
            gm_text_width = bbox_gm[2] - bbox_gm[0]
            gm_text_height = bbox_gm[3] - bbox_gm[1]
        except AttributeError: # For older Pillow versions
            gm_text_width, gm_text_height = draw.textsize(good_morning_text, font=gm_font)

        gm_x = (width - gm_text_width) / 2
        gm_y = height * 0.1 # 10% from the top

        # Add a subtle background for readability
        # draw.rectangle([gm_x - 10, gm_y - 10, gm_x + gm_text_width + 10, gm_y + gm_text_height + 10], fill=(0,0,0,128)) # Semi-transparent black
        draw.text((gm_x, gm_y), good_morning_text, font=gm_font, fill=text_color)


        # --- Add Quote and Author ---
        # Wrap quote text if too long
        max_quote_width = width * 0.8
        lines = []
        words = quote.split(' ')
        current_line = []
        for word in words:
            # Check length if word added to current_line
            test_line = " ".join(current_line + [word])
            try:
                bbox_test = draw.textbbox((0,0), test_line, font=quote_font)
                test_width = bbox_test[2] - bbox_test[0]
            except AttributeError:
                test_width, _ = draw.textsize(test_line, font=quote_font)

            if test_width < max_quote_width:
                current_line.append(word)
            else:
                if current_line: # Add current line if not empty
                    lines.append(" ".join(current_line))
                current_line = [word] # Start new line with the current word
        if current_line: # Add any remaining words
            lines.append(" ".join(current_line))

        # Calculate total height of quote lines
        total_quote_height = 0
        quote_line_heights = []
        for line in lines:
            try:
                bbox_line = draw.textbbox((0,0), line, font=quote_font)
                line_height = bbox_line[3] - bbox_line[1]
            except AttributeError:
                _, line_height = draw.textsize(line, font=quote_font)
            total_quote_height += line_height
            quote_line_heights.append(line_height)

        # Calculate total height for quote and author
        try:
            bbox_author = draw.textbbox((0,0), f"- {author}", font=author_font)
            author_height = bbox_author[3] - bbox_author[1]
        except AttributeError:
            _, author_height = draw.textsize(f"- {author}", font=author_font)

        total_text_block_height = total_quote_height + author_height + (len(lines) * 5) # Add small padding between lines
        text_start_y = height - total_text_block_height - (height * 0.05) # 5% from bottom

        # Draw quote lines
        current_y = text_start_y
        for i, line in enumerate(lines):
            try:
                bbox_line = draw.textbbox((0,0), line, font=quote_font)
                line_width = bbox_line[2] - bbox_line[0]
            except AttributeError:
                line_width, _ = draw.textsize(line, font=quote_font)

            line_x = (width - line_width) / 2
            draw.text((line_x, current_y), line, font=quote_font, fill=text_color)
            current_y += quote_line_heights[i] + 5 # Move to next line, add 5px padding

        # Draw author
        author_text = f"- {author}"
        try:
            bbox_author = draw.textbbox((0,0), author_text, font=author_font)
            author_width = bbox_author[2] - bbox_author[0]
        except AttributeError:
            author_width, _ = draw.textsize(author_text, font=author_font)

        author_x = (width - author_width) / 2
        draw.text((author_x, current_y), author_text, font=author_font, fill=text_color)

        # Save the modified image
        img.save(output_path, quality=95)
        print(f"Text added to image and saved to {output_path}")
        return output_path

    except FileNotFoundError:
        print(f"Error: Font file not found at {FONT_PATH}. Using default font.")
        # Fallback to default font if the specified font path is incorrect
        # This block is for recovery, a more robust solution would be to use
        # ImageFont.load_default() from the start if FONT_PATH is None.
        # For simplicity, if this occurs, you might want to uncomment and debug,
        # or handle it gracefully to use a default font throughout.
        print("Please ensure your FONT_PATH is correct or remove it to use Pillow's default.")
        return None
    except Exception as e:
        print(f"Error processing image with text: {e}")
        return None
    
# --- NEW: Function to send via Telegram ---
async def send_telegram_media(image_path, chat_id, bot_token, message_text=""):
    """Sends the image as a Telegram message."""
    # print(f"DEBUG: Attempting to send image '{image_path}'")
    # print(f"DEBUG: Using Chat ID: {chat_id}")
    # print(f"DEBUG: Bot Token (first 5 chars): {bot_token[:5]}...")
    # print(f"DEBUG: Caption: {message_text[:50]}...")
    try:
        bot = telegram.Bot(token=bot_token)
        # We need to open the file in binary read mode ('rb') to send it.
        with open(image_path, 'rb') as photo_file:
            await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=message_text)
        print(f"Telegram message (image and caption) sent to chat ID {chat_id}.")
    except TelegramError as e:
        print(f"Failed to send Telegram message: {e}")
        print("Please ensure your BOT_TOKEN and CHAT_ID are correct and your bot has been started by the recipient.")
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path} for Telegram.")
    except Exception as e:
        print(f"An unexpected error occurred while sending Telegram message: {e}")

# def send_whatsapp_media(image_path, recipient_number, message_text=""):
#     """Sends the image as a WhatsApp message."""
#     try:
#         # Pywhatkit doesnt run headless on a server, it requires a browser to be open.
#         # I want to run this on a server, so I will use Telegram instead.


#         # For sending image with a caption:
#         # pywhatkit.sendwhats_image(phone_no=recipient_number, img_path=image_path, caption=message_text, wait_time=20)
#         # Note: pywhatkit often requires the browser to be open and WhatsApp Web to be logged in.
#         # It opens a new browser tab.
#         print(f"Attempting to send image to {recipient_number}...")
        
#         pywhatkit.sendwhats_image(
#             phone_no=recipient_number,
#             img_path=image_path,
#             caption=message_text,
#             wait_time=15,  # Time in seconds to wait for WhatsApp Web to load
#             tab_close=True # Close the tab after sending
#         )
#         print("WhatsApp message scheduled. Check your browser.")
#         time.sleep(5) # Give it a moment to process in case tab_close is too fast
#     except Exception as e:
#         print(f"Failed to send WhatsApp message: {e}")
#         print("Please ensure you are logged into WhatsApp Web in your default browser.")


def daily_good_morning_task():
    """Combines all steps to perform the daily task."""
    print(f"\n--- Running daily good morning task at {time.ctime()} ---")
    
    quote_data = get_quote()
    if not quote_data:
        print("Could not get a quote. Aborting.")
        return

    good_morning_message = "Good Morning!"
    full_message_caption = f"{good_morning_message}\n\n'{quote_data['q']}'\n- {quote_data['a']}"
    
    downloaded_img = download_unsplash_image()
    if not downloaded_img:
        print("Could not download image. Aborting.")
        return

    final_image = add_text_to_image(downloaded_img, quote_data['q'], quote_data['a'], FINAL_IMAGE_PATH, good_morning_text="Good Morning!")
    if not final_image:
        print("Could not add text to image. Aborting.")
        return

    # Call the new Telegram sending function
    # send_telegram_media(final_image, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN, message_text=full_message_caption)
    # Call the new Telegram sending function using asyncio.run()
    asyncio.run(send_telegram_media(final_image, TELEGRAM_CHAT_ID, TELEGRAM_BOT_TOKEN))

    # Clean up temporary files
    if os.path.exists(TEMP_IMAGE_PATH):
        os.remove(TEMP_IMAGE_PATH)
        print(f"Removed temporary file: {TEMP_IMAGE_PATH}")
    if os.path.exists(FINAL_IMAGE_PATH):
        # We might want to keep the final image for a day or two for debugging/review,
        # or remove it immediately. For daily automation, removing it is clean.
        os.remove(FINAL_IMAGE_PATH)
        print(f"Removed final image file: {FINAL_IMAGE_PATH}")
    
    print("--- Daily task completed ---")


# --- Scheduling the Task ---
if __name__ == "__main__":
    # For testing, we can uncomment this line to run it once immediately
    # daily_good_morning_task()

    # Schedule the task to run every day at the specified time
    schedule.every().day.at(SEND_TIME).do(daily_good_morning_task)
    print(f"Script scheduled to send good morning messages every day at {SEND_TIME}.")
    print("Keep this script running in the background for it to work.")
    print("Press Ctrl+C to stop.")

    while True:
        schedule.run_pending()
        time.sleep(1) # Wait for 1 second before checking pending jobs again