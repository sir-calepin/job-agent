from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.notifications.telegram_bot import send_telegram_message

result = send_telegram_message("Test message from AI Job Agent")
print(result)