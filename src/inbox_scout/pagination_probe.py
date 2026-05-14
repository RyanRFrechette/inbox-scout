from __future__ import annotations

import argparse
from typing import Optional

from inbox_scout.gmail_auth import get_gmail_service


def build_query(unread_only: bool = False, days: Optional[int] = None) -> str:
    parts = []

    if unread_only:
        parts.append("is:unread")

    if days:
        parts.append(f"newer_than:{days}d")

    return " ".join(parts)


def fetch_message_ids(page_size: int, max_messages: int, unread_only: bool, days: Optional[int]):
    service = get_gmail_service()
    query = build_query(unread_only=unread_only, days=days)

    all_ids = []
    page_token = None
    page_count = 0

    while len(all_ids) < max_messages:
        remaining = max_messages - len(all_ids)
        this_page_size = min(page_size, remaining)

        request = {
            "userId": "me",
            "labelIds": ["INBOX"],
            "maxResults": this_page_size,
        }

        if query:
            request["q"] = query

        if page_token:
            request["pageToken"] = page_token

        results = service.users().messages().list(**request).execute()

        page_count += 1
        messages = results.get("messages", [])
        ids = [m["id"] for m in messages]

        all_ids.extend(ids)

        print(f"Page {page_count}: fetched {len(ids)} message IDs")

        page_token = results.get("nextPageToken")

        if not page_token:
            break

        if not ids:
            break

    return all_ids, page_count, bool(page_token)


def main():
    parser = argparse.ArgumentParser(description="Inbox Scout Phase 11A pagination probe")
    parser.add_argument("--page-size", type=int, default=25)
    parser.add_argument("--max-messages", type=int, default=50)
    parser.add_argument("--unread-only", action="store_true")
    parser.add_argument("--days", type=int)

    args = parser.parse_args()

    print("Inbox Scout Phase 11A: Pagination Probe")
    print("Mode: READ ONLY")
    print(f"Page size: {args.page_size}")
    print(f"Max messages: {args.max_messages}")
    print(f"Unread only: {args.unread_only}")
    print(f"Days: {args.days if args.days else 'All'}")
    print()

    ids, pages, has_more = fetch_message_ids(
        page_size=args.page_size,
        max_messages=args.max_messages,
        unread_only=args.unread_only,
        days=args.days,
    )

    print()
    print(f"Total fetched IDs: {len(ids)}")
    print(f"Pages fetched: {pages}")
    print(f"More available after stop: {has_more}")
    print("Gmail changes: 0")
    print("No emails were archived, trashed, labeled, deleted, replied to, or marked read.")


if __name__ == "__main__":
    main()
