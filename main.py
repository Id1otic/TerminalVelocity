# Made by Mason Rustad
# A bullet dodging game: Terminal Velocity.

import time, keyboard, random, requests
from threading import Thread, Lock
from colorama import init
from getpass import getpass
import qrcode

# Firestore configuration
PROJECT_ID = "bulletdodginggame"
API_KEY = "".join(["AIzaSyDz", "GXj5OkOMwKUM-", "aT_qx_wyrNbV", "1wyEtQ"])


def submit_score(username, score):
    """
    Submits score to firestore.
    """
    url = (
        f"https://firestore.googleapis.com/v1/projects/"
        f"{PROJECT_ID}/databases/(default)/documents/leaderboard/{username}"
        f"?key={API_KEY}"
    )

    payload = {
        "fields": {
            "username": {"stringValue": username},
            "score": {"doubleValue": float(score)},
            "timestamp": {"integerValue": int(time.time())}
        }
    }

    # PATCH creates or overwrites the document for this username
    r = requests.patch(url, json=payload)
    return r.status_code, r.text

def fetch_all_scores():
    """
    Fetches all firestore items.
    """
    url = (
        f"https://firestore.googleapis.com/v1/projects/"
        f"{PROJECT_ID}/databases/(default)/documents:runQuery"
        f"?key={API_KEY}"
    )

    query = {
        "structuredQuery": {
            "from": [{"collectionId": "leaderboard"}]
        }
    }

    r = requests.patch(url, json=query)
    results = []

    for item in r.json():
        if "document" in item:
            f = item["document"]["fields"]
            results.append({
                "username": f["username"]["stringValue"],
                "score": float(f["score"]["doubleValue"]),
                "timestamp": int(f["timestamp"]["integerValue"])
            })

    return results

# Variables
leaderboard_data = sorted(fetch_all_scores(), key=lambda x: x["score"], reverse=True)[:10]

field = []

EMPTY = '·'
COLORS = {
    'BLACK': '\033[0;30m',
    'RED': '\033[0;31m',
    'GREEN': '\033[0;32m',
    'BROWN': '\033[0;33m',
    'BLUE': '\033[0;34m',
    'PURPLE': '\033[0;35m',
    'CYAN': '\033[0;36m',
    'LIGHT_GRAY': '\033[0;37m',
    'DARK_GRAY': '\033[1;30m',
    'LIGHT_RED': '\033[1;31m',
    'LIGHT_GREEN': '\033[1;32m',
    'YELLOW': '\033[1;33m',
    'LIGHT_BLUE': '\033[1;34m',
    'LIGHT_PURPLE': '\033[1;35m',
    'LIGHT_CYAN': '\033[1;36m',
    'RESET': '\033[0m',
}
COLOR_KEYS = tuple(COLORS)

# Mini function
def colorify(text: str, color: str) -> str:
    """
    Wraps text in ANSI color codes.
    """
    return COLORS[color.upper()] + text + COLORS['RESET']

# More variables
prev_projectile_cells = set()
projectile_cells = set()

delay = 0.5
time_elapsed = 0
toggle = {i: True for i in "wasd"}
MOVING_RULES = {
    'w': (0, -1),
    's': (0, 1),
    'a': (-1, 0),
    'd': (1, 0),
    'up': (0, -1),
    'down': (0, 1),
    'left': (-1, 0),
    'right': (1, 0),
}
PLAYER_CHAR = colorify("☺", "green")

game_over = False

