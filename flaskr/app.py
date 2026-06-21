import random

#DBの設計　よくわかんない
#10Rごとの成功率
#累計で苦手なナンバーを出す。

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
    






# git add .
# git commit -m "update"
# git pushgit add .


# このコマンドでgithubに送れる