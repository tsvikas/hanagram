import sys

from hanabi.hanabi import (
    COLORS,
    Game,
    GameState,
    Player,
    check_state,
    get_score,
    perform_action,
)


def print_board_state(game: Game, seen_from: Player | None = None):
    for player in game.players:
        print()
        print(f"{player}'s hand:")
        print(game.hands[player].to_string(player != seen_from))
        print()

    for color in COLORS:
        print(
            f"{color:6}: {game.piles[color]}  {[int(v) for v in game.discarded[color]]}"
        )
    print()

    score = get_score(game)
    print(f"hints: {game.hints}, errors: {game.errors}")
    print(f"score: {score}, deck: {len(game.deck)}")
    print()


def play_repl(player_names: list[str], output_fn=print_board_state):
    players = [Player(s) for s in player_names]
    print(players)
    game = Game(players)

    while True:
        output_fn(game, game.players[game.active_player])

        result = check_state(game)
        if result is GameState.MAX_SCORE:
            print("*** You won! ***")
            break
        elif result is not GameState.RUNNING:
            print("*** You lost! ***")
            break

        ok = False
        while not ok:
            action = input(players[game.active_player] + ": ")
            ok = perform_action(game, players[game.active_player], action)
            if ok:
                print()
                print("-" * len(game.last_action_description))
                print(game.last_action_description)
                print("-" * len(game.last_action_description))
            else:
                print("Usage:")
                print("discard <SLOT>")
                print("play <SLOT>")
                print("hint <PLAYER> <COLOR>")
                print("hint <PLAYER> <VALUE>")


def main():
    try:
        play_repl(sys.argv[1:])
    except EOFError:
        sys.exit(1)
