from __future__ import annotations

from inbox_scout.gmail_auth import get_gmail_service


def get_inbox_counts() -> dict:
    service = get_gmail_service()

    label = service.users().labels().get(
        userId="me",
        id="INBOX"
    ).execute()

    return {
        "total": label.get("messagesTotal", 0),
        "unread": label.get("messagesUnread", 0),
        "threads_total": label.get("threadsTotal", 0),
        "threads_unread": label.get("threadsUnread", 0),
    }


def build_inbox_count_message() -> str:
    counts = get_inbox_counts()
    total = counts["total"]
    unread = counts["unread"]
    t_unread = counts["threads_unread"]

    if unread == 0:
        summary = f"Your inbox is clean — {total} total email{'s' if total != 1 else ''}, none unread."
    elif unread >= total * 0.8:
        summary = f"Your inbox is pretty full — {unread} unread out of {total} total ({t_unread} unread threads)."
    else:
        summary = f"Your inbox has {unread} unread out of {total} total ({t_unread} unread threads)."

    return summary + "\n\nRead-only. Gmail not touched."


def main() -> None:
    print(build_inbox_count_message())


if __name__ == "__main__":
    main()
