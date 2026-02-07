# Payment Notification Implementation Guide

## Overview

This guide provides step-by-step instructions for implementing a complete payment notification system with Stripe webhook integration. The system sends real-time admin alerts for payment events (confirmations, failures, renewals, cancellations, refunds, payment method updates).

## Architecture

```
Stripe Event → Webhook (/api/stripe/webhook)
    ↓
Event Handler (stripeWebhook.ts)
    ↓
Payment Notification Helper (paymentNotifications.ts)
    ↓
Admin Notification System (notifications.ts)
    ↓
Admin Notification Center (UI)
```

## Implementation Steps

### 1. Database Schema

Add notification tables to `drizzle/schema.ts`:

```typescript
export const notifications = mysqlTable("notifications", {
  id: int("id").primaryKey().autoincrement(),
  adminId: int("admin_id").notNull(),
  type: varchar("type", { length: 50 }).notNull(),
  title: text("title").notNull(),
  body: text("body").notNull(),
  linkUrl: text("link_url"),
  metadata: json("metadata"),
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
  emailDigestFrequency: varchar("email_digest_frequency", { length: 20 }).default("immediate"),
  quietHoursEnabled: boolean("quiet_hours_enabled").default(false),
  quietHoursStart: varchar("quiet_hours_start", { length: 5 }),
  quietHoursEnd: varchar("quiet_hours_end", { length: 5 }),
  createdAt: timestamp("created_at").defaultNow(),
  updatedAt: timestamp("updated_at").defaultNow().onUpdateNow(),
});
```

Run migration:
```bash
pnpm db:push
```

### 2. Notification Helper Functions

Create `server/paymentNotifications.ts` with functions for each notification type:

- `sendPaymentConfirmationNotification(data)` - Payment confirmed
- `sendPaymentFailureNotification(data)` - Payment failed
- `sendSubscriptionRenewalNotification(data)` - Subscription renewing soon
- `sendSubscriptionCancellationNotification(data)` - Subscription cancelled
- `sendRefundNotification(data)` - Refund issued
- `sendPaymentMethodUpdateNotification(data)` - Payment method updated

Each function:
1. Formats notification title and body
2. Extracts metadata from payment data
3. Generates admin link URL
4. Calls `createAdminNotification()` with formatted data

### 3. Stripe Webhook Handler

Create `server/_core/stripeWebhook.ts` with:

```typescript
export async function handleStripeWebhook(req: any, res: any) {
  const sig = req.headers["stripe-signature"];
  const event = stripe.webhooks.constructEvent(req.body, sig, process.env.STRIPE_WEBHOOK_SECRET);

  // Handle test events
  if (event.id.startsWith("evt_test_")) {
    return res.json({ verified: true });
  }

  // Route to event handlers
  switch (event.type) {
    case "checkout.session.completed":
      await handleCheckoutSessionCompleted(event.data.object);
      break;
    case "payment_intent.succeeded":
      await handlePaymentIntentSucceeded(event.data.object);
      break;
    case "payment_intent.payment_failed":
      await handlePaymentIntentFailed(event.data.object);
      break;
    // ... more event types
  }

  res.json({ received: true });
}
```

### 4. Register Webhook Endpoint

In `server/_core/index.ts`, register the webhook BEFORE `express.json()`:

```typescript
app.post("/api/stripe/webhook", express.raw({ type: "application/json" }), handleStripeWebhook);
app.use(express.json());
```

**Critical:** Webhook must be registered before JSON middleware to verify Stripe signature.

### 5. Integrate with Payment Router

In `server/routers/payment.ts`, call notification functions:

```typescript
// In getCheckoutSession procedure
await sendPaymentConfirmationNotification({
  amount: session.amount_total,
  currency: session.currency,
  tier: metadata.tier,
  billingInterval: metadata.billingInterval,
  customerEmail: session.customer_email,
  customerName: metadata.customerName,
  sessionId: session.id,
});

// In updateBillingInfo procedure
await sendPaymentMethodUpdateNotification({
  customerEmail: user.email,
  customerName: user.name,
  paymentMethodType: "card",
  last4: "4242",
});
```

### 6. Create Notification UI Components

Build UI components to display notifications:

- `NotificationBell.tsx` - Bell icon with dropdown showing recent notifications
- `NotificationCenter.tsx` - Full page with notification history and filtering
- `NotificationToast.tsx` - Toast component for real-time alerts

