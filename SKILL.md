---
name: payment-notifications
description: Implement real-time admin payment notifications with Stripe webhooks. Use when building payment systems that need to alert administrators about payment events (confirmations, failures, renewals, cancellations, refunds). Supports admin preferences, in-app notifications, and webhook integration.
---

# Payment Notifications System

Implement a production-grade payment notification system that sends real-time alerts to administrators for payment events. This skill guides you through integrating Stripe webhooks with a notification database, creating admin-facing UI components, and handling payment events with proper error handling and preferences.

## When to Use This Skill

Use this skill when you need to:

- **Send payment alerts to admins** - Notify administrators about successful payments, failures, refunds, and subscription changes
- **Integrate Stripe webhooks** - Handle payment events from Stripe with proper signature verification
- **Build admin notification center** - Create UI for admins to view and manage payment notifications
- **Customize notification preferences** - Allow admins to control which notifications they receive and how often
- **Track payment events** - Maintain audit trail of payment notifications for compliance

## Architecture Overview

```
Stripe Event
    ↓
Webhook Endpoint (/api/stripe/webhook)
    ↓
Event Handler (stripeWebhook.ts)
    ↓
Payment Notification Helper (paymentNotifications.ts)
    ↓
Admin Notification System (notifications.ts)
    ↓
Database (notifications table)
    ↓
Admin UI (NotificationCenter, NotificationBell)
```

## Supported Payment Events

| Event | Trigger | Admin Alert | Example |
|-------|---------|------------|----------|
| **Payment Confirmation** | Checkout completed or payment succeeded | ✓ | "Annual School License activated. $999.00" |
| **Payment Failure** | Payment declined or failed | ✓ | "Payment failed. Card declined. $999.00" |
| **Subscription Renewal** | 7 days before renewal | ✓ | "School License renews on 2/13/2026" |
| **Subscription Cancellation** | Subscription cancelled | ✓ | "School License cancelled" |
| **Refund Issued** | Refund processed | ✓ | "Refund of $999.00 issued" |
| **Payment Method Updated** | Payment method changed | ✓ | "Payment method updated" |

## Implementation Workflow

### Phase 1: Database Setup

1. **Add notification tables** to `drizzle/schema.ts`:
   - `notifications` - Stores notification records
   - `adminNotificationPreferences` - Stores admin preferences

2. **Run migration:**
   ```bash
   pnpm db:push
   ```

See `references/implementation-guide.md` for schema details.

### Phase 2: Backend Implementation

1. **Create notification helpers** (`server/paymentNotifications.ts`):
   - `sendPaymentConfirmationNotification(data)`
   - `sendPaymentFailureNotification(data)`
   - `sendSubscriptionRenewalNotification(data)`
   - `sendSubscriptionCancellationNotification(data)`
   - `sendRefundNotification(data)`
   - `sendPaymentMethodUpdateNotification(data)`

2. **Create webhook handler** (`server/_core/stripeWebhook.ts`):
   - Verify Stripe signature
   - Route events to handlers
   - Handle test events
   - Error handling

3. **Register webhook endpoint** in `server/_core/index.ts`:
   ```typescript
   app.post("/api/stripe/webhook", express.raw({ type: "application/json" }), handleStripeWebhook);
   ```
   **Critical:** Register BEFORE `express.json()` middleware.

4. **Integrate with payment router** (`server/routers/payment.ts`):
   - Call notification functions on payment events
   - Pass metadata from payment context

### Phase 3: Frontend Implementation

1. **Create notification components:**
   - `NotificationBell.tsx` - Bell icon with dropdown
   - `NotificationCenter.tsx` - Full notification page
   - `NotificationToast.tsx` - Toast for real-time alerts

2. **Add to layout:**
   - Include NotificationBell in header/navbar
   - Link NotificationCenter to admin dashboard

3. **Implement real-time updates:**
   - Use tRPC subscriptions or polling
   - Update notification count on bell icon
   - Show toast on new notifications

### Phase 4: Testing & Deployment

1. **Unit tests** (`server/paymentNotifications.test.ts`):
   ```bash
   pnpm test server/paymentNotifications.test.ts
   ```

2. **Test with Stripe CLI:**
   ```bash
   stripe listen --forward-to localhost:3000/api/stripe/webhook
   stripe trigger payment_intent.succeeded
   ```

3. **Verify in database:**
   ```sql
   SELECT * FROM notifications ORDER BY createdAt DESC LIMIT 10;
   ```

## Key Implementation Details

### Notification Types

Each notification type has specific formatting and metadata:

