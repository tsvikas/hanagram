import sys
from random import shuffle
from typing import NamedTuple, Optional, Union

import draw

ALLOWED_ERRORS = 3
INITIAL_HINTS = 8
HAND_SIZE = {2: 5, 3: 5, 4: 4, 5: 4, 6: 3}


class Player(str):
    pass


class Color(str):
    pass


class Value(int):
    pass


COLORS = [Color(s) for s in ["red", "blue", "green", "white", "yellow"]]
CARD_COUNT = {Value(1): 3, Value(2): 2, Value(3): 2, Value(4): 2, Value(5): 1}

# calculate useful constants
VALUES = list(CARD_COUNT)
MAX_VALUE = max(VALUES)
COLOR_COUNT = sum(CARD_COUNT.values())


class Card(NamedTuple):
    color: Color
    value: Value


def new_deck() -> list[Card]:
    deck = [
        Card(color, value)
        for color in COLORS
        for value in VALUES
        for _ in range(CARD_COUNT[value])
    ]
    shuffle(deck)
    return deck


class HandCard:
    def __init__(self, color: Color, value: Value):
        self.color = color
        self.value = value
        self.is_color_known = False
        self.is_value_known = False
        self.not_colors = []
        self.not_values = []

    def __str__(self):
        return self.color + " " + str(self.value)

    def known_name(self) -> str:
        data = [
            self.color if self.is_color_known else "",
            str(self.value) if self.is_value_known else "",
        ]
        name = " ".join(data).strip()
        return name or " "


def to_string(card: HandCard, show_value: bool, show_info: bool) -> str:
    info = []
    result = ""
    if show_value:
        result += card.color + " " + str(card.value)

    if show_info:
        if card.is_color_known:
            info.append(card.color)
        if card.is_value_known:
            info.append(str(card.value))

        for color in card.not_colors:
            info.append("not " + color)
        for value in card.not_values:
            info.append("not " + str(value))

    if info:
        if show_value:
            result += ", "
        result += "{"
        result += ", ".join(info)
        result += "}"

    return result


def draw_card(hand: list[HandCard], deck: list[Card]):
    if not deck:
        return

    card = deck.pop()
    hand_card = HandCard(card.color, card.value)
    hand.insert(0, hand_card)


def new_hand(deck: list[Card], num_cards: int) -> list[HandCard]:
    assert num_cards in HAND_SIZE.values()
    hand = []
    for _ in range(num_cards):
        draw_card(hand, deck)
    return hand


class Game:
    def __init__(self, player_names: list[Player]):
        assert len(player_names) in HAND_SIZE
        self.players = player_names
        self.deck = new_deck()
        self.discarded = {
            color: [] for color in COLORS
        }  # type: dict[Color, list[Value]]
        self.errors = 0
        self.hints = INITIAL_HINTS
        num_cards = HAND_SIZE[len(self.players)]
        self.hands = {
            player: new_hand(self.deck, num_cards) for player in player_names
        }  # type: dict[Player, list[HandCard]]
        self.piles = {color: 0 for color in COLORS}  # type: dict[Color, int]
        self.final_moves = 0
        self.active_player = 0
        # TODO: better initial sentence
        self.last_action_description = "Game just started"


def print_hand(game: Game, player: Player, show_value: bool, show_info: bool):
    print(f"{player}'s hand:")
    for i, card in enumerate(game.hands[player]):
        s = to_string(card, show_value, show_info)
        print(f"[{i + 1}]: {s}")


def check_color_finished(game: Game, color: Color) -> bool:
    hinted = sum(
        1
        for hand in game.hands.values()
        for card in hand
        if card.is_color_known and card.color == color
    )
    in_pile = game.piles[color]
    discarded = len(game.discarded[color])
    total = hinted + in_pile + discarded
    return total == COLOR_COUNT


def check_value_finished(game: Game, value: Value) -> bool:
    hinted = sum(
        1
        for hand in game.hands.values()
        for card in hand
        if card.is_value_known and card.value == value
    )
    in_piles = sum(1 for color in COLORS if game.piles[color] >= value)
    discarded = sum(game.discarded[color].count(value) for color in COLORS)
    total = hinted + in_piles + discarded
    return total == len(COLORS) * CARD_COUNT[value]


