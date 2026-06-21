import random

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
