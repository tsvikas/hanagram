import enum
import itertools
import os
import time
from typing import NewType

import dotenv
import telepot  # type: ignore[import-untyped]
from telepot.loop import MessageLoop  # type: ignore[import-untyped]
from telepot.namedtuple import (  # type: ignore[import-untyped]
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)

from hanabi import draw, hanabi

dotenv.load_dotenv()

USERNAME = os.environ["TELEGRAM_USERNAME"]
TELEGRAM_API_KEY = os.environ["TELEGRAM_API_KEY"]
START_LINK = f"https://t.me/{USERNAME}"

MIN_PLAYERS = 2
MAX_PLAYERS = max(hanabi.HAND_SIZE)
DEFAULT_N_PLAYERS_IN_TEST = 4
BOT_COMMAND_DESCRIPTIONS = {
    "start": "show help",
    "link_for_newbies": "send instructions to enable bot for new players",
    "new_game": "create a new game for this group, and publish a join link",
    "deal_cards": "start this group game",
    "end_game": "end this group game",
    "test": "start a playtest",
    "refresh": "resend current player the menu",
}

BACKGROUND_COLORS_RGB = itertools.cycle(
    (
        (20, 20, 20),  # black
        (100, 20, 20),  # red
        (10, 50, 10),  # green
        (15, 30, 74),  # blue
        (75, 0, 70),  # purple
    )
)


class UserId(int):
    pass


class ChatId(int):
    pass


Message = NewType("Message", dict)


class KeyboardType(enum.Enum):
    ACTION = "action"
    PLAY = "play"
    DISCARD = "discard"
    PLAYER = "player"
    INFO = "info"


class ChatGame:
    def __init__(self, chat_id: ChatId, admin: UserId, test_mode: bool = False):
        self.game: hanabi.Game | None = None
        self.admin = admin
        self.player_to_user: dict[hanabi.Player, UserId] = {}
        self.user_to_message: dict[UserId, Message | None] = {}
        self.current_action = ""
        self.chat_id = chat_id
        self.background_color = (70, 70, 70)  # fallback value
        self.test_mode = test_mode


class BotServer:
    def __init__(self, token: str):
        self.bot = telepot.Bot(token)
        self.token = token
        self.games: dict[ChatId, ChatGame] = {}


server = BotServer("DEADBEEF")


def add_player(
    server: BotServer,
    chat_id: ChatId,
    user_id: UserId,
    name: hanabi.Player,
    allow_repeated_players: bool = False,
):
    if chat_id not in server.games:
        server.bot.sendMessage(chat_id, "No game created for this chat")
        return

    player_to_user = server.games[chat_id].player_to_user
    user_to_message = server.games[chat_id].user_to_message
    if not allow_repeated_players and user_id in player_to_user.values():
        server.bot.sendMessage(chat_id, "You already joined the game")
        return

    if len(player_to_user) >= MAX_PLAYERS:
        server.bot.sendMessage(
            chat_id, f"There are already {MAX_PLAYERS} players in the game."
        )
        return

    if name in player_to_user:
        name = hanabi.Player(f"{name}_{len(player_to_user)}")

    server.bot.sendMessage(chat_id, f"{name} joined")
    player_to_user[name] = user_id
    user_to_message[user_id] = None


def send_game_views(bot: telepot.Bot, chat_game: ChatGame, keyboard: bool = False):
    if chat_game.test_mode:
        # send only once
        send_game_view(None, chat_game.admin, bot, chat_game)
    else:
        # first player
        assert chat_game.game is not None
        next_player = hanabi.get_active_player_name(chat_game.game)
        next_user_id = chat_game.player_to_user[next_player]
        send_game_view(next_player, next_user_id, bot, chat_game)
        # other players
        for name, user_id in chat_game.player_to_user.items():
            if name != next_player:
                send_game_view(name, user_id, bot, chat_game)
    # now send keyboard
    if keyboard:
        chat_game.current_action = ""
        send_keyboard(bot, chat_game.chat_id, KeyboardType.ACTION)


def send_game_view(
    name: hanabi.Player | None,
    user_id: UserId,
    bot: telepot.Bot,
    chat_game: ChatGame,
):
    assert chat_game.game is not None
    image = draw.draw_board_state(
        chat_game.game, player_viewing=name, background=chat_game.background_color
    )
    try:
        bot.sendPhoto(user_id, image)
    except Exception as ex:
        print(ex)


