import argparse
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

BASE_URL = "https://activesg.gov.sg/facility-bookings/ballots/review"
# Venue IDs
BISHAN_CLUBHOUSE_VENUE_ID = "GdiZXcMkIKELrCkd90qBP"
BISHAN_SPORTS_HALL_VENUE_ID = "LpiaS3dnMUXa39CrtTm9w"
ACTIVITY_ID = "YLONatwvqJfikKOmB5N9U"

DAYS_AHEAD = 14
# Weekday slots: 8pm-10pm (displayed as 8-10pm for two 1-hour slots)
WEEKDAY_FIRST_HOUR = 20
WEEKDAY_SECOND_HOUR = 21
# Weekend slots: 4pm-6pm (displayed as 4-6pm for two 1-hour slots)
WEEKEND_FIRST_HOUR = 16
WEEKEND_SECOND_HOUR = 17


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
    is_weekend = target_date.weekday() >= 5
    
    if is_weekend:
        start_hour, end_hour = WEEKEND_FIRST_HOUR, WEEKEND_SECOND_HOUR
    else:
        start_hour, end_hour = WEEKDAY_FIRST_HOUR, WEEKDAY_SECOND_HOUR
    
    start_dt, end_dt, start_ms, end_ms = compute_timeslots(
        now, DAYS_AHEAD, start_hour, end_hour
    )
    
    # Create booking URLs for both venues
    clubhouse_url = build_booking_url(start_ms, end_ms, BISHAN_CLUBHOUSE_VENUE_ID, ACTIVITY_ID)
    sports_hall_url = build_booking_url(start_ms, end_ms, BISHAN_SPORTS_HALL_VENUE_ID, ACTIVITY_ID)

    start_time = start_dt.strftime("%I:%M %p").lstrip("0")
    display_end_dt = end_dt + timedelta(hours=1)
    end_time = display_end_dt.strftime("%I:%M %p").lstrip("0")

    message = (
        "ActiveSG Booking Reminder\n\n"
        f"Date: {start_dt.strftime('%A, %d %b %Y')}\n"
        f"Time: {start_time} - {end_time}\n\n"
        f"Book now (Bishan Clubhouse):\n{clubhouse_url}\n\n"
        f"If this link does not work, book the Bishan Sports Hall instead:\n{sports_hall_url}"
    )

    if args.dry_run:
        print(message)
        return

    send_telegram(bot_token, chat_id, message)
    print("Reminder sent.")


if __name__ == "__main__":
    main()
