import enum
import sys
import time
from typing import NewType, Optional

import telepot
from telepot.loop import MessageLoop
from telepot.namedtuple import InlineKeyboardButton, InlineKeyboardMarkup

import draw
import hanabi

MIN_PLAYERS = 2
MAX_PLAYERS = max(hanabi.HAND_SIZE)
DEFAULT_N_PLAYERS_IN_TEST = 4


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
    def __init__(self, chat_id: ChatId, admin: UserId):
        self.game = None  # type: Optional[hanabi.Game]
        self.admin = admin
        self.player_to_user = {}  # type: dict[hanabi.Player, UserId]
        self.user_to_message = {}  # type: dict[UserId, Optional[Message]]
        self.current_action = ""
        self.chat_id = chat_id


class BotServer:
    def __init__(self, token: str):
        self.bot = telepot.Bot(token)
        self.token = token
        self.games = {}  # type: dict[ChatId, ChatGame]


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
        name += "_" + str(len(player_to_user))

    server.bot.sendMessage(chat_id, f"{name} joined")
    player_to_user[name] = user_id
    user_to_message[user_id] = None


def send_game_views(bot: telepot.Bot, chat_game: ChatGame):
    for name, user_id in chat_game.player_to_user.items():
        image = draw.draw_board_state(chat_game.game, name)
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

    server.games[chat_id].game = hanabi.Game(players)
    server.bot.sendMessage(chat_id, f"Game started with players {players}")

    # send a view to all the players
    chat_game = server.games[chat_id]
    send_game_views(server.bot, chat_game)
    server.bot.sendMessage(chat_id, "Game started!")


def edit_message(
    chat_game: ChatGame,
    bot: telepot.Bot,
    user_id: UserId,
    message: str,
    keyboard: Optional[InlineKeyboardMarkup] = None,
):
    edited = telepot.message_identifier(chat_game.user_to_message[user_id])
    bot.editMessageText(edited, message, reply_markup=keyboard)


def delete_message(chat_game: ChatGame, bot: telepot.Bot, user_id: UserId):
    edited = telepot.message_identifier(chat_game.user_to_message[user_id])
    bot.deleteMessage(edited)


def send_keyboard(bot: telepot.Bot, chat_id: ChatId, keyboard_type: KeyboardType):
    chat_game = server.games[chat_id]
    player = hanabi.get_active_player_name(chat_game.game)
    user_id = chat_game.player_to_user[player]
    if keyboard_type is KeyboardType.ACTION:
        action_row = [
            InlineKeyboardButton(text="Discard", callback_data=f"discard|{chat_id}"),
            InlineKeyboardButton(text="Play", callback_data=f"play|{chat_id}"),
        ]
        if chat_game.game.hints > 0:
            action_row.append(
                InlineKeyboardButton(text="Hint", callback_data=f"hint|{chat_id}")
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
            chat_game, bot, user_id, "Choose information to hint", keyboard=keyboard
        )


def restart_turn(chat_id: ChatId):
    chat_game = server.games[chat_id]
    chat_game.current_action = ""
    send_keyboard(server.bot, chat_id, KeyboardType.ACTION)


def handle_game_ending(bot: telepot.Bot, chat_game: ChatGame):
    send_game_views(bot, chat_game)
    chat_id = chat_game.chat_id
    game = chat_game.game
    image = draw.draw_board_state(chat_game.game, player_viewing=None)
    try:
        bot.sendPhoto(chat_id, image)
    except Exception as ex:
        print(ex)

    score = hanabi.get_score(game)
    for name, user_id in chat_game.player_to_user.items():
        bot.sendMessage(user_id, f"The game ended with score {score}")

    bot.sendMessage(chat_id, f"The game ended with score {score}")
    bot.sendMessage(chat_id, "Send /restart to play again")
    chat_game.game = None


