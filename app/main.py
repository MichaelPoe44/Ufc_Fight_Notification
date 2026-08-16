import re
import time
import sys
import platform
import os
from datetime import datetime, date

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from notifypy import Notify
import pygame




# ============================================================
# SETTINGS
# ============================================================

CHECK_INTERVAL = 60  # Check once every 60 seconds

SHERDOG_EVENTS_URL = "https://www.sherdog.com/events"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/139.0.0.0 Safari/537.36"
)


# ============================================================
# NOTIFICATION
# ============================================================

def send_notification(target_fight, previous_fight):
    SOUND_FILE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "sound.mp3"
    )

    print()
    print("=" * 65)
    print("🔔 YOUR UFC FIGHT IS NEXT")
    print("=" * 65)
    print(f"Your fight:")
    print(f"  {target_fight}")
    print()
    print(f"Preceding fight finished:")
    print(f"  {previous_fight}")
    print("=" * 65)

    # --------------------------------------------------------
    # Desktop notification
    # --------------------------------------------------------

    notification = Notify()

    notification.title = "🥊 YOUR FIGHT IS NEXT"

    notification.message = (
        f"{target_fight}\n"
        f"The preceding fight has ended!"
    )

    notification.send()

    # --------------------------------------------------------
    # Play MP3
    # --------------------------------------------------------

    if not os.path.exists(SOUND_FILE):

        print()
        print(f"ERROR: Could not find {SOUND_FILE}")
        print(
            "Make sure sound.mp3 is in the same "
            "folder as main.py."
        )

        return

    try:

        pygame.mixer.init()

        pygame.mixer.music.load(SOUND_FILE)
        pygame.mixer.music.play()

        print("Playing UFC alert sound...")

        # Wait until the sound finishes
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)

        pygame.mixer.quit()

    except Exception as e:

        print()
        print(f"Could not play notification sound: {e}")


# ============================================================
# FIND UPCOMING UFC EVENT
# ============================================================

def find_next_ufc_event(page):
    print()
    print("Looking for the next UFC event...")

    page.goto(
        SHERDOG_EVENTS_URL,
        wait_until="domcontentloaded",
        timeout=30000
    )

    page.wait_for_timeout(2000)

    today = date.today()

    # Sherdog's event page contains event links.
    links = page.locator('a[href*="/events/"]')

    events = []

    for i in range(links.count()):

        link = links.nth(i)

        try:
            name = link.inner_text().strip()
            href = link.get_attribute("href")

            if not href:
                continue

            if not name:
                continue

            # Only UFC events
            parent_text = ""

            try:
                parent_text = link.locator("xpath=..").inner_text()
            except Exception:
                pass

            combined = f"{name} {parent_text}"

            if "UFC" not in combined.upper():
                continue

            # Look for a date such as:
            # Aug 15 2026
            # Sep 05 2026
            match = re.search(
                r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                r"\s+\d{1,2}\s+\d{4}",
                combined
            )

            if not match:
                continue

            date_text = match.group(0)

            try:
                event_date = datetime.strptime(
                    date_text,
                    "%b %d %Y"
                ).date()
            except ValueError:
                continue

            if event_date < today:
                continue

            full_url = href

            if href.startswith("/"):
                full_url = "https://www.sherdog.com" + href

            # Avoid duplicates
            already_found = any(
                event["url"] == full_url
                for event in events
            )

            if not already_found:
                events.append(
                    {
                        "name": name,
                        "date": event_date,
                        "url": full_url
                    }
                )

        except Exception:
            continue

    if not events:
        raise RuntimeError(
            "Could not find an upcoming UFC event on Sherdog."
        )

    # Earliest upcoming UFC event
    events.sort(key=lambda x: x["date"])

    event = events[0]

    print()
    print("Found:")
    print(f"  {event['name']}")
    print(
        f"  Date: {event['date'].strftime('%A, %B %d, %Y')}"
    )
    print(f"  URL: {event['url']}")

    return event