field_size = (30, 30)
positions = {
    'player': (field_size[0]//2-1, field_size[1]//2-1),
    'projectiles': []                                         
}

TITLE = colorify("""
                                        d8,                     d8b
   d8P                                 `8P                      88P
d888888P                                                       d88
  ?88'   d8888b  88bd88b  88bd8b,d88b   88b  88bd88b  d888b8b  888
  88P   d8b_,dP  88P'  `  88P'`?8P'?8b  88P  88P' ?8bd8P' ?88  ?88
  88b   88b     d88      d88  d88  88P d88  d88   88P88b  ,88b  88b
  `?8b  `?888P'd88'     d88' d88'  88bd88' d88'   88b`?88P'`88b  88b
""", "red") + colorify("""
                 d8b                  d8,
                 88P                 `8P    d8P
                d88                      d888888P
?88   d8P d8888b888   d8888b  d8888b  88b  ?88'  ?88   d8P
d88  d8P'd8b_,dP?88  d8P' ?88d8P' `P  88P  88P   d88   88
?8b ,88' 88b     88b 88b  d8888b     d88   88b   ?8(  d88
`?888P'  `?888P'  88b`?8888P'`?888P'd88'   `?8b  `?88P'?8b
                                                        )88
                                                       ,d8P
                                                    `?888P'""", "green")

support_link = "https://buymeacoffee.com/mamaru"

state_lock = Lock()

# Initialize
init() # Colorama, make sure ANSI works.
print("\033[?25l", end="", flush=True) # Hide cursor
print("\033[?1049h", end="", flush=True)

qr = qrcode.QRCode(border=1, box_size=1)
qr.add_data(support_link)
qr.make()
m = qr.get_matrix()

print(TITLE)
print("Please maximize your terminal")
getpass("Press CTRL and + 5 times then enter...")

# Functions
def play():
    """
    Controls/calls everything. Resets/wipes/cleans variables when called. Allows for repeats.
    """
    global leaderboard_data, field, field_size, projectile_cells, delay, time_elapsed, game_over, positions
    print("\033[H\033[2J", end="", flush=True)

    leaderboard_data = sorted(fetch_all_scores(), key=lambda x: x["score"], reverse=True)[:10]

    # Resets the field
    field = []
    for i in range(field_size[1]):
            field.append([])
            for _ in range(field_size[0]):
                field[i].append(EMPTY)

    # Variables
    field_size = (30, 30)

    projectile_cells = set()

    delay = 0.5
    time_elapsed = 0

    game_over = False

    positions = {
        'player': (field_size[0]//2-1, field_size[1]//2-1),
        'projectiles': []                                         
    }

    t1 = Thread(target=player)
    t2 = Thread(target=projectile)
    t3 = Thread(target=delayer)
    t4 = Thread(target=render_field)

    t1.start()
    t2.start()
    t3.start()
    t4.start()

    t1.join()
    t2.join()
    t3.join()
    t4.join()

    print("\033[H", end="", flush=True)
    getpass(f"Game over! Your final time was {time_elapsed:.2f} seconds! " + colorify("Press enter to continue...", "green"))

    while True:
        print("\033[H\033[2J", end="", flush=True)
        initials = input("Please input your name to enter the leaderboard (max of 16 characters): ")
        if len(initials) > 16:
            print("Please keep your initials inside of the range..")
        else:
            break
        time.sleep(3)
    if len(initials) != 0:
        status, _ = submit_score(initials.upper(), f"{time_elapsed:.2f}")
        if status == 200: # 200 = OK
            print("Successfully submitted your score to the leaderboard!")
        else: # Most likely 403 = Forbidden
            print("Error submitting, try again later..")

    render_qrcode(m, (35, 3), colorify("Enjoying the game? Support me here:", "cyan"))
    
    getpass(colorify("Want to play again? Press enter...", "green"))

def render_qrcode(matrix, location: tuple[int, int], message: str):
    """
    Renders a QRcode from a matrix and prints it onto a screen at a specific location.
    This also includes a message above the code.
    """
    start_x, start_y = location
    print(f"\033[{start_y};{start_x}H", end="")
    print(message)
    print(f"\033[{start_y + 1};{start_x}H", end="") # This is extra and I added it to make sure it is accessable from anywhere.
    print(support_link)

    for row_idx in range(0, len(m), 2):
        row = ""
        print(f"\033[{start_y + row_idx // 2 + 2};{start_x + 2}H", end="")

        for col_idx in range(len(m[row_idx])):
            top = matrix[row_idx][col_idx]
            bottom = matrix[row_idx + 1][col_idx] if row_idx + 1 < len(matrix) else False

            row += "█" if top and bottom else "▀" if top else "▄" if bottom else " "

        print(row)

def render_field(seperator=" "):
    """
    Renders the field from the field variable. This also prints data such as delay and time elapsed.
    Also renders the leaderboard.
    """
    while not game_over:
        with state_lock:
            print("\033[H", end="")
            print(f"Delay: {delay:.2f}, Time elapsed: {time_elapsed:.2f}")
            
            print('\n'.join(seperator.join(row) for row in field))

            print("\033[2;65H", end="")
            print("Leaderboard:")
            for i in range(len(leaderboard_data)):
                print(f"\033[{3 + i};65H", end="")
                print(f"{i + 1}.", leaderboard_data[i]['username'], ":", leaderboard_data[i]['score'], "seconds")

        time.sleep(1 / 30)

def spawn_projectile():
    """
    Spawns a projectile randomly. Decides which border side (top, bottom, etc.) then chooses direction.
    """
    edge = random.choice(['left', 'right', 'top', 'bottom'])

    if edge == 'left':
        x = -1
        y = random.randint(0, field_size[1] - 1)
        dx, dy = random.choice([(1, 0), (1, 1), (1, -1)])

    elif edge == 'right':
        x = field_size[0]
        y = random.randint(0, field_size[1] - 1)
        dx, dy = random.choice([(-1, 0), (-1, 1), (-1, -1)])

    elif edge == 'top':
        x = random.randint(0, field_size[0] - 1)
        y = -1
        dx, dy = random.choice([(0, 1), (1, 1), (-1, 1)])

    elif edge == 'bottom':
        x = random.randint(0, field_size[0] - 1)
        y = field_size[1]
        dx, dy = random.choice([(0, -1), (1, -1), (-1, -1)])

    color = random.choice(COLOR_KEYS)
    while color in ['GREEN', 'RESET', 'LIGHT_GREEN', 'BLACK', 'LIGHT_GRAY', 'DARK_GRAY']:
        color = random.choice(COLOR_KEYS)
    
    positions['projectiles'].append({
        'head': (x, y),
        'dir': (dx, dy),
        'length': 3,
        'char': colorify("X", color)
    })

def update_projectiles():
    projectile_cells.clear()
    new_projectiles = []

    for p in positions['projectiles']:
        hx, hy = p['head']
        dx, dy = p['dir']
        hx += dx
        hy += dy
        p['head'] = (hx, hy)

        visible = False

        for i in range(p['length']):
            x = hx - dx * i
            y = hy - dy * i
            if in_bounds(x, y):
                visible = True
                projectile_cells.add((x, y))
                field[y][x] = p['char']

        if visible:
            new_projectiles.append(p)

    positions['projectiles'] = new_projectiles

def in_bounds(x, y):
    """Mini helper function that checks if a coordinate is inside another (the field)."""
    return 0 <= x < field_size[0] and 0 <= y < field_size[1]

# Main logic
def player():
    """
    Controls player movement, updates time elapsed, and controls if the game is over or not.
    """
    global time_elapsed, game_over

    while not game_over:
        with state_lock:
            if positions['player'] in projectile_cells:
                game_over = True
                break

            prev_player = positions['player']

        # input does NOT need locking
        x, y = prev_player
        for key, (dx, dy) in MOVING_RULES.items():
            pressed = keyboard.is_pressed(key)
            if pressed and toggle[key]:
                x += dx
                y += dy
                toggle[key] = False
            elif not pressed:
                toggle[key] = True

        # Clamping the player to stay within the field
        x = max(0, min(field_size[0] - 1, x))
        y = max(0, min(field_size[1] - 1, y))

        with state_lock:
            positions['player'] = (x, y)
            field[prev_player[1]][prev_player[0]] = EMPTY
            field[y][x] = PLAYER_CHAR

        time.sleep(0.01)
        time_elapsed += 0.01

def projectile():
    """
    Projectile function that spawns it using the other helper functions.
    Also modifies previous and current projectile cells which prevents ghosting.
    """
    global prev_projectile_cells

    while not game_over:
        with state_lock:
            spawn_projectile()

            # erase old projectile cells
            for x, y in prev_projectile_cells:
                if (x, y) != positions['player']:
                    field[y][x] = EMPTY

            update_projectiles()
            prev_projectile_cells = projectile_cells.copy()

        time.sleep(delay)

def delayer():
    """
    Modifies the delay/speed of projectiles and projectiles' spawn rate.
    """
    global delay
    while not game_over:
        with state_lock:
            delay *= 0.995
        time.sleep(2)

# Constant loop to reset and play again.
while True:
    play()

