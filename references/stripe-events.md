# Stripe Webhook Events Reference

## Supported Events

### Payment Events

#### `checkout.session.completed`
**When:** Checkout session is completed (payment processed)
**Metadata:**
```json
{
  "id": "cs_test_123",
  "amount_total": 99900,
  "currency": "usd",
  "customer_email": "school@example.com",
  "metadata": {
    "tier": "school",
    "billingInterval": "annual",
    "customerName": "Example School"
  }
}
```
**Action:** Send payment confirmation notification

#### `payment_intent.succeeded`
**When:** Payment intent succeeds (alternative to checkout.session.completed)
**Metadata:**
```json
{
  "id": "pi_test_123",
  "amount": 99900,
  "currency": "usd",
  "metadata": {
    "tier": "school",
    "billingInterval": "annual",
    "customerEmail": "school@example.com",
    "customerName": "Example School"
  }
}
```
**Action:** Send payment confirmation notification

#### `payment_intent.payment_failed`
**When:** Payment intent fails (card declined, insufficient funds, etc.)
**Metadata:**
```json
{
  "id": "pi_test_456",
  "amount": 99900,
  "currency": "usd",
  "last_payment_error": {
    "message": "Card declined"
  },
  "metadata": {
    "tier": "district",
    "billingInterval": "month",
    "customerEmail": "district@example.com",
    "customerName": "Example District"
  }
}
```
**Action:** Send payment failure notification with reason

### Subscription Events

#### `customer.subscription.created`
**When:** Subscription is created
**Metadata:**
```json
{
  "id": "sub_test_123",
  "customer": "cus_test_123",
  "items": {
    "data": [
      {
        "price": {
          "amount": 99900,
          "currency": "usd",
          "recurring": {
            "interval": "year"
          }
        }
      }
    ]
  },
  "metadata": {
    "tier": "school"
  }
}
```
**Action:** Log subscription creation (optional notification)

#### `customer.subscription.updated`
**When:** Subscription is updated (e.g., renewal date approaching)
**Metadata:**
```json
{
  "id": "sub_test_123",
  "current_period_end": 1707868800,
  "customer": "cus_test_123",
  "metadata": {
    "tier": "school"
  }
}
```
**Action:** Check if renewal is within 7 days, send renewal notification

#### `customer.subscription.deleted`
**When:** Subscription is cancelled
**Metadata:**
```json
{
  "id": "sub_test_789",
  "customer": "cus_test_123",
  "canceled_at": 1707868800,
  "cancellation_details": {
    "reason": "cancellation_requested"
  },
  "metadata": {
    "tier": "school"
  }
}
```
**Action:** Send subscription cancellation notification

### Refund Events

#### `charge.refunded`
**When:** Charge is refunded
**Metadata:**
```json
{
  "id": "ch_test_123",
  "amount": 99900,
  "currency": "usd",
  "refunded": true,
  "refunds": {
    "data": [
      {
        "id": "re_test_123",
        "amount": 99900,
        "reason": "duplicate"
      }
    ]
  }
}
```
**Action:** Send refund notification with reason

### Invoice Events

#### `invoice.paid`
**When:** Invoice is paid
**Metadata:**
```json
{
  "id": "in_test_123",
  "amount_paid": 99900,
  "currency": "usd",
  "customer": "cus_test_123",
  "subscription": "sub_test_123"
}
```
**Action:** Log invoice payment (optional notification)

#### `invoice.payment_failed`
**When:** Invoice payment fails
**Metadata:**
```json
{
  "id": "in_test_456",
  "amount_due": 99900,
  "currency": "usd",
  "customer": "cus_test_123",
  "last_finalization_error": {
    "message": "Card declined"
  }
}
```
**Action:** Send payment failure notification

## Event Handling Pattern

```typescript
export async function handleStripeWebhook(req: any, res: any) {
  const sig = req.headers["stripe-signature"];
  const event = stripe.webhooks.constructEvent(
    req.body,
    sig,
    process.env.STRIPE_WEBHOOK_SECRET
  );

  // Handle test events
  if (event.id.startsWith("evt_test_")) {
    return res.json({ verified: true });
  }

  try {
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

      case "customer.subscription.created":
        await handleSubscriptionCreated(event.data.object);
        break;

      case "customer.subscription.updated":
        await handleSubscriptionUpdated(event.data.object);
        break;

      case "customer.subscription.deleted":
        await handleSubscriptionDeleted(event.data.object);
        break;

      case "charge.refunded":
        await handleChargeRefunded(event.data.object);
        break;

      case "invoice.paid":
        await handleInvoicePaid(event.data.object);
        break;

      case "invoice.payment_failed":
        await handleInvoicePaymentFailed(event.data.object);
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
```

