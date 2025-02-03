# Hanagram

Telegram bot to play Hanabi with your friends.

<img src="assets/example.webp">

# Usage

- Get an API TOKEN from `@BotFather`
- Save to the `.env` file:

```bash
cp .env.sample .env
nano .env  # set the API TOKEN
```

And run the server with
[uv](https://docs.astral.sh/uv/getting-started/installation/)

```bash
uv run main.py
```

# Telegram game

How to play a Telegram game:

- Send `/test <number-of-players>` in a private chat, to test.
- Add your bot to a group chat.
- Send `/new_game` in a group chat to create a new game.
- Players must first activate the bot with `/start` in private chat.
- Users can join the game with the `Join` button displayed.
- Send `/start_game` to start playing!

# Local game

How to play a local game. Let's say players are Alice, Bob and Casey.

- Run `uv run python hanabi/hanabi.py Alice Bob Casey`
- On each turn, type one of those actions:
  - `play <index of card to play>`
  - `discard <index of card to play>`
  - `hint <player name to hint> <color or value>`

# Development

- please run `uv run pre-commit install` to set up the pre-commit hooks.
