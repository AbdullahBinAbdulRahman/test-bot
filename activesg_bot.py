import argparse
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

BASE_URL = "https://activesg.gov.sg/facility-bookings/ballots/review"
# Venue IDs
BISHAN_VENUE_ID = "GdiZXcMkIKELrCkd90qBP"
MOE_EVANS_VENUE_ID = "kEBJKrx1USi4BvQxwMMHs"
ACTIVITY_ID = "YLONatwvqJfikKOmB5N9U"

DAYS_AHEAD = 14
# Weekday slots: 8pm-9pm (displayed as 8-10pm for two 1-hour slots)
WEEKDAY_START_HOUR = 20
WEEKDAY_END_HOUR = 21
# Weekend slots: 5pm-6pm (displayed as 5-7pm for two 1-hour slots)
WEEKEND_START_HOUR = 17
WEEKEND_END_HOUR = 18


def get_env(name, default=None, required=False):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def build_booking_url(start_ms, end_ms, venue_id, activity_id):
    return (
        f"{BASE_URL}"
        f"?timeslot={start_ms}"
        f"&timeslot={end_ms}"
        f"&venueId={venue_id}"
        f"&activityId={activity_id}"
    )


def compute_timeslots(now_sgt, days_ahead, start_hour, end_hour):
    target = now_sgt + timedelta(days=days_ahead)
    start_dt = target.replace(hour=start_hour, minute=0, second=0, microsecond=0)
    end_dt = target.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    start_ms = int(start_dt.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    return start_dt, end_dt, start_ms, end_ms


def send_telegram(token, chat_id, message):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": message,
            "disable_web_page_preview": True,
        },
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f"Telegram API error: {response.status_code} {response.text}")


def main():
    parser = argparse.ArgumentParser(
        description="Send ActiveSG booking reminders via Telegram."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the message instead of sending to Telegram.",
    )
    args = parser.parse_args()

    try:
        sgt = ZoneInfo("Asia/Singapore")
    except ZoneInfoNotFoundError as exc:
        raise RuntimeError(
            "Timezone data missing. Install the 'tzdata' package."
        ) from exc

    now = datetime.now(sgt)
    bot_token = get_env("BOT_TOKEN", required=True)
    chat_id = get_env("CHAT_ID", required=True)
    
    # Determine if target booking day is weekend or weekday
    target_date = now + timedelta(days=DAYS_AHEAD)
    target_weekday = target_date.weekday()  # 0=Monday, 1=Tuesday, ..., 6=Sunday
    is_weekend = target_weekday >= 5
    
    # Determine venue and location based on day of week
    if target_weekday in [0, 2]:  # Monday or Wednesday
        venue_id = MOE_EVANS_VENUE_ID
        location = "MOE (Evans) Sport Hall"
    else:  # Tuesday, Thursday, Friday, Saturday, Sunday
        venue_id = BISHAN_VENUE_ID
        location = "Bishan Clubhouse"
    
    if is_weekend:
        start_hour, end_hour = WEEKEND_START_HOUR, WEEKEND_END_HOUR
    else:
        start_hour, end_hour = WEEKDAY_START_HOUR, WEEKDAY_END_HOUR
    
    start_dt, end_dt, start_ms, end_ms = compute_timeslots(
        now, DAYS_AHEAD, start_hour, end_hour
    )
    booking_url = build_booking_url(start_ms, end_ms, venue_id, ACTIVITY_ID)

    start_time = start_dt.strftime("%I:%M %p").lstrip("0")
    display_end_dt = end_dt + timedelta(hours=1)
    end_time = display_end_dt.strftime("%I:%M %p").lstrip("0")

    message = (
        "ActiveSG Booking Reminder\n\n"
        f"Location: {location}\n"
        f"Date: {start_dt.strftime('%A, %d %b %Y')}\n"
        f"Time: {start_time} - {end_time}\n\n"
        f"Book now:\n{booking_url}"
    )

    if args.dry_run:
        print(message)
        return

    send_telegram(bot_token, chat_id, message)
    print("Reminder sent.")


if __name__ == "__main__":
    main()
