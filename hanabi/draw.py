import io

from PIL import Image, ImageDraw, ImageFont

from . import hanabi


def rounded_rectangle(
    image: ImageDraw,
    xy: tuple[tuple[float, float], tuple[float, float]],
    corner_radius: float,
    fill: tuple[int, int, int],
):
    r = corner_radius
    up, left = xy[0]
    bottom, right = xy[1]
    color = dict(fill=fill, outline=None)
    image.rectangle([(up, left + r), (bottom, right - r)], **color)
    image.rectangle([(up + r, left), (bottom - r, right)], **color)
    image.pieslice([(up, left), (up + r * 2, left + r * 2)], 180, 270, **color)
    image.pieslice([(bottom - r * 2, right - r * 2), (bottom, right)], 0, 90, **color)
    image.pieslice([(up, right - r * 2), (up + r * 2, right)], 90, 180, **color)
    image.pieslice([(bottom - r * 2, left), (bottom, left + r * 2)], 270, 360, **color)


size = 1
card_font = ImageFont.truetype("assets/Avenir.ttc", 50 * size)
text_font = ImageFont.truetype("assets/Avenir.ttc", 20 * size)
text_font_discarded = ImageFont.truetype("assets/Avenir.ttc", 15 * size)
text_font_small = ImageFont.truetype("assets/Avenir.ttc", 10 * size)

colors_rbg = {
    "red": (230, 20, 20),
    "green": (50, 150, 50),
    "blue": (50, 100, 250),
    "yellow": (250, 200, 0),
    "white": (230, 230, 230),
    "grey": (100, 100, 100),
}


def render_card(image: ImageDraw, x: float, y: float, color: str, value: str):
    width = 50 * size
    rounded_rectangle(
        image, ((x, y), (x + width, y + width * 1.3)), width / 7, fill=colors_rbg[color]
    )
    text_fill = (0, 0, 0)
    image.text((x + width / 4, y), value, font=card_font, fill=text_fill)


def render_card_friend(image: ImageDraw, x: float, y: float, color: str, value: str):
    width = 50 * size
    height = 30 * size
    rounded_rectangle(
        image, ((x, y), (x + width, y + height)), width / 10, fill=colors_rbg[color]
    )
    text_fill = (0, 0, 0)
    image.text((x + width / 2.5, y + height / 8), value, font=text_font, fill=text_fill)