def start_game(server: BotServer, chat_id: ChatId, user_id: UserId):
    if chat_id not in server.games:
        server.bot.sendMessage(chat_id, "No game created for this chat")
        return

    if user_id != server.games[chat_id].admin:
        server.bot.sendMessage(chat_id, "You cannot start this game")
        return

    player_to_user = server.games[chat_id].player_to_user
    if len(server.games[chat_id].player_to_user) < MIN_PLAYERS:
        server.bot.sendMessage(chat_id, "Too few players")
        return

    players = list(player_to_user)
    server.bot.sendMessage(chat_id, f"Starting game with players {players}")
    server.bot.sendMessage(chat_id, "FYI: newest card → oldest card")
    chat_game = server.games[chat_id]
    chat_game.background_color = next(BACKGROUND_COLORS_RGB)
    chat_game.game = hanabi.Game(players)
    server.bot.sendMessage(
        chat_id, f"Go to [private chat]({START_LINK}) to play", parse_mode="Markdown"
    )

    # send a view to all the players
    send_game_views(server.bot, chat_game, keyboard=True)


def edit_message(
    chat_game: ChatGame,
    bot: telepot.Bot,
    user_id: UserId,
    message: str,
    keyboard: InlineKeyboardMarkup | None = None,
):
    if msg := chat_game.user_to_message[user_id]:
        edited = telepot.message_identifier(msg)
        bot.editMessageText(edited, message, reply_markup=keyboard)


def delete_message(chat_game: ChatGame, bot: telepot.Bot, user_id: UserId):
    edited = telepot.message_identifier(chat_game.user_to_message[user_id])
    bot.deleteMessage(edited)


def send_keyboard(bot: telepot.Bot, chat_id: ChatId, keyboard_type: KeyboardType):
    chat_game = server.games[chat_id]
    assert chat_game.game is not None
    player = hanabi.get_active_player_name(chat_game.game)
    user_id = chat_game.player_to_user[player]
    if keyboard_type is KeyboardType.ACTION:
        action_row = [
            InlineKeyboardButton(text="Play", callback_data=f"play|{chat_id}"),
            InlineKeyboardButton(text="Discard", callback_data=f"discard|{chat_id}"),
        ]
        if chat_game.game.hints > 0:
            action_row.append(
                InlineKeyboardButton(
                    text=f"Hint ({chat_game.game.hints})",
                    callback_data=f"hint|{chat_id}",
                )
            )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[action_row])
        if chat_game.user_to_message[user_id] is not None:
            edit_message(
                chat_game, bot, user_id, f"{player}, choose an action", keyboard
            )
        else:
            chat_game.user_to_message[user_id] = bot.sendMessage(
                user_id, f"{player}, it's your turn", reply_markup=keyboard
            )

    elif keyboard_type in [KeyboardType.PLAY, KeyboardType.DISCARD]:
        game = chat_game.game
        active_player = game.players[game.active_player]
        player_hand = chat_game.game.hands[active_player]
        options_row = [
            InlineKeyboardButton(
                text=card.known_name(), callback_data=f"{i + 1}|{chat_id}"
            )
            for i, card in enumerate(player_hand)
        ]

        back_row = [InlineKeyboardButton(text="Back", callback_data=f"back|{chat_id}")]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[options_row, back_row])
        edit_message(
            chat_game, bot, user_id, f"Choose card to {keyboard_type.value}", keyboard
        )

    elif keyboard_type == KeyboardType.PLAYER:
        players = chat_game.game.players
        options_row = [
            InlineKeyboardButton(text=p, callback_data=f"{p}|{chat_id}")
            for p in players
            if p != player
        ]
        back_row = [InlineKeyboardButton(text="Back", callback_data=f"back|{chat_id}")]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[options_row, back_row])
        edit_message(
            chat_game, bot, user_id, "Choose a player to hint", keyboard=keyboard
        )

    elif keyboard_type == KeyboardType.INFO:
        _action, hinted_player = chat_game.current_action.split(" ")
        colors_row = [
            InlineKeyboardButton(text=str(c), callback_data=f"{c}|{chat_id}")
            for c in hanabi.COLORS
        ]
        values_row = [
            InlineKeyboardButton(text=str(v), callback_data=f"{v}|{chat_id}")
            for v in hanabi.VALUES
        ]
        back_row = [InlineKeyboardButton(text="Back", callback_data=f"back|{chat_id}")]
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[colors_row, values_row, back_row]
        )
        edit_message(
            chat_game,
            bot,
            user_id,
            f"Choose information to hint to {hinted_player}",
            keyboard=keyboard,
        )


