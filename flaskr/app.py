import random

def draw_number():
    number = random.randint(1, 21)
    if number == 21:
        return "bull"
    else:
        return number
    

def draw_Advanced_numbers():
    number = random.randint(1, 21)

    if number == 21:
        position = random.choice(["Outer", "Inner"])
        number = "bull"
        return number, position
    else:
        bed = random.choice(["Single", "Double", "Triple"])
        return number, bed