def draw_board_state(
    game: hanabi.Game,
    player_viewing: hanabi.Player | None,
    background: tuple[int, int, int] = (20, 20, 20),
) -> io.BytesIO:
    width = 400 * size
    height = (width * 16) // 9
    if len(game.players) > 3:
        height += 140 * (len(game.players) - 3) * size
        height += -50 * size

    image = Image.new("RGB", (width, height), background)
    draw = ImageDraw.Draw(image)
    text_fill = (200, 200, 200)

    # counters
    x = 20 * size
    draw.text(
        (x, 25 * size), "Hints: " + str(game.hints), font=text_font, fill=text_fill
    )
    draw.text(
        (x + (100 - 15) * size, 25 * size),
        f"Errors: {game.errors}/{hanabi.ALLOWED_ERRORS}",
        font=text_font,
        fill=text_fill,
    )
    draw.text(
        (x + (200 - 5) * size, 25 * size),
        "Deck: " + str(len(game.deck)),
        font=text_font,
        fill=text_fill,
    )
    draw.text(
        (x + (300 - 10) * size, 25 * size),
        "Score: " + str(hanabi.get_score(game)),
        font=text_font,
        fill=text_fill,
    )

    # piles
    left_margin = 35 * size
    x = left_margin
    y = 65 * size
    for color in hanabi.COLORS:
        value = game.piles[color]
        value = "" if value == 0 else str(value)
        render_card(draw, x, y, color, value)
        xx = x
        yy = y
        for i, discarded in enumerate(sorted(game.discarded[color])):
            draw.text(
                (xx, yy + 70 * size),
                str(discarded),
                font=text_font_discarded,
                fill=(255, 255, 255),
            )
            xx += 10 * size
            if i == 4:
                yy += 18 * size
                xx = x
        x += 70 * size

    # hands
    for player in game.players:
        x = left_margin
        y += 110 * size
        draw.text((x, y), player, font=text_font, fill=text_fill)

        # current player marker
        if player == game.players[game.active_player]:
            draw.ellipse(
                (x - 20 * size, y + 8 * size, x - 10 * size, y + 18 * size),
                fill=(255, 255, 255),
            )

        y += 30 * size
        for card in game.hands[player]:
            # big card with full info for other players, known info for current player
            color = card.color
            value = str(card.value)
            if player == player_viewing:
                if not card.is_color_known:
                    color = "grey"
                if not card.is_value_known:
                    value = ""
            render_card(draw, x, y, color, value)

            # for current player, fill big card with negative info
            if player_viewing == player:
                yy = y + 0 * size
                xx = x + 5 * size

                if not card.is_color_known:
                    for not_color in card.not_colors:
                        start = (xx, yy + 2 * size)
                        radius = 10 * size
                        draw.ellipse(
                            (start[0], start[1], start[0] + radius, start[1] + radius),
                            fill=background,
                        )
                        start = (start[0] + 2 * size, start[1] + 2 * size)
                        radius = 6 * size
                        draw.ellipse(
                            (start[0], start[1], start[0] + radius, start[1] + radius),
                            fill=colors_rbg[not_color],
                        )
                        xx += 15 * size

                xx = x + 5 * size
                yy = y + 50 * size
                if not card.is_value_known:
                    for not_value in card.not_values:
                        start = (xx - 1 * size, yy)
                        radius = 12 * size
                        draw.ellipse(
                            (start[0], start[1], start[0] + radius, start[1] + radius),
                            fill=background,
                        )
                        draw.text(
                            (xx + 5, yy),
                            str(not_value),
                            font=text_font_small,
                            fill=text_fill,
                        )
                        xx += 15 * size

            # for other players, add a small card below with their info
            yy = y + 70 * size
            xx = x + 5 * size
            if player_viewing != player:
                # positive info
                if not card.is_color_known:
                    color = "grey"
                if not card.is_value_known:
                    value = ""
                render_card_friend(draw, x, yy, color, str(value))

                # negative info
                if not card.is_color_known:
                    for not_color in card.not_colors:
                        start = (xx, yy + 2 * size)
                        radius = 7 * size
                        draw.ellipse(
                            (start[0], start[1], start[0] + radius, start[1] + radius),
                            fill=background,
                        )
                        start = (start[0] + 1 * size, start[1] + 1 * size)
                        radius = 5 * size
                        draw.ellipse(
                            (start[0], start[1], start[0] + radius, start[1] + radius),
                            fill=colors_rbg[not_color],
                        )
                        xx += 25

                xx = x + 5 * size
                yy += 15 * size
                if not card.is_value_known:
                    for not_value in card.not_values:
                        start = (xx - 3.5 * size, yy)
                        radius = 12 * size
                        draw.ellipse(
                            (start[0], start[1], start[0] + radius, start[1] + radius),
                            fill=background,
                        )
                        draw.text(
                            (xx, yy),
                            str(not_value),
                            font=text_font_small,
                            fill=text_fill,
                        )
                        xx += 15 * size

            x += 70 * size

        if player_viewing == player:
            y -= 30 * size

    x = left_margin
    y = height
    if len(game.players) < 4:
        y -= 50 * size
    else:
        y -= 40 * size
    draw.text((x, y), game.last_action_description, font=text_font, fill=text_fill)
    # last player
    x = left_margin
    y -= 30 * size
    last = (
        "" if game.deck else f"{len(game.players) - game.final_moves} turns until end"
    )
    last = "Game ended" if last.startswith("0") else last
    draw.text((x, y), last, font=text_font, fill=text_fill)
    # to image
    image_file = io.BytesIO()
    image.save(image_file, "webp")
    image_file.seek(0)
    return image_file


def main():
    players = [hanabi.Player(s) for s in ["Giacomo", "Gabriele", "Fabrizio"]]
    player1 = players[0]
    game = hanabi.Game(players)
    hanabi.perform_action(game, player1, "hint Gabriele yellow")
    # hanabi.give_hint(game, player1, hanabi.Color('red'))
    # hanabi.give_hint(game, player1, hanabi.Color('blue'))
    # hanabi.give_hint(game, player1, hanabi.Color('white'))
    # hanabi.give_hint(game, player1, hanabi.Color('yellow'))
    # hanabi.give_hint(game, player1, hanabi.Value(1))
    # hanabi.give_hint(game, player1, hanabi.Value(2))
    # hanabi.give_hint(game, player1, hanabi.Value(3))
    game.discarded[hanabi.Color("red")] = [
        hanabi.Value(v) for v in [5, 2, 1, 1, 3, 3, 2]
    ]
    # game.hands[player1][0].is_value_known = True
    # game.hands[player1][0].not_values = [hanabi.Value(v) for v in [1, 2, 3]]
    # game.hands[player1][0].not_colors = [hanabi.Color(c) for c in ['red', 'blue', 'green']]
    image = draw_board_state(game, player1)
    with open("image.png", "wb") as f:
        f.write(image.read())


if __name__ == "__main__":
    main()
