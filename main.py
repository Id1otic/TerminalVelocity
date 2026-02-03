# Made by Mason Rustad
# A bullet dodging Game: Terminal Velocity.

import time, keyboard, random, requests
from threading import Thread, Lock
from colorama import init
from getpass import getpass
import qrcode

# Constants
STATE_LOCK = Lock()

PROJECT_ID = "bulletdodgingGame"
API_KEY = "AIzaSyDzGXj5OkOMwKUM-aT_qx_wyrNbV1wyEtQ"

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

# Make sure colors work before using colors.
def colorify(text: str, color: str) -> str:
    """
    Wraps text in ANSI color codes.
    """
    return COLORS[color.upper()] + text + COLORS['RESET']

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

SUPPORT_LINK = "https://buymeacoffee.com/mamaru"

class Game:
    ID_TOKEN: str | None = None
    LOCAL_ID: str | None = None

    field_size: tuple[int, int]
    field: list[list[str]]
    positions: dict[str, tuple[int,int] | list[dict]]
    prev_projectile_cells: set[tuple[int,int]]
    projectile_cells: set[tuple[int,int]]
    game_over: bool
    delay: float
    time_elapsed: float
    leaderboard: list[dict]
    movement_toggle: dict[str, bool]
    m: list[list[bool]]

    def __init__(self):
        if Game.ID_TOKEN is None or Game.LOCAL_ID is None:
            Game.ID_TOKEN, Game.LOCAL_ID = self.anonymous_sign_in()

        self.field_size = (30, 30)
        self.field = [[EMPTY for _ in range(self.field_size[0])] for _ in range(self.field_size[1])]
        
        self.positions = {
            'player': (self.field_size[0]//2-1, self.field_size[1]//2-1),
            'projectiles': []                                         
        }
        self.prev_projectile_cells = set()
        self.projectile_cells = set()

        self.Game_over = False
        self.delay = 0.5
        self.time_elapsed = 0

        self.leaderboard = sorted(
            self.fetch_all_scores(),
            key=lambda x: x["score"],
            reverse=True
        )[:10]

        self.movement_toggle = {i: True for i in "wasd"}

        qr = qrcode.QRCode(border=1, box_size=1)
        qr.add_data(SUPPORT_LINK)
        qr.make()
        self.m = qr.get_matrix()


    def begin_threads_and_wait(self) -> None:
        self.threads = [
            Thread(target=self.player, name="Player"),
            Thread(target=self.projectile, name="Projectile"),
            Thread(target=self.delayer, name="Delayer"),
            Thread(target=self.render_field, name="RenderField"),
        ]

        for i in self.threads:
            i.start()
        for i in self.threads:
            i.join()

    def anonymous_sign_in(self) -> tuple[str, str]:
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
        resp = requests.post(url, json={"returnSecureToken": True})
        data = resp.json()
        
        if "error" in data:
            raise Exception(f"Auth failed: {data['error']}")
        
        id_token = data["idToken"]
        local_id = data["localId"]
        return id_token, local_id
    
    def submit_score(self, username: str, score: float) -> tuple[int, str]:
        """
        Submits score to firestore.
        """
        url = (
            f"https://firestore.googleapis.com/v1/projects/"
            f"{PROJECT_ID}/databases/(default)/documents/leaderboard/{Game.LOCAL_ID}"
            f"?key={API_KEY}"
        )

        payload = {
            "fields": {
                "username": {"stringValue": username},
                "score": {"doubleValue": score},
                "timestamp": {"integerValue": int(time.time())}
            }
        }

        headers = {"Authorization": f"Bearer {Game.ID_TOKEN}"}

        # PATCH creates or overwrites the document for this username
        r = requests.patch(url, json=payload, headers=headers)
        return r.status_code, r.text

    def fetch_all_scores(self) -> list:
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

        r = requests.post(url, json=query)
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
    
    def play(self) -> None:
        print("\033[H\033[2J", end="", flush=True)
        
        self.begin_threads_and_wait()

        print("\033[H", end="", flush=True)
        getpass(f"Game over! Your final time was {self.time_elapsed:.2f} seconds! " + colorify("Press enter to continue...", "green"))

        while True:
            print("\033[H\033[2J", end="", flush=True)
            initials = input("Please input your name to enter the leaderboard (max of 16 characters): ")
            if len(initials) > 16:
                print("Please keep your initials inside of the range..")
            else:
                break
            time.sleep(3)
        if len(initials) != 0:
            status, _ = self.submit_score(initials.upper(), float(f"{self.time_elapsed:.2f}"))
            if status == 200: # 200 = OK
                print("Successfully submitted your score to the leaderboard!")
            else: # Most likely 403 = Forbidden
                print("Error submitting, try again later..")

        self.render_qrcode(self.m, (35, 3), colorify("Enjoying the game? Support me here:", "cyan"))
        
        getpass(colorify("Want to play again? Press enter...", "green"))

    def render_qrcode(self, matrix: list[list[bool]], location: tuple[int, int], message: str) -> None:
        """
        Renders a QRcode from a matrix and prints it onto a screen at a specific location.
        This also includes a message above the code.
        """
        start_x, start_y = location
        print(f"\033[{start_y};{start_x}H", end="")
        print(message)
        print(f"\033[{start_y + 1};{start_x}H", end="") # This is extra and I added it to make sure it is accessable from anywhere.
        print(SUPPORT_LINK)

        for row_idx in range(0, len(matrix), 2):
            row = ""
            print(f"\033[{start_y + row_idx // 2 + 2};{start_x + 2}H", end="")

            for col_idx in range(len(matrix[row_idx])):
                top = matrix[row_idx][col_idx]
                bottom = matrix[row_idx + 1][col_idx] if row_idx + 1 < len(matrix) else False

                row += "█" if top and bottom else "▀" if top else "▄" if bottom else " "

            print(row)

    def render_field(self, seperator: str=" ") -> None:
        """
        Renders the field from the field variable. This also prints data such as delay and time elapsed.
        Also renders the leaderboard.
        """
        while not self.Game_over:
            with STATE_LOCK:
                print("\033[H", end="")
                print(f"Delay: {self.delay:.2f}, Time elapsed: {self.time_elapsed:.2f}")
                
                print('\n'.join(seperator.join(row) for row in self.field))

                print("\033[2;65H", end="")
                print("Leaderboard:")
                for i in range(len(self.leaderboard)):
                    print(f"\033[{3 + i};65H", end="")
                    print(f"{i + 1}.", self.leaderboard[i]['username'], ":", self.leaderboard[i]['score'], "seconds")

            time.sleep(1 / 30)

    def spawn_projectile(self) -> None:
        """
        Spawns a projectile randomly. Decides which border side (top, bottom, etc.) then chooses direction.
        """
        edge = random.choice(['left', 'right', 'top', 'bottom'])

        if edge == 'left':
            x = -1
            y = random.randint(0, self.field_size[1] - 1)
            dx, dy = random.choice([(1, 0), (1, 1), (1, -1)])

        elif edge == 'right':
            x = self.field_size[0]
            y = random.randint(0, self.field_size[1] - 1)
            dx, dy = random.choice([(-1, 0), (-1, 1), (-1, -1)])

        elif edge == 'top':
            x = random.randint(0, self.field_size[0] - 1)
            y = -1
            dx, dy = random.choice([(0, 1), (1, 1), (-1, 1)])

        elif edge == 'bottom':
            x = random.randint(0, self.field_size[0] - 1)
            y = self.field_size[1]
            dx, dy = random.choice([(0, -1), (1, -1), (-1, -1)])

        color = random.choice(COLOR_KEYS)
        while color in ['GREEN', 'RESET', 'LIGHT_GREEN', 'BLACK', 'LIGHT_GRAY', 'DARK_GRAY']:
            color = random.choice(COLOR_KEYS)
        
        self.positions['projectiles'].append({
            'head': (x, y),
            'dir': (dx, dy),
            'length': 3,
            'char': colorify("X", color)
        })

    def update_projectiles(self) -> None:
        self.projectile_cells.clear()
        new_projectiles = []

        for p in self.positions['projectiles']:
            hx, hy = p['head']
            dx, dy = p['dir']
            hx += dx
            hy += dy
            p['head'] = (hx, hy)

            visible = False

            for i in range(p['length']):
                x = hx - dx * i
                y = hy - dy * i
                if 0 <= x < self.field_size[0] and 0 <= y < self.field_size[1]: # If in bounds
                    visible = True
                    self.projectile_cells.add((x, y))
                    self.field[y][x] = p['char']

            if visible:
                new_projectiles.append(p)

        self.positions['projectiles'] = new_projectiles

    # Main logic
    def player(self) -> None:
        """
        Controls player movement, updates time elapsed, and controls if the Game is over or not.
        """
        while not self.Game_over:
            with STATE_LOCK:
                if self.positions['player'] in self.projectile_cells:
                    self.Game_over = True
                    break

                prev_player = self.positions['player']

            # input does NOT need locking
            x, y = prev_player
            for key, (dx, dy) in MOVING_RULES.items():
                pressed = keyboard.is_pressed(key)
                if pressed and self.movement_toggle[key]:
                    x += dx
                    y += dy
                    self.movement_toggle[key] = False
                elif not pressed:
                    self.movement_toggle[key] = True

            # Clamping the player to stay within the field
            x = max(0, min(self.field_size[0] - 1, x))
            y = max(0, min(self.field_size[1] - 1, y))

            with STATE_LOCK:
                self.positions['player'] = (x, y)
                self.field[prev_player[1]][prev_player[0]] = EMPTY
                self.field[y][x] = PLAYER_CHAR

            time.sleep(0.01)
            self.time_elapsed += 0.01

    def projectile(self) -> None:
        """
        Projectile function that spawns it using the other helper functions.
        Also modifies previous and current projectile cells which prevents ghosting.
        """
        while not self.Game_over:
            with STATE_LOCK:
                self.spawn_projectile()

                # erase old projectile cells
                for x, y in self.prev_projectile_cells:
                    if (x, y) != self.positions['player']:
                        self.field[y][x] = EMPTY

                self.update_projectiles()
                self.prev_projectile_cells = self.projectile_cells.copy()

            time.sleep(self.delay)

    def delayer(self) -> None:
        """
        Modifies the delay/speed of projectiles and projectiles' spawn rate.
        """
        while not self.Game_over:
            with STATE_LOCK:
                self.delay *= 0.995
            time.sleep(2)

# Initialize
init() # Colorama, make sure ANSI works.
print("\033[?25l", end="", flush=True) # Hide cursor
print("\033[?1049h", end="", flush=True)

print(TITLE)
print("Please maximize your terminal")
getpass("Press CTRL and + 5 times then enter...")

# Constant loop to reset and play again.
def main() -> None:
    while True:
        g = Game()
        g.play()

if __name__ == "__main__":
    main()
