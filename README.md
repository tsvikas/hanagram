
# Hanagram
Telegram bot to play Hanabi with your friends.

<img src="example.jpg" with="51">

# Install
Install hanagram and its dependencies:
```bash
git clone https://github.com/francesconazzaro/telepota.git  # telepota fork that fixes an issue with telegram polls
git clone https://github.com/giacomonazzaro/hanagram.git
pip install ./telepota
pip install -R ./hanagram/requirements.txt
```

# Telegram game
How to play a Telegram game:
- Start the server with `python3 main.py <your-bot-token>`
- Add your bot to a chat.
- Send `\new_game` to create a new game.
- Users can join the game with the `Join` button displayed (they must acitvate the bot).
- Send `\start` to start playing!

# Local game
How to play a local game. Let's say players are Alice, Bob and Casey.
- Run `python3 hanabi.py Alice Bob Casey`
- On each turn, type one of those actions:
    - `play <index of card to play>`
    - `discard <index of card to play>`
    - `hint <player name to hint> <color or value>`
