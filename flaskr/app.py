import random

CRICKET_NUMBERS = [15, 16, 17, 18, 19, 20, 'bull']

def draw_number():
    number = random.randint(1, 21)
    if number == 21:
        return "bull"
    return number


def draw_advanced_numbers():
    number = random.randint(1, 21)

    if number == 21:
        position = random.choice(["Outer", "Inner"])
        return "bull", position

    bed = random.choice(["Single", "Double", "Triple"])
    return number, bed


def draw_cricket_number():
    return random.choice(CRICKET_NUMBERS)
