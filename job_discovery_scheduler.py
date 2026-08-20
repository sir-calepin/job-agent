import importlib
import os
import time
from datetime import datetime, timezone

import requests
from apscheduler.schedulers.background import BackgroundScheduler


TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DISCOVERY_INTERVAL_MINUTES = int(os.environ.get("DISCOVERY_INTERVAL_MINUTES", "60"))
DISCOVERY_MODULE = os.environ.get("DISCOVERY_MODULE", "app.services.discovery_service")
DISCOVERY_FUNCTION = os.environ.get("DISCOVERY_FUNCTION", "run_job_discovery")


def send_telegram_message(text, disable_notification=False):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[ALERT DEBUG] Telegram credentials not set.")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_notification": disable_notification,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"[ALERT DEBUG] Telegram send failed: {e}")
        return False


def load_discovery_function():
    try:
        module = importlib.import_module(DISCOVERY_MODULE)
    except Exception as e:
        raise ImportError(
            f"Could not import module '{DISCOVERY_MODULE}'. "
            f"Run this script from your project root so the 'app' package is importable. "
            f"Original error: {e}"
        ) from e

    try:
        func = getattr(module, DISCOVERY_FUNCTION)
    except AttributeError as e:
        raise AttributeError(
            f"Module '{DISCOVERY_MODULE}' does not have a function named '{DISCOVERY_FUNCTION}'."
        ) from e

    if not callable(func):
        raise TypeError(
            f"'{DISCOVERY_FUNCTION}' in module '{DISCOVERY_MODULE}' is not callable."
        )

    return func


def format_summary(result):
    return (
        f"Discovered: {result.get('discovered_total', 0)} | "
        f"Missing URL: {result.get('missing_url_total', 0)} | "
        f"Unique: {result.get('unique_total', 0)} | "
        f"Recent: {result.get('recent_total', 0)} | "
        f"Preferred location: {result.get('preferred_total', 0)} | "
        f"Processed: {result.get('processed_total', 0)} | "
        f"New: {result.get('inserted_total', 0)} | "
        f"Duplicates skipped: {result.get('skipped_total', 0)} | "
        f"Alerts sent: {result.get('alerted_total', 0)}"
    )


def run_discovery_once():
    started_at = datetime.now(timezone.utc).isoformat()
    print(f"[SCHEDULER] Discovery started at {started_at}")
    print(f"[SCHEDULER] Using {DISCOVERY_MODULE}.{DISCOVERY_FUNCTION}()")

    try:
        run_job_discovery = load_discovery_function()
        result = run_job_discovery()

        if not isinstance(result, dict):
            raise ValueError(
                "run_job_discovery() must return a dictionary with keys like "
                "discovered_total, recent_total, preferred_total, processed_total, inserted_total"
            )

        print("[SCHEDULER] Discovery finished")
        print(format_summary(result))
        return result
    except Exception as e:
        print(f"[SCHEDULER DEBUG] discovery failed: {e}")
        return None


def scheduled_discovery():
    result = run_discovery_once()
    if not result:
        return

    inserted_total = result.get("inserted_total", 0)
    recent_total = result.get("recent_total", 0)
    preferred_total = result.get("preferred_total", 0)
    processed_total = result.get("processed_total", 0)

    if inserted_total > 0:
        message = (
            f"Job alert: {inserted_total} new match(es)\n"
            f"Recent: {recent_total}\n"
            f"Preferred location: {preferred_total}\n"
            f"Processed: {processed_total}\n\n"
            f"{format_summary(result)}"
        )
        sent = send_telegram_message(message, disable_notification=False)
        if sent:
            print("[SCHEDULER] Telegram alert sent")
        else:
            print("[SCHEDULER] Telegram alert failed")
    else:
        print("[SCHEDULER] No new jobs found; no Telegram alert sent")



def start_scheduler():
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        scheduled_discovery,
        trigger="interval",
        minutes=DISCOVERY_INTERVAL_MINUTES,
        id="job_discovery",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    print(f"[SCHEDULER] Started every {DISCOVERY_INTERVAL_MINUTES} minutes")
    return scheduler


if __name__ == "__main__":
    scheduler = start_scheduler()
    scheduled_discovery()
    try:
        while True:
            time.sleep(5)
    except KeyboardInterrupt:
        scheduler.shutdown(wait=False)
        print("[SCHEDULER] Stopped")