def count_discarded(game: Game, color: Color, value: Value) -> int:
    return sum(
        1 for discarded_value in game.discarded[color] if discarded_value == value
    )


def check_card_finished(game: Game, color: Color, value: Value) -> bool:
    discarded = count_discarded(game, color, value)
    played = 1 if game.piles[color] >= value else 0
    in_hands = sum(
        1
        for hand in game.hands.values()
        for card in hand
        if card.is_color_known
        and card.is_value_known
        and card.value == value
        and card.color == color
    )

    total = discarded + played + in_hands
    assert total <= CARD_COUNT[value]
    return total == CARD_COUNT[value]


def is_critical_card(game: Game, color: Color, value: Value) -> bool:
    if game.piles[color] >= value:
        return False
    for lower_value in range(game.piles[color] + 1, value):
        if (
            count_discarded(game, color, Value(lower_value))
            == CARD_COUNT[Value(lower_value)]
        ):
            return False
    if count_discarded(game, color, value) == CARD_COUNT[value] - 1:
        return True
    return False


def update_not_colors(card: HandCard, color: Color):
    if card.color != color:
        if not card.is_color_known and color not in card.not_colors:
            card.not_colors.append(color)
            if len(card.not_colors) == len(COLORS) - 1:
                card.not_colors = []
                card.is_color_known = True


def update_not_values(card: HandCard, value: Value):
    if card.value != value:
        if not card.is_value_known and value not in card.not_values:
            card.not_values.append(value)
            if len(card.not_values) == len(VALUES) - 1:
                card.not_values = []
                card.is_value_known = True


def update_hand_info(game: Game):
    for color in COLORS:
        if check_color_finished(game, color):
            for hand in game.hands.values():
                for card in hand:
                    update_not_colors(card, color)

    for value in VALUES:
        if check_value_finished(game, value):
            for hand in game.hands.values():
                for card in hand:
                    update_not_values(card, value)

    for hand in game.hands.values():
        for card in hand:
            if card.is_value_known and not card.is_color_known:
                for color in COLORS:
                    if check_card_finished(game, color, card.value):
                        update_not_colors(card, color)

            elif card.is_color_known and not card.is_value_known:
                for value in VALUES:
                    if check_card_finished(game, card.color, value):
                        update_not_values(card, value)


def discard_card(game: Game, player: Player, index: int) -> bool:
    if index < 1 or index > len(game.hands[player]):
        return False

    print(f"discarding {index}")

    hand = game.hands[player]
    card = hand.pop(index - 1)
    game.discarded[card.color].append(card.value)
    game.hints = min(game.hints + 1, INITIAL_HINTS)

    if len(game.deck) == 0:
        game.final_moves += 1

    draw_card(hand, game.deck)
    return True


def play_card(game: Game, player: Player, index: int) -> bool:
    if index < 1 or index > len(game.hands[player]):
        return False

    hand = game.hands[player]
    card = hand.pop(index - 1)

    success = False
    pile = game.piles[card.color]
    if card.value == pile + 1:
        success = True
        if card.value == MAX_VALUE:
            game.hints = min(game.hints + 1, INITIAL_HINTS)

    if success:
        game.piles[card.color] += 1
    else:
        game.errors += 1
        game.discarded[card.color].append(card.value)

    if len(game.deck) == 0:
        game.final_moves += 1

    draw_card(hand, game.deck)
    return True


def check_state(game: Game) -> int:
    """
    return -1 if game has ended because of errors or empty deck,
    1 if game has ended because of full score
    0 if game has not ended
    """
    if game.errors == ALLOWED_ERRORS:
        return -1

    if all(p == MAX_VALUE for p in game.piles.values()):
        return 1

    if len(game.deck) == 0 and game.final_moves == len(game.players):
        return -1

    if all(
        count_discarded(game, color, Value(game.piles[color] + 1))
        == CARD_COUNT[Value(game.piles[color] + 1)]
        for color in COLORS
        if Value(game.piles[color]) < MAX_VALUE
    ):
        return -1

    return 0