def restart_turn(chat_id: ChatId):
    chat_game = server.games[chat_id]
    chat_game.current_action = ""
    send_keyboard(server.bot, chat_id, KeyboardType.ACTION)


def handle_game_ending(bot: telepot.Bot, chat_game: ChatGame):
    assert chat_game.game is not None
    send_game_views(bot, chat_game)
    chat_id = chat_game.chat_id
    game = chat_game.game
    image = draw.draw_board_state(
        chat_game.game, player_viewing=None, background=chat_game.background_color
    )
    try:
        bot.sendPhoto(chat_id, image)
    except Exception as ex:
        print(ex)

    score = hanabi.get_score(game)
    for user_id in set(chat_game.player_to_user.values()).union([UserId(chat_id)]):
        bot.sendMessage(user_id, f"The game ended with score {score}")
    bot.sendMessage(chat_id, f"Type /deal_cards@{USERNAME} to play again")
    chat_game.game = None


def complete_processed_action(bot: telepot.Bot, chat_id: ChatId):
    # check game ending
    chat_game = server.games[chat_id]
    assert chat_game.game is not None
    if hanabi.check_state(chat_game.game) is not hanabi.GameState.RUNNING:
        handle_game_ending(bot, chat_game)
        return

    send_game_views(bot, chat_game, keyboard=True)


def handle_keyboard_response(msg: Message) -> bool | None:
    try:
        _query_id, _from_id, data = telepot.glance(msg, flavor="callback_query")
    except Exception:
        print("[ERROR]", msg)
        return None

    user_id = UserId(msg["from"]["id"])
    chat_id = ChatId(msg["message"]["chat"]["id"])

    if data == "join":
        add_player(server, chat_id, user_id, msg["from"]["first_name"])
        return None

    data, chat_id = data.split("|")
    chat_id = ChatId(chat_id)

    chat_game = server.games.get(chat_id, None)
    if not chat_game:
        return None

    game = chat_game.game
    if not game:
        return None

    active_player = hanabi.get_active_player_name(game)
    active_user_id = chat_game.player_to_user[active_player]
    if user_id != active_user_id:
        return None

    # perform action

    if data == "back":
        restart_turn(chat_id)
        return True

    if data == "discard":
        if chat_game.current_action != "":
            return False
        chat_game.current_action = "discard"
        send_keyboard(server.bot, chat_id, KeyboardType.DISCARD)
        return True

    if data == "play":
        if chat_game.current_action != "":
            return False
        chat_game.current_action = "play"
        send_keyboard(server.bot, chat_id, KeyboardType.PLAY)
        return True

    if data == "hint":
        if chat_game.current_action != "":
            return False
        chat_game.current_action = "hint"
        if len(chat_game.player_to_user) == 2:
            i = 1 - game.active_player
            chat_game.current_action += " " + game.players[i]
            send_keyboard(server.bot, chat_id, KeyboardType.INFO)
        else:
            send_keyboard(server.bot, chat_id, KeyboardType.PLAYER)
        return True

    if chat_game.current_action in [
        "discard",
        "play",
    ] or chat_game.current_action.startswith("hint "):
        chat_game.current_action += " " + data
        success = hanabi.perform_action(game, active_player, chat_game.current_action)

        if success:
            delete_message(chat_game, server.bot, user_id)
            chat_game.user_to_message[active_user_id] = None
            complete_processed_action(server.bot, chat_id)
        else:
            restart_turn(chat_id)
        return None

    if chat_game.current_action == "hint":
        chat_game.current_action += " " + data
        send_keyboard(server.bot, chat_id, KeyboardType.INFO)
        return None

    raise RuntimeError(f"invalid state, {chat_game.current_action=}, {data=}")


