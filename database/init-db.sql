-- Database Initialization Script for NotifyFlow Transactional Email Notification Service

-- Create Notification Templates Table
CREATE TABLE IF NOT EXISTS notification_templates (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    subject_template TEXT NOT NULL,
    body_template TEXT NOT NULL,
    language VARCHAR(10) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create User Preferences Table
CREATE TABLE IF NOT EXISTS user_preferences (
    user_id VARCHAR(100) PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    email_opt_out BOOLEAN DEFAULT FALSE NOT NULL,
    preferred_language VARCHAR(10) DEFAULT 'en' NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create Index for email lookups in user_preferences
CREATE INDEX IF NOT EXISTS idx_user_preferences_email ON user_preferences(email);

-- Seed Notification Templates (At least 3 required - providing 5 standard templates)
INSERT INTO notification_templates (id, name, subject_template, body_template, language)
VALUES
    (
        'order-confirmation',
        'Order Confirmation',
        'Order Confirmation #{{ order_id }} - Thank You for Your Purchase!',
        'Hello {{ customer_name | default("Customer") }},\n\nThank you for your order! Your purchase of {{ product_name }} (Order ID: {{ order_id }}) for a total of {{ total_amount | default("$0.00") }} has been confirmed and is being processed.\n\nShipping Address: {{ shipping_address | default("Standard Delivery") }}\nEstimated Delivery: {{ delivery_date | default("3-5 business days") }}\n\nThank you for shopping with us!\nThe NotifyFlow Team',
        'en'
    ),
    (
        'password-reset',
        'Password Reset Request',
        'Security Notice: Password Reset Request for Your Account',
        'Hello {{ user_name | default("User") }},\n\nWe received a request to reset the password for your account.\n\nPlease click the link below to set a new password:\n{{ reset_link }}\n\nThis link will expire in {{ expiry_minutes | default(15) }} minutes.\nIf you did not request this change, please ignore this email or contact support immediately.\n\nBest regards,\nThe Security Team',
        'en'
    ),
    (
        'account-alert',
        'Account Security Alert',
        'Security Alert: {{ alert_type | default("New sign-in detected") }}',
        'Hello {{ user_name | default("User") }},\n\nWe detected a security event on your account:\n\nEvent: {{ alert_type | default("New device login") }}\nDevice: {{ device | default("Unknown Device") }}\nLocation: {{ location | default("Unknown Location") }}\nTimestamp: {{ login_time | default("Recently") }}\nIP Address: {{ ip_address | default("N/A") }}\n\nIf this was you, no action is needed. If you do not recognize this activity, please secure your account immediately.\n\nRegards,\nThe Security Team',
        'en'
    ),
    (
        'welcome-email',
        'Welcome to NotifyFlow',
        'Welcome to NotifyFlow, {{ user_name }}!',
        'Hi {{ user_name }},\n\nWelcome to NotifyFlow! We are thrilled to have you on board.\n\nGet started by exploring your dashboard: {{ dashboard_url | default("https://notifyflow.example.com/dashboard") }}\n\nIf you have any questions, reply directly to this email.\n\nCheers,\nThe NotifyFlow Team',
        'en'
    ),
    (
        'payment-receipt',
        'Payment Receipt',
        'Receipt for Invoice #{{ invoice_number }}',
        'Dear {{ customer_name }},\n\nThis is a confirmation of your payment of {{ amount }} on {{ payment_date }}.\n\nInvoice ID: {{ invoice_number }}\nPayment Method: {{ payment_method | default("Credit Card") }}\nStatus: {{ status | default("Paid") }}\n\nYou can view and download your full invoice here: {{ invoice_url | default("https://notifyflow.example.com/invoices") }}\n\nThank you for your business!',
        'en'
    )
ON CONFLICT (id) DO NOTHING;

-- Seed User Preferences (At least 5 required)
INSERT INTO user_preferences (user_id, email, email_opt_out, preferred_language)
VALUES
    ('usr-001', 'john.doe@example.com', FALSE, 'en'),
    ('usr-002', 'jane.smith@example.com', FALSE, 'en'),
    ('usr-003', 'optedout.user@example.com', TRUE, 'en'),
    ('usr-004', 'alex.tech@example.com', FALSE, 'es'),
    ('usr-005', 'sarah.connor@example.com', FALSE, 'en'),
    ('usr-006', 'bob.unsubscribed@example.com', TRUE, 'en'),
    ('usr-007', 'dev.lead@example.com', FALSE, 'en')
ON CONFLICT (user_id) DO NOTHING;
