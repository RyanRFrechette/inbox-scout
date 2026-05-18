"""
Test: tightened Promotion and Newsletter keyword classification.

Verifies that broad single-word keywords ("off", "save", "update") no longer cause
false Promotion/Newsletter matches while correct multi-word phrases still fire.

Run:
  $env:PYTHONPATH = "src"; .venv/Scripts/python.exe -m unittest tests.test_rule_classifier_keywords -v
"""
from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from inbox_scout.rule_classifier import classify_email, load_json
from inbox_scout.paths import RULES_FILE

_RULES = load_json(RULES_FILE)


def _cat(subject: str, snippet: str = "") -> str:
    email = {"from": "", "subject": subject, "snippet": snippet}
    return classify_email(email, _RULES, [], [])["category"]


class TestPromotionKeywords(unittest.TestCase):

    def test_offer_not_promotion(self):
        self.assertNotEqual(_cat("Your offer is ready"), "Promotion")

    def test_percent_off_is_promotion(self):
        self.assertEqual(_cat("50% off today only"), "Promotion")

    def test_save_the_date_not_promotion(self):
        self.assertNotEqual(_cat("Save the date for our wedding"), "Promotion")

    def test_save_up_to_is_promotion(self):
        self.assertEqual(_cat("Save up to 40% this weekend"), "Promotion")

    def test_save_now_is_promotion(self):
        self.assertEqual(_cat("Save now — limited seats available"), "Promotion")

    def test_offline_not_promotion(self):
        self.assertNotEqual(_cat("Your account is offline"), "Promotion")

    def test_offered_not_promotion(self):
        self.assertNotEqual(_cat("You have been offered a free consultation"), "Promotion")


class TestNewsletterKeywords(unittest.TestCase):

    def test_status_update_not_newsletter(self):
        self.assertNotEqual(_cat("Status update from your team"), "Newsletter")

    def test_weekly_update_is_newsletter(self):
        self.assertEqual(_cat("Weekly update from the team"), "Newsletter")

    def test_product_update_is_newsletter(self):
        self.assertEqual(_cat("Product update: new features this month"), "Newsletter")

    def test_plain_weekly_still_newsletter(self):
        self.assertEqual(_cat("Your weekly digest"), "Newsletter")

    def test_software_update_not_newsletter(self):
        self.assertNotEqual(_cat("Software update available for your device"), "Newsletter")


class TestJobCareerApplicationKeyword(unittest.TestCase):

    def test_job_application_received_is_job_career(self):
        self.assertEqual(_cat("Your job application received"), "Job/career")

    def test_application_status_update_is_job_career(self):
        self.assertEqual(_cat("Application status update from Acme"), "Job/career")

    def test_your_application_is_job_career(self):
        self.assertEqual(_cat("Your application has been reviewed"), "Job/career")

    def test_mobile_application_not_job_career(self):
        self.assertNotEqual(_cat("Mobile application update available"), "Job/career")

    def test_web_application_not_job_career(self):
        self.assertNotEqual(_cat("Web application maintenance notice"), "Job/career")


class TestClientBusinessCustomerKeyword(unittest.TestCase):

    def test_dear_customer_not_client_business(self):
        self.assertNotEqual(_cat("Dear customer, check out these deals"), "Client/business")

    def test_customer_survey_not_client_business(self):
        self.assertNotEqual(_cat("Customer satisfaction survey"), "Client/business")

    def test_client_quote_still_client_business(self):
        self.assertEqual(_cat("Client quote attached"), "Client/business")

    def test_contractor_still_client_business(self):
        self.assertEqual(_cat("New contractor agreement attached"), "Client/business")


class TestLegalNoticeKeyword(unittest.TestCase):

    def test_important_legal_notice_still_legal(self):
        self.assertEqual(_cat("Important legal notice"), "Legal")

    def test_notice_of_delivery_not_legal(self):
        self.assertNotEqual(_cat("Notice of delivery"), "Legal")

    def test_account_notice_not_legal(self):
        self.assertNotEqual(_cat("Important notice about your account"), "Legal")

    def test_court_date_still_legal(self):
        self.assertEqual(_cat("Court date reminder"), "Legal")

    def test_attorney_docs_still_legal(self):
        self.assertEqual(_cat("Attorney documents attached"), "Legal")


class TestVetAndWarrantyKeywords(unittest.TestCase):

    def test_veteran_day_not_medical(self):
        self.assertNotEqual(_cat("Veteran Day sale 20% off"), "Medical")

    def test_vet_appointment_still_medical(self):
        self.assertEqual(_cat("Vet appointment reminder for Max"), "Medical")

    def test_claim_reward_not_warranty(self):
        self.assertNotEqual(_cat("Claim your free reward now!"), "Warranty/support")

    def test_warranty_claim_still_warranty(self):
        self.assertEqual(_cat("Warranty claim submitted for MacBook"), "Warranty/support")


class TestUnchangedCategories(unittest.TestCase):

    def test_mobile_application_update_not_newsletter(self):
        self.assertNotEqual(_cat("Mobile application update available"), "Newsletter")


if __name__ == "__main__":
    unittest.main()