def link_for_newbies(chat_id):
    server.bot.sendMessage(
        chat_id,
        "Before you join a game for the first time, "
        f"please open a [chat with me]({START_LINK}) "
        "and press the big blue START button at the bottom.",
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


def handle_message(message_object: Message):
    content_type, _chat_type, chat_id = telepot.glance(message_object)

    user_id = UserId(message_object["from"]["id"])

    if content_type != "text":
        return

    text: str = message_object["text"].split("@")[0].strip()
    data: str = message_object.get("callback_data", None)
    chat_id = ChatId(chat_id)
    if data:
        print("DATA", data)

    if text == "/start":
        server.bot.sendMessage(chat_id, "Thanks for trying Hanagram bot.")
        server.bot.sendMessage(
            chat_id, "Add me to a group, than type /new_game to create a game."
        )
        server.bot.sendMessage(
            chat_id,
            "Type /refresh in that group to resend the menu to the current player.",
        )
        server.bot.sendMessage(
            chat_id, "Type /test in a group or a private chat, to run a playtest."
        )
        server.bot.sendMessage(
            chat_id,
            "If i'm sleeping, try to go to https://hanagram.onrender.com/ . "
            "It won't show anything, but it might wake me up.",
        )
        if chat_id != user_id:
            link_for_newbies(chat_id)

    if text == "/link_for_newbies":
        link_for_newbies(chat_id)

    if text == "/new_game":
        if user_id == chat_id:
            server.bot.sendMessage(chat_id, "Start the game in a group chat")
            return
        if chat_id in server.games and server.games[chat_id].game:
            server.bot.sendMessage(
                chat_id, "Game in progress. Send /end_game if you want to end it"
            )
            return
        server.games[chat_id] = ChatGame(chat_id, admin=user_id)
        keyboard = [[InlineKeyboardButton(text="Join", callback_data="join")]]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard)
        server.bot.sendMessage(
            chat_id,
            "🎴 A new game has been created.\n"
            f"After everyone joined, type /deal_cards@{USERNAME} to start the game",
        )
        link_for_newbies(chat_id)
        server.bot.sendMessage(
            chat_id,
            "Click here ↓ to join.",
            reply_markup=keyboard,
        )

    if text == "/end_game":
        if chat_id not in server.games:
            server.bot.sendMessage(chat_id, "No game to end")
        elif not server.games[chat_id].game:
            server.bot.sendMessage(chat_id, "Ending the game which has not started yet")
            del server.games[chat_id]
        else:
            try:
                server.bot.sendMessage(chat_id, "Ending the game")
                edit_message(
                    server.games[chat_id], server.bot, user_id, "The game ended."
                )
            finally:
                del server.games[chat_id]

    if text == "/deal_cards":
        start_game(server, chat_id, user_id)

    if text.startswith("/test"):
        try:
            _, n_str = text.split(" ")
            n = int(n_str)
        except ValueError:
            n = DEFAULT_N_PLAYERS_IN_TEST
        server.games[chat_id] = ChatGame(chat_id, admin=user_id, test_mode=True)
        server.bot.sendMessage(chat_id, "A new game has been created.")
        test_players = [
            hanabi.Player(s) for s in ["Alice", "Bob", "Carol", "Dan", "Erin", "Frank"]
        ]
        for name in test_players[:n]:
            add_player(server, chat_id, user_id, name, allow_repeated_players=True)
        start_game(server, chat_id, user_id)

    if text == "/refresh":
        if chat_id not in server.games:
            server.bot.sendMessage(chat_id, "No game to refresh")
        elif not server.games[chat_id].game:
            server.bot.sendMessage(chat_id, "Game has not started yet")
        else:
            restart_turn(chat_id)


def main(token: str):
    global server
    server = BotServer(token)
    server.bot.setMyCommands(
        [
            {"command": command, "description": description}
            for command, description in BOT_COMMAND_DESCRIPTIONS.items()
        ]
    )

    print("*** Telegram bot started ***")
    print("    Now listening...")
    MessageLoop(
        server.bot, {"chat": handle_message, "callback_query": handle_keyboard_response}
    ).run_as_thread()
    while 1:
        time.sleep(10)


if __name__ == "__main__":
    main(os.environ["TELEGRAM_API_KEY"])