# ============================================================
# GET FIGHT CARD
# ============================================================
def get_fight_card(page, event):
    print()
    print("Loading fight card...")

    page.goto(
        event["url"],
        wait_until="domcontentloaded",
        timeout=30000
    )

    page.wait_for_timeout(2500)

    fighter_links = page.locator(
        'a[href*="/fighter/"]'
    )

    fighter_names = []

    for i in range(fighter_links.count()):

        try:
            name = fighter_links.nth(i).inner_text()

            # Clean up line breaks and extra spaces
            name = re.sub(r"\s+", " ", name).strip()

            if not name:
                continue

            if len(name) > 60:
                continue

            fighter_names.append(name)

        except Exception:
            continue

    # --------------------------------------------------------
    # Remove consecutive duplicates
    # --------------------------------------------------------

    cleaned = []

    for name in fighter_names:

        if not cleaned or name.lower() != cleaned[-1].lower():
            cleaned.append(name)

    fighter_names = cleaned

    # --------------------------------------------------------
    # Pair fighters together
    # --------------------------------------------------------

    fights = []

    for i in range(0, len(fighter_names) - 1, 2):

        fighter1 = fighter_names[i]
        fighter2 = fighter_names[i + 1]

        fight = (
            f"{fighter1} VS {fighter2}"
        )

        fights.append(fight)

    # --------------------------------------------------------
    # Remove duplicate fights
    # --------------------------------------------------------

    unique_fights = []

    seen = set()

    for fight in fights:

        normalized = fight.lower()

        if normalized not in seen:
            seen.add(normalized)
            unique_fights.append(fight)

    # --------------------------------------------------------
    # SHERDOG RETURNS THE CARD BACKWARDS
    #
    # Reverse it so Fight #1 is the first fight of the night
    # and the main event is the final fight.
    # --------------------------------------------------------

    unique_fights.reverse()

    # --------------------------------------------------------
    # FULL CAPS + clean whitespace
    # --------------------------------------------------------

    final_fights = []

    for fight in unique_fights:

        fight = re.sub(r"\s+", " ", fight).strip()

        fight = fight.upper()

        if fight not in final_fights:
            final_fights.append(fight)

    if not final_fights:

        raise RuntimeError(
            "I found the UFC event, but couldn't extract "
            "its fight card."
        )

    print()
    print("Fight card found:")
    print()

    for i, fight in enumerate(final_fights, 1):
        print(f"{i:2}. {fight}")

    return final_fights

# ============================================================
# SELECT FIGHT
# ============================================================

def select_fight(fights):

    print()
    print("=" * 65)
    print("SELECT YOUR FIGHT")
    print("=" * 65)

    for i, fight in enumerate(fights, 1):
        print(f"{i:2}. {fight}")

    print()

    while True:

        choice = input(
            "Enter the number of the fight you want "
            "to be notified for: "
        ).strip()

        try:
            number = int(choice)

            if 1 <= number <= len(fights):
                return number - 1

        except ValueError:
            pass

        print(
            f"Please enter a number between 1 and {len(fights)}."
        )


# ============================================================
# CHECK WHETHER A FIGHT IS COMPLETE
# ============================================================

def fight_is_complete(page, fight):

    """
    Check whether a specific fight has an official result
    on Sherdog's live results page.
    """

    # --------------------------------------------------------
    # Split our fight string
    # --------------------------------------------------------

    fighter_parts = re.split(
        r"\s+VS\s+",
        fight,
        flags=re.IGNORECASE
    )

    if len(fighter_parts) != 2:

        print("Could not split fight:")
        print(fight)

        return False

    fighter1 = fighter_parts[0].strip()
    fighter2 = fighter_parts[1].strip()

    print()
    print("Checking fight:")
    print(f"  Fighter 1: {fighter1}")
    print(f"  Fighter 2: {fighter2}")

    # --------------------------------------------------------
    # Get ALL page text
    # --------------------------------------------------------

    body = page.locator("body").inner_text()

    body = re.sub(r"\s+", " ", body)

    body_lower = body.lower()

    fighter1_lower = fighter1.lower()
    fighter2_lower = fighter2.lower()

    # --------------------------------------------------------
    # Find both possible fighter orders
    #
    # Sherdog might show:
    #
    # Jalin Turner vs Kaue Fernandes
    #
    # OR:
    #
    # Kaue Fernandes vs Jalin Turner
    # --------------------------------------------------------

    pattern1 = re.escape(fighter1_lower) + r".{0,150}?" + re.escape(fighter2_lower)

    pattern2 = re.escape(fighter2_lower) + r".{0,150}?" + re.escape(fighter1_lower)

    match = re.search(
        pattern1,
        body_lower,
        flags=re.IGNORECASE
    )

    if not match:

        match = re.search(
            pattern2,
            body_lower,
            flags=re.IGNORECASE
        )

    if not match:

        print()
        print("❌ Could not find both fighters together.")
        print(f"Looking for:")
        print(f"  {fighter1}")
        print(f"  {fighter2}")

        return False

    # --------------------------------------------------------
    # We found the fight heading.
    #
    # Use the position of THAT occurrence rather than
    # the first fighter occurrence on the page.
    # --------------------------------------------------------

    fight_start = match.start()

    print()
    print("✅ Found the fight on the live page.")
    print(f"Position in page text: {fight_start}")

    # --------------------------------------------------------
    # Print a large section around the fight for debugging
    # --------------------------------------------------------

    section = body[
        max(0, fight_start - 200):
        fight_start + 5000
    ]

    # --------------------------------------------------------
    # Look for Official Result after the fight heading
    # --------------------------------------------------------

    section_lower = section.lower()

    official_result = "the official result"

    if official_result in section_lower:

        print()
        print("✅ THE OFFICIAL RESULT WAS FOUND!")
        print()

        return True

    # --------------------------------------------------------
    # If there is no official result yet, report that
    # --------------------------------------------------------

    print()
    print("Official result not found yet.")
    print()

    return False


# ============================================================
# FIND LIVE/RESULTS PAGE
# ============================================================