```typescript
interface PaymentNotification {
  type: "payment_success" | "payment_failed" | "subscription_renewal" | "subscription_cancelled" | "refund_issued" | "account_change";
  title: string;              // e.g., "Payment Confirmed ✓"
  body: string;               // e.g., "Annual School License activated..."
  linkUrl: string;            // e.g., "/admin/payments?session=cs_xxx"
  metadata: {
    paymentType: string;
    tier: "school" | "district";
    amount: number;           // in cents
    currency: string;
    billingInterval: "month" | "year";
    customerEmail: string;
    customerName: string;
    [key: string]: any;       // Event-specific data
  };
}
```

### Admin Preferences

Admins can customize notifications:

```typescript
interface AdminNotificationPreferences {
  adminId: number;
  inAppPayments: boolean;           // Show in-app payment alerts
  inAppSystemAlerts: boolean;       // Show system alerts
  inAppAccountChanges: boolean;     // Show account changes
  emailPayments: boolean;           // Send email for payments
  emailSystemAlerts: boolean;       // Send email for system alerts
  emailAccountChanges: boolean;     // Send email for account changes
  emailDigestFrequency: "immediate" | "daily" | "weekly";
  quietHoursEnabled: boolean;
  quietHoursStart?: string;         // HH:MM
  quietHoursEnd?: string;           // HH:MM
}
```

### Webhook Signature Verification

All webhooks are verified using Stripe's signature:

```typescript
const event = stripe.webhooks.constructEvent(
  req.body,                           // Raw request body
  req.headers["stripe-signature"],    // Signature from Stripe
  process.env.STRIPE_WEBHOOK_SECRET   // Secret from dashboard
);
```

**Critical:** Webhook endpoint must be registered BEFORE `express.json()` middleware to access raw request body.

### Error Handling

Notifications are non-blocking. If notification creation fails, payment processing continues:

```typescript
try {
  await sendPaymentConfirmationNotification(data);
} catch (error) {
  console.error("Failed to send notification:", error);
  // Payment succeeds even if notification fails
}
```

## Bundled Resources

### Scripts

- **`setup_payment_notifications.py`** - Generate boilerplate code for your project
  ```bash
  python scripts/setup_payment_notifications.py /path/to/project
  ```

### References

- **`implementation-guide.md`** - Step-by-step setup instructions with code examples
- **`stripe-events.md`** - Complete Stripe webhook event reference and testing guide

## Testing Checklist

- [ ] Database tables created (`pnpm db:push`)
- [ ] Notification helpers implemented
- [ ] Webhook handler created and registered
- [ ] Webhook registered BEFORE `express.json()`
- [ ] Payment router calls notification functions
- [ ] Unit tests passing (`pnpm test`)
- [ ] Stripe CLI webhook forwarding working
- [ ] Test events trigger notifications
- [ ] Notifications appear in database
- [ ] Admin UI displays notifications
- [ ] Admin preferences respected

## Common Issues & Solutions

### Webhook Signature Verification Failed
**Cause:** Webhook registered after `express.json()` or webhook secret incorrect
**Solution:** Register webhook BEFORE `express.json()`, verify secret in Stripe dashboard

### Notifications Not Appearing
**Cause:** Admin user doesn't exist or preferences not set
**Solution:** Check admin user exists, verify preferences in database

### Webhook Not Triggered
**Cause:** Endpoint not reachable or secret incorrect
**Solution:** Test with Stripe CLI, verify endpoint is accessible, check secret

### Duplicate Notifications
**Cause:** Webhook retried and processed multiple times
**Solution:** Use event ID as unique constraint, implement idempotency

## Next Steps

1. **Email Notifications** - Extend to send emails alongside in-app notifications
2. **Admin Settings UI** - Create page for customizing notification preferences
3. **Webhook Monitoring** - Add dashboard showing webhook delivery status
4. **Notification Analytics** - Track notification delivery and engagement
5. **Scheduled Digests** - Implement daily/weekly email digests

## Production Considerations

### Idempotency
Webhooks may be delivered multiple times. Use event ID as unique constraint:

```typescript
await createAdminNotification({
  ...data,
  externalId: event.id, // Stripe event ID
});
```

### Monitoring
Log all webhook events for audit trail:

```typescript
console.log(`[Webhook] ${event.type} processed at ${new Date().toISOString()}`);
```

### Retry Logic
Stripe automatically retries failed webhooks with exponential backoff (up to 24 hours).

### Security
- Never log sensitive payment data (full card numbers, CVV)
- Verify webhook signature on every request
- Use environment variables for webhook secret
- Restrict webhook endpoint to POST requests only


