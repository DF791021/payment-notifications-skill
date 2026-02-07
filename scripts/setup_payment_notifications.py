#!/usr/bin/env python3
"""
Payment Notification System Setup Script

Generates boilerplate code for implementing payment notifications with Stripe.
Usage: python setup_payment_notifications.py <project-path>
"""

import sys
import os
from pathlib import Path

def generate_notification_types():
    """Generate notification type constants."""
    return '''// Notification types for payment events
export const PAYMENT_NOTIFICATION_TYPES = {
  PAYMENT_SUCCESS: "payment_success",
  PAYMENT_FAILED: "payment_failed",
  SUBSCRIPTION_RENEWAL: "subscription_renewal",
  SUBSCRIPTION_CANCELLED: "subscription_cancelled",
  REFUND_ISSUED: "refund_issued",
  ACCOUNT_CHANGE: "account_change",
} as const;

export const PAYMENT_NOTIFICATION_ICONS = {
  payment_success: "CheckCircle",
  payment_failed: "AlertCircle",
  subscription_renewal: "Clock",
  subscription_cancelled: "XCircle",
  refund_issued: "RefreshCw",
  account_change: "Settings",
} as const;

export const PAYMENT_NOTIFICATION_COLORS = {
  payment_success: "bg-green-50 border-green-200",
  payment_failed: "bg-red-50 border-red-200",
  subscription_renewal: "bg-blue-50 border-blue-200",
  subscription_cancelled: "bg-yellow-50 border-yellow-200",
  refund_issued: "bg-purple-50 border-purple-200",
  account_change: "bg-gray-50 border-gray-200",
} as const;
'''

def generate_database_schema():
    """Generate Drizzle database schema for notifications."""
    return '''// Add to drizzle/schema.ts

import { mysqlTable, int, text, timestamp, boolean, varchar, json } from "drizzle-orm/mysql-core";
import { relations } from "drizzle-orm";

export const notifications = mysqlTable("notifications", {
  id: int("id").primaryKey().autoincrement(),
  adminId: int("admin_id").notNull(),
  type: varchar("type", { length: 50 }).notNull(), // payment_success, payment_failed, etc.
  title: text("title").notNull(),
  body: text("body").notNull(),
  linkUrl: text("link_url"),
  metadata: json("metadata"), // Payment-specific data
  read: boolean("read").default(false),
  dismissed: boolean("dismissed").default(false),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow(),
});

export const adminNotificationPreferences = mysqlTable("admin_notification_preferences", {
  id: int("id").primaryKey().autoincrement(),
  adminId: int("admin_id").notNull().unique(),
  inAppPayments: boolean("in_app_payments").default(true),
  inAppSystemAlerts: boolean("in_app_system_alerts").default(true),
  inAppAccountChanges: boolean("in_app_account_changes").default(true),
  emailPayments: boolean("email_payments").default(false),
  emailSystemAlerts: boolean("email_system_alerts").default(false),
  emailAccountChanges: boolean("email_account_changes").default(false),
  emailDigestFrequency: varchar("email_digest_frequency", { length: 20 }).default("immediate"), // immediate, daily, weekly
  quietHoursEnabled: boolean("quiet_hours_enabled").default(false),
  quietHoursStart: varchar("quiet_hours_start", { length: 5 }), // HH:MM
  quietHoursEnd: varchar("quiet_hours_end", { length: 5 }), // HH:MM
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow(),
});

export const notificationsRelations = relations(notifications, ({ one }) => ({
  admin: one(users, {
    fields: [notifications.adminId],
    references: [users.id],
  }),
}));
'''

def generate_webhook_handler():
    """Generate Stripe webhook handler template."""
    return '''// Add to server/_core/stripeWebhook.ts

import Stripe from "stripe";
import { sendPaymentConfirmationNotification, sendPaymentFailureNotification } from "../paymentNotifications";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY || "");

export async function handleStripeWebhook(req: any, res: any) {
  const sig = req.headers["stripe-signature"];
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;

  if (!sig || !webhookSecret) {
    return res.status(400).json({ error: "Missing signature or webhook secret" });
  }

  let event: Stripe.Event;

  try {
    event = stripe.webhooks.constructEvent(req.body, sig, webhookSecret);
  } catch (error: any) {
    console.error("Webhook signature verification failed:", error.message);
    return res.status(400).json({ error: "Invalid signature" });
  }

  // Handle test events
  if (event.id.startsWith("evt_test_")) {
    console.log("[Webhook] Test event detected, returning verification response");
    return res.json({ verified: true });
  }

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutSessionCompleted(event.data.object as Stripe.Checkout.Session);
        break;

      case "payment_intent.succeeded":
        await handlePaymentIntentSucceeded(event.data.object as Stripe.PaymentIntent);
        break;

      case "payment_intent.payment_failed":
        await handlePaymentIntentFailed(event.data.object as Stripe.PaymentIntent);
        break;

      case "customer.subscription.created":
        console.log("Subscription created:", event.data.object);
        break;

      case "customer.subscription.updated":
        console.log("Subscription updated:", event.data.object);
        break;

      case "customer.subscription.deleted":
        console.log("Subscription deleted:", event.data.object);
        break;

      case "charge.refunded":
        console.log("Charge refunded:", event.data.object);
        break;

      default:
        console.log("Unhandled event type:", event.type);
    }

    res.json({ received: true });
  } catch (error) {
    console.error("Error processing webhook:", error);
    res.status(500).json({ error: "Webhook processing failed" });
  }
}

async function handleCheckoutSessionCompleted(session: Stripe.Checkout.Session) {
  const metadata = session.metadata || {};
  
  await sendPaymentConfirmationNotification({
    amount: session.amount_total || 0,
    currency: session.currency || "usd",
    tier: metadata.tier || "school",
    billingInterval: metadata.billingInterval || "annual",
    customerEmail: session.customer_email || "",
    customerName: metadata.customerName || "",
    sessionId: session.id,
  });
}

async function handlePaymentIntentSucceeded(intent: Stripe.PaymentIntent) {
  const metadata = intent.metadata || {};
  
  await sendPaymentConfirmationNotification({
    amount: intent.amount,
    currency: intent.currency,
    tier: metadata.tier || "school",
    billingInterval: metadata.billingInterval || "annual",
    customerEmail: metadata.customerEmail || "",
    customerName: metadata.customerName || "",
    sessionId: intent.id,
  });
}

async function handlePaymentIntentFailed(intent: Stripe.PaymentIntent) {
  const metadata = intent.metadata || {};
  
  await sendPaymentFailureNotification({
    amount: intent.amount,
    currency: intent.currency,
    tier: metadata.tier || "school",
    billingInterval: metadata.billingInterval || "annual",
    customerEmail: metadata.customerEmail || "",
    customerName: metadata.customerName || "",
    failureReason: intent.last_payment_error?.message || "Unknown error",
    sessionId: intent.id,
  });
}
'''

