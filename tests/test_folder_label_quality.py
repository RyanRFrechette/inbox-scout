"""
Folder label quality tests: category → InboxScout label routing.

Proves:
- Amazon/USPS/Anthropic emails mis-classified as Finance get better folders
- True Finance signals (statement/bank/investment/irs) are never demoted
- Anthropic receipt/plan → AI-Dev-Tools
- USPS Click-N-Ship payment → Receipts; USPS tracking → Shipping-Returns
- PayPal statement → Finance; Merrill/investment → Finance
- New CATEGORY_TO_LABEL entries route AI-returned strings correctly

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_folder_label_quality -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _label(category: str = "Finance", from_: str = "", subject: str = "", snippet: str = "") -> str:
    from inbox_scout.autopilot_cleanup import _pick_inboxscout_label
    return _pick_inboxscout_label({
        "category": category,
        "from": from_,
        "subject": subject,
        "snippet": snippet,
    })


class TestFinanceNotMisassigned(unittest.TestCase):
    """Emails from retail/AI senders with Finance category get better folders."""

    def test_amazon_shipped_gets_shipping_returns(self):
        self.assertEqual(
            _label(from_="ship-confirm@amazon.com", subject="Shipped: Your order"),
            "InboxScout/Shipping-Returns",
        )

    def test_amazon_tracking_gets_shipping_returns(self):
        self.assertEqual(
            _label(from_="tracking@amazon.com", subject="Your package is now tracking"),
            "InboxScout/Shipping-Returns",
        )

    def test_amazon_order_placed_gets_receipts(self):
        self.assertEqual(
            _label(from_="order-update@amazon.com", subject="Your Amazon order has been placed"),
            "InboxScout/Receipts",
        )

    def test_amazon_delivered_not_finance(self):
        result = _label(from_="delivery-tracking@amazon.com", subject="Delivered: Your package arrived")
        self.assertNotEqual(result, "InboxScout/Finance")

    def test_anthropic_receipt_gets_ai_dev_tools(self):
        self.assertEqual(
            _label(from_="billing@anthropic.com", subject="Your receipt from Anthropic, PBC"),
            "InboxScout/AI-Dev-Tools",
        )

    def test_anthropic_pro_plan_gets_ai_dev_tools(self):
        self.assertEqual(
            _label(from_="no-reply@anthropic.com", subject="Welcome to Claude Pro"),
            "InboxScout/AI-Dev-Tools",
        )

    def test_anthropic_invoice_gets_ai_dev_tools(self):
        self.assertEqual(
            _label(from_="noreply@anthropic.com", subject="Invoice for your Anthropic subscription"),
            "InboxScout/AI-Dev-Tools",
        )

    def test_usps_click_n_ship_gets_receipts(self):
        self.assertEqual(
            _label(from_="do-not-reply@usps.com", subject="USPS Click-N-Ship payment confirmation"),
            "InboxScout/Receipts",
        )

    def test_usps_tracking_gets_shipping_returns(self):
        self.assertEqual(
            _label(from_="auto-reply@usps.com", subject="Your package has shipped"),
            "InboxScout/Shipping-Returns",
        )


class TestFinanceStillProtected(unittest.TestCase):
    """True Finance signals must NOT be demoted to another folder."""

    def test_bank_statement_stays_finance(self):
        self.assertEqual(
            _label(from_="noreply@bankofamerica.com", subject="Your bank statement is ready"),
            "InboxScout/Finance",
        )

    def test_credit_card_stays_finance(self):
        self.assertEqual(
            _label(from_="alerts@chase.com", subject="Your credit card statement"),
            "InboxScout/Finance",
        )

    def test_investment_statement_stays_finance(self):
        self.assertEqual(
            _label(from_="service@merrill.com", subject="Your investment statement is ready"),
            "InboxScout/Finance",
        )

    def test_paypal_monthly_statement_stays_finance(self):
        self.assertEqual(
            _label(from_="service@paypal.com", subject="Your monthly account statement"),
            "InboxScout/Finance",
        )

    def test_tax_form_stays_finance(self):
        self.assertEqual(
            _label(from_="noreply@irs.gov", subject="Your tax form 1099 is ready"),
            "InboxScout/Finance",
        )

    def test_irs_subject_stays_finance(self):
        self.assertEqual(
            _label(from_="noreply@irs.gov", subject="IRS notice regarding your account"),
            "InboxScout/Finance",
        )

    def test_brokerage_statement_stays_finance(self):
        self.assertEqual(
            _label(from_="noreply@fidelity.com", subject="Your brokerage statement"),
            "InboxScout/Finance",
        )

    def test_amazon_with_credit_card_subject_stays_finance(self):
        # Amazon Store Card statement — should stay Finance because "credit card" in subject
        self.assertEqual(
            _label(from_="amazon-statements@amazon.com", subject="Your Amazon credit card statement"),
            "InboxScout/Finance",
        )


class TestCategoryToLabelNewEntries(unittest.TestCase):
    """New CATEGORY_TO_LABEL entries route AI-returned category strings correctly."""

    def _map(self, cat: str) -> str:
        return _label(category=cat, from_="other@other.com", subject="subject")

    def test_amazon_order_category(self):
        self.assertEqual(self._map("amazon order"), "InboxScout/Shopping-History")

    def test_amazon_shipped_category(self):
        self.assertEqual(self._map("amazon shipped"), "InboxScout/Shipping-Returns")

    def test_amazon_delivered_category(self):
        self.assertEqual(self._map("amazon delivered"), "InboxScout/Shopping-History")

    def test_order_notification_category(self):
        self.assertEqual(self._map("order notification"), "InboxScout/Shopping-History")

    def test_order_placed_category(self):
        self.assertEqual(self._map("order placed"), "InboxScout/Receipts")

    def test_order_shipped_category(self):
        self.assertEqual(self._map("order shipped"), "InboxScout/Shipping-Returns")

    def test_shipping_update_category(self):
        self.assertEqual(self._map("shipping update"), "InboxScout/Shipping-Returns")

    def test_package_tracking_category(self):
        self.assertEqual(self._map("package tracking"), "InboxScout/Shipping-Returns")

    def test_tracking_update_category(self):
        self.assertEqual(self._map("tracking update"), "InboxScout/Shipping-Returns")

    def test_delivery_notification_category(self):
        self.assertEqual(self._map("delivery notification"), "InboxScout/Shopping-History")

    def test_usps_category(self):
        self.assertEqual(self._map("usps"), "InboxScout/Shipping-Returns")

    def test_click_n_ship_category(self):
        self.assertEqual(self._map("click-n-ship"), "InboxScout/Receipts")

    def test_merrill_category(self):
        self.assertEqual(self._map("merrill"), "InboxScout/Finance")

    def test_paypal_statement_category(self):
        self.assertEqual(self._map("paypal statement"), "InboxScout/Finance")

    def test_investment_statement_category(self):
        self.assertEqual(self._map("investment statement"), "InboxScout/Finance")

    def test_anthropic_receipt_category(self):
        self.assertEqual(self._map("anthropic receipt"), "InboxScout/AI-Dev-Tools")


if __name__ == "__main__":
    unittest.main()
