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

    return (
        "Here is your Gmail Inbox count:\n\n"
        f"- Total inbox emails: {counts['total']}\n"
        f"- Unread inbox emails: {counts['unread']}\n"
        f"- Total inbox threads: {counts['threads_total']}\n"
        f"- Unread inbox threads: {counts['threads_unread']}\n\n"
        "I only checked the count. I did not touch Gmail."
    )


def main() -> None:
    print(build_inbox_count_message())


if __name__ == "__main__":
    main()