def get_active_player_name(game: Game) -> Player:
    return game.players[game.active_player]


def give_color_hint(hand: list[HandCard], color: Color):
    for card in hand:
        if card.color == color:
            card.is_color_known = True
            card.not_colors = []
        else:
            if color not in card.not_colors:
                card.not_colors.append(color)

        if len(card.not_colors) == len(COLORS) - 1:
            card.not_colors = []
            card.is_color_known = True


def give_value_hint(hand: list[HandCard], value: Value):
    for card in hand:
        if card.value == value:
            card.is_value_known = True
            card.not_values = []
        else:
            if value not in card.not_values:
                card.not_values.append(value)

        if len(card.not_values) == len(VALUES) - 1:
            card.not_values = []
            card.is_value_known = True


def give_hint(game: Game, player: Player, hint: Union[Color, Value]) -> bool:
    assert game.hints > 0
    hand = game.hands[player]
    if isinstance(hint, Color):
        give_color_hint(hand, hint)
    elif isinstance(hint, Value):
        give_value_hint(hand, hint)
    else:
        return False

    game.hints -= 1
    if not game.deck:
        game.final_moves += 1
    return True


def parse_int(s: str) -> tuple[int, bool]:
    try:
        return int(s.strip()), True
    except ValueError:
        return 0, False


def perform_action(game: Game, player: Player, action: str) -> bool:
    name, value = action.strip().split(" ", 1)
    ok = False
    description = player[:] + " "

    if name == "discard":
        index, ok = parse_int(value)
        if not ok:
            return False
        hand_card = game.hands[player][index - 1]
        description += "discarded a "
        if is_critical_card(game, hand_card.color, hand_card.value):
            description += "critical "
        if hand_card.is_value_known or hand_card.is_color_known:
            description += "hinted "
        description += str(hand_card)
        ok = discard_card(game, player, index)

    elif name == "play":
        index, ok = parse_int(value)
        if not ok:
            return False
        hand_card = game.hands[player][index - 1]
        hinted = hand_card.is_value_known or hand_card.is_color_known
        if not hinted:
            description += "blind-"
        description += "played a "
        if is_critical_card(game, hand_card.color, hand_card.value):
            description += "critical "
        description += str(hand_card)
        errors = game.errors
        ok = play_card(game, player, index)
        if game.errors != errors:
            description += ", and it failed"

    elif name == "hint":
        other_player, hint = value.split(" ")
        if other_player == player:
            return False
        if other_player not in game.hands:
            return False
        if hint not in COLORS:
            index, ok = parse_int(hint)
            if not ok:
                return False
            ok = give_hint(game, other_player, Value(index))
        else:
            ok = give_hint(game, other_player, Color(hint))
        description += f"hinted {hint!r} to {other_player}"

    if not ok:
        print("Invalid action. Please repeat.")
    else:
        game.active_player = (game.active_player + 1) % len(game.players)

    game.last_action_description = description
    if ok:
        update_hand_info(game)
    return ok


def get_score(game: Game):
    return sum(game.piles.values())


def print_board_state(game: Game, seen_from: Optional[Player] = None):
    for player in game.players:
        print()
        print_hand(game, player, player != seen_from, True)
        print()

    for color in COLORS:
        print(f"{color:6}: {game.piles[color]}  {game.discarded[color]}")
    print()

    score = get_score(game)
    print(f"hints: {game.hints}, errors: {game.errors}")
    print(f"score: {score}, deck: {len(game.deck)}")
    print()


def main():
    players = [Player(s) for s in sys.argv[1:]]
    print(players)
    game = Game(players)

    while True:
        # print_board_state(game, game.players[game.active_player])
        image = draw.draw_board_state(game, game.players[game.active_player])
        with open("image.png", "wb") as f:
            f.write(image.read())

        result = check_state(game)
        if result > 0:
            print("*** You win! ***")
            break
        elif result < 0:
            print("*** You lost! ***")
            break

        ok = False
        while not ok:
            action = input(players[game.active_player] + ": ")
            ok, description = perform_action(game, players[game.active_player], action)
            if ok:
                print(description)
                print()
                print("    *****************")
                print()


if __name__ == "__main__":
    main()