def complete_processed_action(bot: telepot.Bot, chat_id: ChatId):
    # check game ending
    chat_game = server.games[chat_id]
    if hanabi.check_state(chat_game.game) != 0:
        handle_game_ending(bot, chat_game)
        return

    send_game_views(bot, chat_game)
    chat_game.current_action = ""
    send_keyboard(server.bot, chat_id, KeyboardType.ACTION)


def handle_keyboard_response(msg: Message) -> Optional[bool]:
    try:
        _query_id, _from_id, data = telepot.glance(msg, flavor="callback_query")
    except Exception:
        print("[ERROR]", msg)
        return

    user_id = UserId(msg["from"]["id"])
    chat_id = ChatId(msg["message"]["chat"]["id"])

    if data == "join":
        add_player(server, chat_id, user_id, msg["from"]["first_name"])
        return

    data, chat_id = data.split("|")
    chat_id = ChatId(chat_id)

    chat_game = server.games.get(chat_id, None)
    if not chat_game:
        return

    game = chat_game.game
    if not game:
        return

    active_player = hanabi.get_active_player_name(game)
    active_user_id = chat_game.player_to_user[active_player]
    if user_id != active_user_id:
        return

    # perform action
    if chat_game.current_action in [
        "discard",
        "play",
    ] or chat_game.current_action.strip().startswith("hint "):
        chat_game.current_action += " " + data
        success = hanabi.perform_action(game, active_player, chat_game.current_action)

        if success:
            delete_message(chat_game, server.bot, user_id)
            chat_game.user_to_message[active_user_id] = None
            complete_processed_action(server.bot, chat_id)
        else:
            restart_turn(chat_id)

    if chat_game.current_action == "hint":
        chat_game.current_action += " " + data
        send_keyboard(server.bot, chat_id, KeyboardType.INFO)

    if data == "back":
        send_keyboard(server.bot, chat_id, KeyboardType.ACTION)

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


def handle_message(message_object: Message):
    content_type, _chat_type, chat_id = telepot.glance(message_object)

    user_id = UserId(message_object["from"]["id"])

    if content_type != "text":
        return

    text = message_object["text"].split("@")[0].strip()  # type: str
    data = message_object.get("callback_data", None)  # type: str
    chat_id = ChatId(chat_id)
    if data:
        print("DATA", data)

    if text == "/new_game":
        server.games[chat_id] = ChatGame(chat_id, admin=user_id)
        keyboard = [
            [
                InlineKeyboardButton(text="Join", callback_data="join"),
            ]
        ]
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard)
        server.bot.sendMessage(
            chat_id, "A new game has been created", reply_markup=keyboard
        )
        return

    elif text == "/end_game":
        edit_message(server.games[chat_id], server.bot, user_id, "The game ended.")
        del server.games[chat_id]
        return

    elif text in ["/start", "/restart"]:
        start_game(server, chat_id, user_id)

    elif text.startswith("/test"):
        try:
            _, n = text.split(" ")
            n = int(n)
        except ValueError:
            n = DEFAULT_N_PLAYERS_IN_TEST
        server.games[chat_id] = ChatGame(chat_id, admin=user_id)
        server.bot.sendMessage(chat_id, "A new game has been created.")
        test_players = [
            hanabi.Player(s) for s in ["Alice", "Bob", "Carol", "Dan", "Erin", "Frank"]
        ]
        for name in test_players[:n]:
            add_player(server, chat_id, user_id, name, allow_repeated_players=True)
        start_game(server, chat_id, user_id)
    else:
        return

    chat_game = server.games[chat_id]
    game = chat_game.game

    if not game:
        return

    restart_turn(chat_id)


def main(token: str):
    global server
    server = BotServer(token)

    print("*** Telegram bot started ***")
    print("    Now listening...")
    MessageLoop(
        server.bot, {"chat": handle_message, "callback_query": handle_keyboard_response}
    ).run_as_thread()
    while 1:
        time.sleep(10)


if __name__ == "__main__":
    main(sys.argv[1])