### 7. Write Tests

Create `server/paymentNotifications.test.ts` with tests for:

- Notification type validation
- Metadata structure verification
- Title and body formatting
- Link URL generation
- Error handling

Run tests:
```bash
pnpm test server/paymentNotifications.test.ts
```

## Payment Event Types

### 1. Payment Confirmation
**Event:** `checkout.session.completed` or `payment_intent.succeeded`
**Data:** Amount, tier, billing interval, customer info
**Link:** `/admin/payments?session=cs_xxx`

### 2. Payment Failure
**Event:** `payment_intent.payment_failed`
**Data:** Amount, tier, failure reason
**Link:** `/admin/payments?session=cs_xxx&status=failed`

### 3. Subscription Renewal
**Event:** `customer.subscription.updated` (7 days before renewal)
**Data:** Amount, renewal date, subscription ID
**Link:** `/admin/payments?subscription=sub_xxx`

### 4. Subscription Cancellation
**Event:** `customer.subscription.deleted`
**Data:** Tier, cancellation reason, subscription ID
**Link:** `/admin/payments?subscription=sub_xxx&status=cancelled`

### 5. Refund Issued
**Event:** `charge.refunded`
**Data:** Amount, refund reason, charge/refund IDs
**Link:** `/admin/payments?refund=re_xxx`

### 6. Payment Method Updated
**Event:** Manual (in payment router)
**Data:** Customer info, payment method type, last 4 digits
**Link:** `/admin/payments?customer=email@example.com`

## Testing with Stripe CLI

1. **Install Stripe CLI:**
   ```bash
   brew install stripe/stripe-cli/stripe
   ```

2. **Listen for webhooks:**
   ```bash
   stripe listen --forward-to localhost:3000/api/stripe/webhook
   ```

3. **Trigger test events:**
   ```bash
   stripe trigger payment_intent.succeeded
   stripe trigger payment_intent.payment_failed
   stripe trigger customer.subscription.created
   ```

4. **Verify in logs:**
   - Check server logs for "Payment confirmation notification sent"
   - Check database for new notification records

## Admin Notification Preferences

Admins can customize notifications via `adminNotificationPreferences` table:

| Setting | Type | Default | Purpose |
|---------|------|---------|---------|
| `inAppPayments` | boolean | true | Receive in-app payment notifications |
| `emailPayments` | boolean | false | Receive email payment notifications |
| `emailDigestFrequency` | string | "immediate" | Email frequency (immediate/daily/weekly) |
| `quietHoursEnabled` | boolean | false | Disable notifications during quiet hours |
| `quietHoursStart` | string | null | Quiet hours start time (HH:MM) |
| `quietHoursEnd` | string | null | Quiet hours end time (HH:MM) |

## Error Handling

All notification functions include try-catch blocks:

```typescript
try {
  await sendPaymentConfirmationNotification(data);
} catch (error) {
  console.error("Failed to send notification:", error);
  // Payment succeeds even if notification fails
}
```

**Key principle:** Notifications are non-blocking. Payment processing continues even if notifications fail.

## Troubleshooting

### Notifications not appearing
1. Check admin user exists: `SELECT * FROM users WHERE role = 'admin'`
2. Check preferences: `SELECT * FROM adminNotificationPreferences WHERE adminId = 1`
3. Check notifications table: `SELECT * FROM notifications ORDER BY createdAt DESC`
4. Check server logs for error messages

### Webhook not triggering
1. Verify webhook secret: Check `STRIPE_WEBHOOK_SECRET` environment variable
2. Verify endpoint: Check `/api/stripe/webhook` is registered
3. Test with Stripe CLI: `stripe listen --forward-to localhost:3000/api/stripe/webhook`
4. Check Stripe dashboard → Developers → Webhooks for delivery status

### Signature verification failing
1. Ensure webhook is registered BEFORE `express.json()`
2. Verify webhook secret matches Stripe dashboard
3. Check request body is raw (not parsed)

## Next Steps

1. **Email Notifications** - Extend to send emails alongside in-app notifications
2. **Admin Settings UI** - Create page for customizing notification preferences
3. **Webhook Monitoring** - Add dashboard showing webhook delivery status
4. **Notification Analytics** - Track notification delivery and engagement
