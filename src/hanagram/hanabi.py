import enum
from dataclasses import dataclass, field
from random import shuffle

ALLOWED_ERRORS = 3
INITIAL_HINTS = 8
HAND_SIZE = {2: 5, 3: 5, 4: 4, 5: 4, 6: 3}


class Player(str):
    pass


class Color(enum.StrEnum):
    RED = enum.auto()
    BLUE = enum.auto()
    GREEN = enum.auto()
    WHITE = enum.auto()
    YELLOW = enum.auto()


COLORS = Color.__members__.values()


class Value(enum.IntEnum):
    n1 = 1
    n2 = 2
    n3 = 3
    n4 = 4
    n5 = 5


CARD_COUNT = {Value.n1: 3, Value.n2: 2, Value.n3: 2, Value.n4: 2, Value.n5: 1}

# calculate useful constants
VALUES = Value.__members__.values()
MAX_VALUE = max(VALUES)
COLOR_COUNT = sum(CARD_COUNT.values())


@dataclass(frozen=True, slots=True)
class Card:
    color: Color
    value: Value


class Deck(list[Card]):
    @classmethod
    def new(cls):
        deck = [
            Card(color, value)
            for color in COLORS
            for value in VALUES
            for _ in range(CARD_COUNT[value])
        ]
        shuffle(deck)
        return cls(deck)


class HandCard:
    def __init__(self, color: Color, value: Value):
        self.color = color
        self.value = value
        self.is_color_known = False
        self.is_value_known = False
        self.not_colors: list[Color] = []
        self.not_values: list[Value] = []

    def real_name(self) -> str:
        return f"{self.color} {self.value}"

    def known_name(self) -> str:
        data = [
            self.color if self.is_color_known else "",
            str(self.value) if self.is_value_known else "",
        ]
        name = " ".join(data).strip()
        return name or " "

    def to_string(self, show_value: bool) -> str:
        info: list[str] = []
        if self.is_color_known:
            info.append(str(self.color))
        if self.is_value_known:
            info.append(str(self.value))
        if not self.is_color_known:
            info.extend(f"not {color}" for color in self.not_colors)
        if not self.is_value_known:
            info.extend(f"not {value}" for value in self.not_values)

        info_str = "{" + ", ".join(info) + "}"
        if show_value:
            return f"{self.real_name():>8}, {info_str}"
        return info_str

    def give_color_hint(self, color: Color):
        if self.color == color:
            self.is_color_known = True
        elif color not in self.not_colors:
            self.not_colors.append(color)
            if len(self.not_colors) == len(COLORS) - 1:
                self.is_color_known = True

    def give_value_hint(self, value: Value):
        if self.value == value:
            self.is_value_known = True
        elif value not in self.not_values:
            self.not_values.append(value)
            if len(self.not_values) == len(VALUES) - 1:
                self.is_value_known = True


class Hand(list[HandCard]):
    def to_string(self, show_value: bool):
        return "\n".join(
            f"[{i + 1}]: {hand_card.to_string(show_value)}"
            for i, hand_card in enumerate(self)
        )

    def give_color_hint(self, color: Color):
        for card in self:
            card.give_color_hint(color)

    def give_value_hint(self, value: Value):
        for card in self:
            card.give_value_hint(value)


def draw_card(hand: Hand, deck: Deck):
    if not deck:
        return

    card = deck.pop()
    hand_card = HandCard(card.color, card.value)
    hand.insert(0, hand_card)


def new_hand(deck: Deck, num_cards: int) -> Hand:
    assert num_cards in HAND_SIZE.values()
    hand = Hand()
    for _ in range(num_cards):
        draw_card(hand, deck)
    return hand


@dataclass(slots=True)
class Game:
    players: list[Player]
    deck: Deck = field(default_factory=Deck.new)
    errors: int = 0
    hints: int = INITIAL_HINTS
    piles: dict[Color, int] = field(
        default_factory=lambda: {color: 0 for color in COLORS}
    )
    discarded: dict[Color, list[Value]] = field(
        default_factory=lambda: {color: [] for color in COLORS}
    )
    final_moves: int = 0
    active_player: int = 0
    hands: dict[Player, Hand] = field(init=False)
    # TODO: change to game-log
    last_action_description: str = "Game just started"

    def __post_init__(self) -> None:
        num_cards = HAND_SIZE[len(self.players)]
        self.hands = {player: new_hand(self.deck, num_cards) for player in self.players}


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
    in_piles = sum(color_value >= value for _color, color_value in game.piles.items())
    discarded = sum(
        color_discarded.count(value)
        for _color, color_discarded in game.discarded.items()
    )
    seen = hinted + in_piles + discarded
    total = len(COLORS) * CARD_COUNT[value]
    return seen == total


def count_discarded(game: Game, color: Color, value: Value) -> int:
    return game.discarded[color].count(value)


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
    return count_discarded(game, color, value) == CARD_COUNT[value] - 1


def update_not_colors(card: HandCard, color: Color):
    if (
        (card.color != color)
        and (not card.is_color_known)
        and (color not in card.not_colors)
    ):
        card.not_colors.append(color)
        if len(card.not_colors) == len(COLORS) - 1:
            card.not_colors = []
            card.is_color_known = True


def update_not_values(card: HandCard, value: Value):
    if (
        (card.value != value)
        and (not card.is_value_known)
        and (value not in card.not_values)
    ):
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


class GameState(enum.Enum):
    RUNNING = enum.auto()
    MAX_SCORE = enum.auto()
    NO_LIVES = enum.auto()
    TIMEOUT = enum.auto()
    STUCK = enum.auto()


def check_state(game: Game) -> GameState:
    if game.errors == ALLOWED_ERRORS:
        return GameState.NO_LIVES

    if all(p == MAX_VALUE for p in game.piles.values()):
        return GameState.MAX_SCORE

    if len(game.deck) == 0 and game.final_moves == len(game.players):
        return GameState.TIMEOUT

    if all(
        count_discarded(game, color, Value(game.piles[color] + 1))
        == CARD_COUNT[Value(game.piles[color] + 1)]
        for color in COLORS
        if game.piles[color] < MAX_VALUE
    ):
        return GameState.STUCK

    return GameState.RUNNING


def get_active_player_name(game: Game) -> Player:
    return game.players[game.active_player]


def give_hint(game: Game, player: Player, hint: Color | Value) -> bool:
    assert game.hints > 0
    hand = game.hands[player]
    if isinstance(hint, Color):
        hand.give_color_hint(hint)
    elif isinstance(hint, Value):
        hand.give_value_hint(hint)
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
    if " " not in action.strip():
        return False
    name, value = action.strip().split(" ", 1)
    ok = False
    description = player[:] + " "

    aliases = {"h": "hint", "d": "discard", "p": "play"}
    if name in aliases:
        name = aliases[name]

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
        description += hand_card.real_name()
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
        if hand_card.value != MAX_VALUE and is_critical_card(
            game, hand_card.color, hand_card.value
        ):
            description += "critical "
        description += hand_card.real_name()
        errors = game.errors
        ok = play_card(game, player, index)
        if game.errors != errors:
            description = "BOOM! " + description
        elif game.piles[hand_card.color] == MAX_VALUE:
            description = "+ " + description

    elif name == "hint":
        other_player_str, hint = value.split(" ")
        other_player = Player(other_player_str)
        if other_player == player:
            return False
        if other_player not in game.hands:
            return False
        if hint in COLORS:
            ok = give_hint(game, other_player, Color(hint))
        else:
            index, ok = parse_int(hint)
            if not ok:
                return False
            ok = give_hint(game, other_player, Value(index))
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