def find_live_page(page, event):

    """
    Search Sherdog for a live play-by-play page associated
    with the event.

    On fight night Sherdog publishes a live results page.
    """

    print()
    print("Looking for the live results page...")

    page.goto(
        event["url"],
        wait_until="domcontentloaded",
        timeout=30000
    )

    page.wait_for_timeout(1500)

    links = page.locator("a")

    event_name = event["name"].lower()

    candidates = []

    for i in range(links.count()):

        try:
            link = links.nth(i)

            text = link.inner_text().strip()
            href = link.get_attribute("href")

            if not href:
                continue

            combined = (
                f"{text} {href}"
            ).lower()

            if (
                "play-by-play" in combined
                or "live now" in combined
                or "results" in combined
            ):

                if "ufc" in combined:

                    if href.startswith("/"):
                        href = (
                            "https://www.sherdog.com"
                            + href
                        )

                    candidates.append(href)

        except Exception:
            continue

    # Prefer the first candidate
    if candidates:

        print(
            "Live results page found:"
        )
        print(candidates[0])

        return candidates[0]

    return None


# ============================================================
# MONITOR
# ============================================================

def monitor(
    page,
    event,
    target_fight,
    previous_fight
):

    print()
    print("=" * 65)
    print("MONITORING UFC")
    print("=" * 65)

    print()
    print("Your fight:")
    print(f"  {target_fight}")

    print()
    print("Waiting for preceding fight to finish:")
    print(f"  {previous_fight}")

    print()
    print(
        f"Checking once every {CHECK_INTERVAL} seconds."
    )

    print()
    print(
        "You can leave this window running in the background."
    )

    notified = False

    while not notified:

        try:

            # Try to find the live page again every check.
            live_url = find_live_page(page, event)

            if live_url:

                page.goto(
                    live_url,
                    wait_until="domcontentloaded",
                    timeout=30000
                )

                page.wait_for_timeout(1500)

                complete = fight_is_complete(
                    page,
                    previous_fight
                )

                now = datetime.now().strftime(
                    "%I:%M:%S %p"
                )

                if complete:

                    print(
                        f"[{now}] "
                        f"Preceding fight is COMPLETE."
                    )

                    send_notification(
                        target_fight,
                        previous_fight
                    )

                    notified = True
                    break

                else:

                    print(
                        f"[{now}] "
                        f"Preceding fight has not finished yet."
                    )

            else:

                now = datetime.now().strftime(
                    "%I:%M:%S %p"
                )

                print(
                    f"[{now}] "
                    "Live results page not available yet."
                )

        except PlaywrightTimeoutError:

            print(
                "\nPage timed out. "
                "Will try again in 60 seconds."
            )

        except Exception as e:

            print(
                f"\nCheck failed: {e}"
            )

            print(
                "Will try again in 60 seconds."
            )

        if not notified:

            print(
                f"Sleeping {CHECK_INTERVAL} seconds..."
            )

            time.sleep(CHECK_INTERVAL)


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 65)
    print("              UFC FIGHT NOTIFIER")
    print("=" * 65)

    print()
    print("No API key required.")
    print("Using Playwright + Sherdog.")

    with sync_playwright() as p:

        browser = p.chromium.launch(
            headless=True
        )

        page = browser.new_page(
            user_agent=USER_AGENT,
            viewport={
                "width": 1400,
                "height": 900
            }
        )

        try:

            # ------------------------------------------------
            # Find next UFC event
            # ------------------------------------------------

            event = find_next_ufc_event(page)

            # ------------------------------------------------
            # Get fight card
            # ------------------------------------------------

            fights = get_fight_card(
                page,
                event
            )

            # ------------------------------------------------
            # Select target fight
            # ------------------------------------------------

            selected_index = select_fight(
                fights
            )

            if selected_index == 0:

                print()
                print(
                    "You selected the first fight."
                )

                print(
                    "There isn't a preceding UFC fight "
                    "to monitor."
                )

                return

            target_fight = fights[selected_index]

            previous_fight = fights[
                selected_index - 1
            ]

            # ------------------------------------------------
            # Confirm
            # ------------------------------------------------

            print()
            print("=" * 65)
            print("NOTIFICATION SET")
            print("=" * 65)

            print()
            print(
                f"YOUR FIGHT:\n"
                f"  {target_fight}"
            )

            print()
            print(
                f"I WILL WATCH:\n"
                f"  {previous_fight}"
            )

            print()
            print(
                "When that fight is finished, "
                "you'll receive a Windows notification."
            )

            print()
            print(
                "Checking every 60 seconds."
            )

            # ------------------------------------------------
            # Monitor
            # ------------------------------------------------

            monitor(
                page,
                event,
                target_fight,
                previous_fight
            )

        finally:

            browser.close()


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    try:
        main()

    except KeyboardInterrupt:

        print()
        print("Program stopped.")

    except Exception as e:

        print()
        print("=" * 65)
        print("ERROR")
        print("=" * 65)
        print(e)
