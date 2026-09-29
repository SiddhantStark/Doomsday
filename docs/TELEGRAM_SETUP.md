# Telegram setup

Telegram is the only external alert channel. Setup status: user confirmed bot creation and private-chat Start. The token was accepted by Telegram and the private chat ID was saved in the ignored local .env. Telegram accepted one user-authorized test alert, and the user confirmed receipt in the private chat.

## User setup

1. Open the official [@BotFather](https://t.me/BotFather) in Telegram and use `/newbot`.
2. Choose a bot name and available username. Keep the returned bot token private.
3. Open your new bot's private chat and press Start or send `/start`. Bots cannot initiate a private conversation until the user starts it.
4. During implementation, obtain your private chat ID from the bot's `getUpdates` response to that message. Use a local setup helper that reads the token from the environment; do not paste token-bearing API URLs into browser history or share raw updates.
5. Save `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in an ignored local `.env`, then deployment secrets when needed. Never commit them or paste the token into chat.
6. In Phase 5, authorize one test message, confirm it appears in your Telegram chat, and ensure notifications for that chat are enabled on your phone.

```dotenv
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

A webhook or continuously running inbound server is unnecessary for outbound alerts. `getUpdates` is needed only for setup unless later features add bot commands. If the bot already has a webhook, resolve that configuration deliberately before using polling.

## Free-use requirements

The standard bot platform is free for our low-volume personal alerts. Keep `allow_paid_broadcast` false or omitted. No payment details, business verification, or message-template approval is needed for this flow. Hosting and state storage are separate dependencies: validate their free allowances before deployment and never enable paid overages automatically.

## Send semantics

Use plain-text `sendMessage` with a booking link. Record the returned `message_id` and API acceptance; Telegram's standard Bot API does not provide device-delivery or read receipts for this workflow. Respect rate limits, retain failed events, and record ambiguous timeouts as uncertain. A blocked bot or invalid token must be visible in workflow logs because there is no second external alert channel.

References: [Bot introduction](https://core.telegram.org/bots), [Bot FAQ](https://core.telegram.org/bots/faq), [sendMessage](https://core.telegram.org/bots/api#sendmessage), [getUpdates](https://core.telegram.org/bots/api#getupdates).

## Verification result

Bot creation, private-chat setup, token validation, chat-ID retrieval, and one test message are complete. The user confirmed receipt. Application notification logic and automated monitoring are not implemented yet.