## Webhook Signature Verification

All webhooks must be verified using Stripe's signature:

```typescript
const event = stripe.webhooks.constructEvent(
  req.body,           // Raw request body (must not be parsed)
  sig,                // Stripe signature from header
  webhookSecret       // Webhook secret from Stripe dashboard
);
```

**Critical:** Webhook endpoint must be registered BEFORE `express.json()` middleware to access raw request body.

```typescript
// ✅ Correct order
app.post("/api/stripe/webhook", express.raw({ type: "application/json" }), handleStripeWebhook);
app.use(express.json());

// ❌ Wrong order
app.use(express.json());
app.post("/api/stripe/webhook", handleStripeWebhook); // Will fail signature verification
```

## Test Events

Stripe provides test events that start with `evt_test_`:

```typescript
if (event.id.startsWith("evt_test_")) {
  console.log("[Webhook] Test event detected");
  return res.json({ verified: true });
}
```

Test events are useful for:
- Testing webhook delivery without processing
- Verifying webhook endpoint is reachable
- Testing signature verification logic

## Webhook Retry Logic

Stripe automatically retries failed webhooks with exponential backoff:

1. Immediately
2. 5 seconds later
3. 5 minutes later
4. 30 minutes later
5. 2 hours later
6. 5 hours later
7. 10 hours later
8. 24 hours later

After 8 retries (24 hours), the webhook is marked as failed.

## Webhook Delivery Status

Monitor webhook delivery in Stripe dashboard:

1. Go to Developers → Webhooks
2. Click on webhook endpoint
3. View event delivery history
4. Check response status and body

## Common Issues

### Signature Verification Failed
- Ensure webhook secret is correct
- Ensure request body is raw (not parsed)
- Ensure webhook is registered before JSON middleware

### Webhook Not Triggered
- Verify webhook endpoint is reachable
- Check firewall/network settings
- Verify webhook secret in Stripe dashboard
- Test with Stripe CLI

### Event Not Processed
- Check error logs for exceptions
- Verify event type is handled
- Check database for notification records
- Verify admin user exists

## Testing Webhooks Locally

### Using Stripe CLI

1. **Install Stripe CLI:**
   ```bash
   brew install stripe/stripe-cli/stripe
   ```

2. **Login to Stripe account:**
   ```bash
   stripe login
   ```

3. **Forward webhooks to local endpoint:**
   ```bash
   stripe listen --forward-to localhost:3000/api/stripe/webhook
   ```

4. **Trigger test events:**
   ```bash
   stripe trigger payment_intent.succeeded
   stripe trigger payment_intent.payment_failed
   stripe trigger customer.subscription.created
   stripe trigger customer.subscription.deleted
   stripe trigger charge.refunded
   ```

5. **View webhook logs:**
   ```bash
   stripe logs tail
   ```

### Using Webhook Testing Tools

- **Stripe Dashboard:** Developers → Webhooks → Send test event
- **Postman:** Send raw webhook payload with Stripe signature
- **curl:** Manually craft webhook request with signature

## Production Considerations

### Idempotency

Webhooks may be delivered multiple times. Ensure handlers are idempotent:

```typescript
// ❌ Not idempotent - creates duplicate notification
await createAdminNotification(data);

// ✅ Idempotent - uses unique constraint
await createAdminNotification({
  ...data,
  externalId: event.id, // Stripe event ID
});
```

### Error Handling

Always return appropriate HTTP status:

```typescript
// ✅ Correct
if (error) {
  console.error("Error:", error);
  return res.status(500).json({ error: "Processing failed" });
}
res.json({ received: true });

// ❌ Wrong
res.json({ received: true }); // Returns 200 even on error
```

### Monitoring

Track webhook delivery and processing:

```typescript
console.log(`[Webhook] Received ${event.type} event`);
console.log(`[Webhook] Processing ${event.type} event`);
console.log(`[Webhook] Completed ${event.type} event`);
```

### Logging

Log all webhook events for audit trail:

```typescript
await logWebhookEvent({
  stripeEventId: event.id,
  type: event.type,
  timestamp: new Date(event.created * 1000),
  status: "processed",
  data: event.data.object,
});
```