def generate_notification_helpers():
    """Generate payment notification helper functions."""
    return '''// Add to server/paymentNotifications.ts

import { getDb } from "./db";
import { createAdminNotification, getAdminNotificationPreferences } from "./notifications";

interface PaymentData {
  amount: number;
  currency: string;
  tier: "school" | "district";
  billingInterval: "month" | "year";
  customerEmail: string;
  customerName: string;
  sessionId?: string;
  failureReason?: string;
  renewalDate?: Date;
  subscriptionId?: string;
  cancellationReason?: string;
  refundReason?: string;
  chargeId?: string;
  refundId?: string;
  paymentMethodType?: string;
  last4?: string;
}

export async function sendPaymentConfirmationNotification(data: PaymentData) {
  try {
    const tierLabel = data.tier === "school" ? "School License" : "District License";
    const intervalLabel = data.billingInterval === "month" ? "Monthly" : "Annual";
    const amount = (data.amount / 100).toFixed(2);

    const title = "Payment Confirmed ✓";
    const body = `${intervalLabel} ${tierLabel} subscription activated. Amount: $${amount} ${data.currency.toUpperCase()}. Customer: ${data.customerEmail}`;

    const metadata = {
      paymentType: "subscription",
      tier: data.tier,
      amount: data.amount,
      currency: data.currency,
      billingInterval: data.billingInterval,
      customerEmail: data.customerEmail,
      customerName: data.customerName,
      sessionId: data.sessionId,
      timestamp: new Date().toISOString(),
    };

    const linkUrl = `/admin/payments?session=${data.sessionId}`;

    await createAdminNotification({
      type: "payment_success",
      title,
      body,
      linkUrl,
      metadata,
    });

    console.log("Payment confirmation notification sent");
  } catch (error) {
    console.error("Failed to send payment confirmation notification:", error);
  }
}

export async function sendPaymentFailureNotification(data: PaymentData) {
  try {
    const tierLabel = data.tier === "school" ? "School License" : "District License";
    const intervalLabel = data.billingInterval === "month" ? "Monthly" : "Annual";
    const amount = (data.amount / 100).toFixed(2);

    const title = "Payment Failed ✗";
    const body = `${intervalLabel} ${tierLabel} subscription failed. Amount: $${amount} ${data.currency.toUpperCase()}. Reason: ${data.failureReason}. Customer: ${data.customerEmail}`;

    const metadata = {
      paymentType: "subscription",
      tier: data.tier,
      amount: data.amount,
      currency: data.currency,
      billingInterval: data.billingInterval,
      customerEmail: data.customerEmail,
      customerName: data.customerName,
      failureReason: data.failureReason,
      sessionId: data.sessionId,
      timestamp: new Date().toISOString(),
    };

    const linkUrl = `/admin/payments?session=${data.sessionId}&status=failed`;

    await createAdminNotification({
      type: "payment_failed",
      title,
      body,
      linkUrl,
      metadata,
    });

    console.log("Payment failure notification sent");
  } catch (error) {
    console.error("Failed to send payment failure notification:", error);
  }
}
'''

def main():
    if len(sys.argv) < 2:
        print("Usage: python setup_payment_notifications.py <project-path>")
        sys.exit(1)

    project_path = Path(sys.argv[1])
    
    print("📦 Payment Notification System Setup")
    print("=" * 50)
    print()
    print("Generated code snippets:")
    print()
    print("1. Notification Types (shared/notifications.ts)")
    print("-" * 50)
    print(generate_notification_types())
    print()
    print("2. Database Schema (drizzle/schema.ts)")
    print("-" * 50)
    print(generate_database_schema())
    print()
    print("3. Webhook Handler (server/_core/stripeWebhook.ts)")
    print("-" * 50)
    print(generate_webhook_handler())
    print()
    print("4. Notification Helpers (server/paymentNotifications.ts)")
    print("-" * 50)
    print(generate_notification_helpers())
    print()
    print("=" * 50)
    print("✅ Code generation complete!")
    print()
    print("Next steps:")
    print("1. Copy the generated code snippets into your project")
    print("2. Run 'pnpm db:push' to apply database migrations")
    print("3. Register the webhook endpoint in your server")
    print("4. Test with Stripe CLI: stripe listen --forward-to localhost:3000/api/stripe/webhook")

if __name__ == "__main__":
    main()
