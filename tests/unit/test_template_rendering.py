import pytest
from worker.src.template_engine import template_engine


class TestTemplateEngine:
    def test_render_order_confirmation(self):
        subject_tpl = "Order Confirmation #{{ order_id }} - Thank You!"
        body_tpl = "Hi {{ customer_name }}, your order for {{ product_name }} (Total: {{ total_amount | currency }}) is confirmed."
        
        dynamic_data = {
            "order_id": "ORD-9988",
            "customer_name": "Lokesh Reddy",
            "product_name": "Pro Developer Subscription",
            "total_amount": 199.99,
        }

        subj, body = template_engine.render(subject_tpl, body_tpl, dynamic_data)
        assert subj == "Order Confirmation #ORD-9988 - Thank You!"
        assert "Hi Lokesh Reddy" in body
        assert "Pro Developer Subscription" in body
        assert "$199.99" in body

    def test_render_password_reset(self):
        subject_tpl = "Password Reset Request"
        body_tpl = "Hello {{ user_name | default('User') }}, reset link: {{ reset_link }}. Expires in {{ expiry_minutes | default(15) }} mins."

        # Case 1: All variables provided
        subj, body = template_engine.render(
            subject_tpl,
            body_tpl,
            {"user_name": "Alice", "reset_link": "https://example.com/reset/token123", "expiry_minutes": 30},
        )
        assert "Hello Alice" in body
        assert "https://example.com/reset/token123" in body
        assert "30 mins" in body

        # Case 2: Defaults used when missing
        subj2, body2 = template_engine.render(subject_tpl, body_tpl, {})
        assert "Hello User" in body2
        assert "15 mins" in body2

    def test_render_silent_undefined(self):
        subject_tpl = "Alert: {{ missing_subject_var }}"
        body_tpl = "Detail: {{ missing_body_var }}"

        subj, body = template_engine.render(subject_tpl, body_tpl, {})
        assert subj == "Alert:"
        assert body == "Detail:"

    def test_render_html_escape(self):
        subject_tpl = "Notification for {{ name }}"
        body_tpl = "Your message: {{ message }}"

        subj, body = template_engine.render(
            subject_tpl,
            body_tpl,
            {"name": "Bob", "message": "<b>Hello</b> & welcome"},
        )
        assert "Bob" in subj
        assert "<b>Hello</b> & welcome" in body
