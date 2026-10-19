# idea maker : raid of rome 1527
# format :
# top down yes
#
# its been a while since ive done something like this -_-
 
import math
import os
import random
from enum import Enum
 
import pygame
 
Vec = pygame.math.Vector2
 
SCREEN_W, SCREEN_H = 800, 600
SCREEN_CENTER = Vec(SCREEN_W / 2, SCREEN_H / 2)
FPS = 60
VOID_COLOR = (255, 30, 46)
SPRITE_FACING = 0
PLAYER_SIZE = 40
 
# maps and run settings
MAP_DIR = "maps"                  # folder with map art
MAP_MIN, MAP_MAX = -3, 3          # leftmost / rightmost map
REINFORCE_MAPS = (0, -1, -2)
DRAW_FOREGROUND = True            # draw foreground image above player + enemies
BANNER_TIME = 2.0                 # seconds the VICTORY / DEFEAT banner stays up
LOS_STEP = 16                     # pixels between line-of-sight checks
ENEMY_SPAWN_MIN_DIST = 350        # enemies never spawn closer than this to the player
 
BINDS = {"up": pygame.K_w, "down": pygame.K_s, "left": pygame.K_a, "right": pygame.K_d}
 
 
def angle_to(dx, dy):
    return math.degrees(math.atan2(-dy, dx))
 
 
def load_sprite(path, fallback_size, fallback_color):
    if path:
        try:
            return pygame.image.load(path).convert_alpha()
        except (FileNotFoundError, pygame.error):
            pass
    surface = pygame.Surface((fallback_size, fallback_size), pygame.SRCALPHA)
    half = fallback_size // 2
 
    pygame.draw.circle(surface, fallback_color, (half, half), half)
    return surface
 
 
def blit_rotated(target, sprite, angle, center):
    rotated = pygame.transform.rotate(sprite, angle - SPRITE_FACING)
    target.blit(rotated, rotated.get_rect(center=center))
 
 
 
class EnemyLevel(Enum):
    GRUNT = 1
    MINIBOSS = 2
    BOSS = 3
 
 
class EnemyState(Enum):
    IDLE = 0
    CHASE = 1
    ATTACK = 2
    DEAD = 3
 
 
ENEMY_STATS = {
    EnemyLevel.GRUNT:    dict(health=50,  speed=90,  damage=8,  size=36, attack_reach=8,
                              attack_cooldown=1.0, detect_range=350, color=(200, 70, 70)),
    EnemyLevel.MINIBOSS: dict(health=200, speed=110, damage=20, size = 50, attack_reach=12,
                              attack_cooldown=1.2, detect_range=450,  color=(220, 120, 40)),
    EnemyLevel.BOSS:     dict(health=2000, speed=80,  damage=40, size=80, attack_reach=20,
                              attack_cooldown=1.5, detect_range=600, color=(140, 40, 180)),
}
 

DIFFICULTY_STEPS = [0, 1, 2, 2.5]
RATTICUS_MAP = 3

DIFFICULTY_SPAWNS = {
    0:   [(EnemyLevel.GRUNT, 4)],
    1:   [(EnemyLevel.GRUNT, 8)],
    2:   [(EnemyLevel.MINIBOSS, 1), (EnemyLevel.GRUNT, 6)],
    2.5: [(EnemyLevel.MINIBOSS, 2), (EnemyLevel.GRUNT, 8)],
    3:   [(EnemyLevel.MINIBOSS, 3), (EnemyLevel.GRUNT, 10)],
}
 
 
def next_difficulty(difficulty):
    return next((step for step in DIFFICULTY_STEPS if step > difficulty), difficulty)
 


_warned = set()
 
 
def load_image(path, alpha):
    try:
        image = pygame.image.load(path)
        return image.convert_alpha() if alpha else image.convert()
    except (FileNotFoundError, pygame.error):
        if path not in _warned:
            print(f"[maps] couldn't load {path}, using a placeholder")
            _warned.add(path)
        return None
 
 
class World:
 
    def __init__(self, map_index):
        self.map_index = map_index
 
        self.background = load_image(os.path.join(MAP_DIR, f"background_{map_index}.png"), alpha=False)
        if self.background is None:
            self.background = self._placeholder_background()
        self.width, self.height = self.background.get_size()
        self.rect = pygame.Rect(0, 0, self.width, self.height)
 
        self.foreground = load_image(os.path.join(MAP_DIR, f"foreground_{map_index}.png"), alpha=True)
        if self.foreground is None:
            self.foreground = self._placeholder_foreground()
        elif self.foreground.get_size() != self.background.get_size():
            self.foreground = pygame.transform.scale(self.foreground, self.background.get_size())
 
        self.mask = pygame.mask.from_surface(self.foreground)      #reminder: alpha > 127 = solid
        self.debug_overlay = self.mask.to_surface(setcolor=(0, 255, 255, 110), unsetcolor=(0, 0, 0, 0))
        self._box_masks = {}
 
    # --- placeholders before i get to drawing -_-
    def _placeholder_background(self):
        surf = pygame.Surface((1920, 1280))
        for ty in range(20):
            for tx in range(30):
                colour = (196, 178, 140) if (tx + ty) % 2 == 0 else (188, 170, 132)
                pygame.draw.rect(surf, colour, (tx * 64, ty * 64, 64, 64))
        return surf
 
    def _placeholder_foreground(self):
        surf = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        wall = (90, 80, 75, 255)
        pygame.draw.rect(surf, wall, (0, 0, self.width, 64))
        pygame.draw.rect(surf, wall, (0, self.height - 64, self.width, 64))
        pygame.draw.rect(surf, wall, (0, 0, 64, self.height))
        pygame.draw.rect(surf, wall, (self.width - 64, 0, 64, self.height))
        pygame.draw.rect(surf, wall, (600, 400, 128, 128))
        pygame.draw.rect(surf, wall, (1200, 700, 256, 64))
        return surf
 
    def _box_mask(self, w, h):
        if (w, h) not in self._box_masks:
            self._box_masks[(w, h)] = pygame.Mask((w, h), fill=True)
        return self._box_masks[(w, h)]
 
    def hits_wall(self, hitbox):
        if not self.rect.contains(hitbox):
            return True
        return self.mask.overlap(self._box_mask(hitbox.w, hitbox.h), hitbox.topleft) is not None
 
    def is_solid_at(self, x, y):
        ix, iy = math.floor(x), math.floor(y)
        if not (0 <= ix < self.width and 0 <= iy < self.height):
            return True
        return bool(self.mask.get_at((ix, iy)))
 
    @staticmethod
    def _place(hitbox, pos):
        hitbox.center = (round(pos.x), round(pos.y))
 
    def move(self, pos, hitbox, delta):
        for axis in ("x", "y"):
            amount = getattr(delta, axis)
            if not amount:
                continue
            old = getattr(pos, axis)
            setattr(pos, axis, old + amount)
            self._place(hitbox, pos)
            if not self.hits_wall(hitbox):
                continue
 
            # blocked: walk back one pixel at a time until clear
            direction = 1 if amount > 0 else -1
            candidate, start = round(old + amount), round(old)
            blocked = True
            while candidate != start and blocked:
                candidate -= direction
                setattr(pos, axis, candidate)
                self._place(hitbox, pos)
                blocked = self.hits_wall(hitbox)
            if blocked:                                   # no free pixel found
                setattr(pos, axis, old)
                self._place(hitbox, pos)
 
    def line_of_sight(self, a, b):

        diff = b - a
        length = diff.length()
        if length == 0:
            return True
        steps = max(1, int(length // LOS_STEP))
        for i in range(1, steps):
            p = a + diff * (i / steps)
            if self.is_solid_at(p.x, p.y):
                return False
        return True
 
    def find_free_spot(self, size, preferred=None, avoid=None, min_dist=0, occupied=()):

        box = pygame.Rect(0, 0, size, size)
        candidates = [Vec(preferred)] if preferred is not None else []
        candidates += [Vec(random.uniform(size, self.width - size), random.uniform(size, self.height - size))
                       for _ in range(300)]
        for pos in candidates:
            box.center = (round(pos.x), round(pos.y))
            if self.hits_wall(box):
                continue
            if avoid is not None and pos.distance_to(avoid) < min_dist:
                continue
            if any(pos.distance_to(o) < size * 1.5 for o in occupied):
                continue
            return pos
        return Vec(self.width / 2, self.height / 2)
 
    def draw_background(self, screen, cam):
        screen.blit(self.background, (round(-cam.x), round(-cam.y)))
 
    def draw_foreground(self, screen, cam):
        screen.blit(self.foreground, (round(-cam.x), round(-cam.y)))
 
    def draw_hitboxes(self, screen, cam):
        screen.blit(self.debug_overlay, (round(-cam.x), round(-cam.y)))
 
 
class Run:
    def __init__(self):
        self.map_index = 0              # Map index
        self.difficulty = 0             # Difficulty meter
        self.reinforcements = 0         # reinforcement events granted
        self.reinforced_maps = set()    # maps where a loss already gave reinforcements
        self.result = None              # None while playing, then "won" or "lost"
 
    def battle_won(self):
        if self.map_index == MAP_MAX:
            self.result = "won"
            return "RATTICUS IS DOWN", "The raid is won."
        self.map_index += 1
        self.difficulty = next_difficulty(self.difficulty)
        return "VICTORY", f"Advancing to map {self.map_index}"
 
    def battle_lost(self):
        if self.map_index == MAP_MIN:                  # nowhere left to fall back to
            self.result = "lost"
            return "DEFEAT", "The raid is lost."
        note = ""
        if self.map_index in REINFORCE_MAPS and self.map_index not in self.reinforced_maps:
            self.reinforced_maps.add(self.map_index)
            self.reinforcements += 1
            note = f"Reinforcements arrive ({self.reinforcements}/{len(REINFORCE_MAPS)}). "
        self.map_index -= 1
        self.difficulty = max(self.difficulty, abs(self.map_index))
        return "DEFEAT", note + f"Falling back to map {self.map_index}"
 
 
def spawn_enemies(world, player, run):
    plan = list(DIFFICULTY_SPAWNS[run.difficulty])
    if run.map_index == RATTICUS_MAP:
        plan = [(EnemyLevel.BOSS, 1)] + [(lvl, n) for lvl, n in plan if lvl is not EnemyLevel.MINIBOSS]
    enemies, taken = [], []
    for level, count in plan:
        for _ in range(count):
            pos = world.find_free_spot(ENEMY_STATS[level]["size"], avoid=player.pos,
                                       min_dist=ENEMY_SPAWN_MIN_DIST, occupied=taken)
            taken.append(pos)
            enemies.append(Enemy(pos, level))
    return enemies
 
 
def start_battle(run):
    world = World(run.map_index)
    player = Player(world.find_free_spot(PLAYER_SIZE, preferred=(world.width / 2, world.height / 2)))
    return world, player, spawn_enemies(world, player, run)
 
 
def battle_result(player, enemies):
    if not player.is_alive:
        return "lost"
    if not enemies:
        return "won"
    return None
 
 
class Player:
    def __init__(self, position):
        self.pos = Vec(position)
        self.orientation = 0
        self.max_health = 100
        self.health = 100
        self.speed = 180
        self.size = PLAYER_SIZE
        self.radius = self.size / 2
        self.hitbox = pygame.Rect(0, 0, self.size, self.size)
        self.hitbox.center = (round(self.pos.x), round(self.pos.y))
        self.sprite = load_sprite("sprites/player_1.0.png", self.size, (60, 120, 255))
 
    @property
    def is_alive(self):
        return self.health > 0
 
    def face_mouse(self):
        mx, my = pygame.mouse.get_pos()
        self.orientation = angle_to(mx - SCREEN_CENTER.x, my - SCREEN_CENTER.y)
 
    def move(self, keys, dt, world):
        direction = Vec(keys[BINDS["right"]] - keys[BINDS["left"]],
                        keys[BINDS["down"]] - keys[BINDS["up"]])
        if direction.length_squared() > 0:
            world.move(self.pos, self.hitbox, direction.normalize() * self.speed * dt)
 
    def take_damage(self, amount):
        self.health = max(0, self.health - amount)
 
    def draw(self, screen):
        blit_rotated(screen, self.sprite, self.orientation, SCREEN_CENTER)
 
class Enemy:
    def __init__(self, position, level=EnemyLevel.GRUNT, sprite_path=None, **overrides):
        """position : world position (Vec or tuple)
        level       : EnemyLevel.GRUNT / MINIBOSS / BOSS (picks default stats)
        sprite_path : optional image, otherwise a coloured placeholder is used
        overrides   : any stat from ENEMY_STATS, e.g. Enemy(pos, EnemyLevel.BOSS, health=1000)"""
        stats = {**ENEMY_STATS[level], **overrides}
 
        self.level = level
        self.pos = Vec(position)
        self.max_health = stats["health"]
        self.health = self.max_health
        self.speed = stats["speed"]                         # movement speed in pps
        self.damage = stats["damage"]                       # atk
        self.size = stats["size"]
        self.radius = self.size / 2
        self.attack_reach = stats["attack_reach"]           # attack reach
        self.attack_cooldown = stats["attack_cooldown"]     # attack speed
        self.detect_range = stats["detect_range"]
 
        self.state = EnemyState.IDLE
        self.orientation = 0
        self.cooldown_timer = 0.0
        self.hit_flash = 0.0                              # seconds left of the white hit flash
 
        self.hitbox = pygame.Rect(0, 0, self.size, self.size)
        self.hitbox.center = (round(self.pos.x), round(self.pos.y))
        self.sprite = load_sprite(sprite_path, self.size, stats["color"])
 
    @property
    def is_alive(self):
        return self.state is not EnemyState.DEAD
 
    def distance_to(self, other):
        return self.pos.distance_to(other.pos)
 
    def can_see(self, target, world):
        return (self.distance_to(target) <= self.detect_range
                and world.line_of_sight(self.pos, target.pos))
 
    def take_damage(self, amount):
        """Returns True if this hit killed the enemy."""
        if not self.is_alive:
            return False
        self.health -= amount
        self.hit_flash = 0.1
        if self.state is EnemyState.IDLE:
            self.state = EnemyState.CHASE                 # getting shot wakes you up
        if self.health <= 0:
            self.die()
            return True
        return False
 
    def die(self):
        self.health = 0
        self.state = EnemyState.DEAD
        # later: play sound, spawn corpse sprite
 
    def attack(self, target):
        if self.cooldown_timer <= 0:
            target.take_damage(self.damage)
            self.cooldown_timer = self.attack_cooldown
 
    def update(self, dt, player, world, enemies=()):
        if not self.is_alive:
            return
 
        self.cooldown_timer = max(0.0, self.cooldown_timer - dt)
        self.hit_flash = max(0.0, self.hit_flash - dt)
 
        to_player = player.pos - self.pos
        dist = to_player.length()
        touching = dist <= self.radius + player.radius + self.attack_reach
 
        # state transitions
        if self.state is EnemyState.IDLE:
            if self.can_see(player, world):
                self.state = EnemyState.CHASE
        elif self.state is EnemyState.CHASE:
            if touching:
                self.state = EnemyState.ATTACK
            elif dist > self.detect_range * 1.5:          # lost them
                self.state = EnemyState.IDLE
        elif self.state is EnemyState.ATTACK:
            if not touching:
                self.state = EnemyState.CHASE
 
        # state behaviour
        if self.state is not EnemyState.IDLE and dist > 0:
            self.orientation = angle_to(to_player.x, to_player.y)
 
        if self.state is EnemyState.CHASE and dist > 0:
            world.move(self.pos, self.hitbox, to_player.normalize() * self.speed * dt)
        elif self.state is EnemyState.ATTACK:
            self.attack(player)
 
        self._separate(enemies, world)
 
    def _separate(self, enemies, world):
        for other in enemies:
            if other is self or not other.is_alive:
                continue
            offset = self.pos - other.pos
            min_dist = self.radius + other.radius
            d = offset.length()
            if 0 < d < min_dist:
                world.move(self.pos, self.hitbox, offset / d * (min_dist - d) * 0.5)
 
    def draw(self, screen, cam, debug=False):
        if not self.is_alive:
            return
        centre = (round(self.pos.x - cam.x), round(self.pos.y - cam.y))
        margin = max(self.sprite.get_size())
        if not screen.get_rect().inflate(margin * 2, margin * 2).collidepoint(centre):
            return                                        # off screen skip
 
        sprite = self.sprite
        if self.hit_flash > 0:
            sprite = sprite.copy()
            sprite.fill((120, 120, 120, 0), special_flags=pygame.BLEND_RGB_ADD)
        blit_rotated(screen, sprite, self.orientation, centre)
 
        if self.health < self.max_health:                 # health bar
            bar = pygame.Rect(centre[0] - self.size // 2, centre[1] - self.size // 2 - 10, self.size, 5)
            pygame.draw.rect(screen, (40, 40, 40), bar)
            pygame.draw.rect(screen, (60, 220, 80), (bar.x, bar.y, round(bar.w * self.health / self.max_health), bar.h))
 
        if debug:
            pygame.draw.circle(screen, (255, 255, 0), centre, int(self.detect_range), 1)
            pygame.draw.rect(screen, (0, 255, 255), self.hitbox.move(round(-cam.x), round(-cam.y)), 1)
 
 
def draw_text(screen, font, text, pos, colour=(255, 255, 255), center=False):
    image = font.render(text, True, colour)
    rect = image.get_rect(center=pos) if center else image.get_rect(topleft=pos)
    screen.blit(font.render(text, True, (0, 0, 0)), rect.move(2, 2))      # little shadow so it's readable and also cute
    screen.blit(image, rect)
 
 
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("Raidicus of Romicus of 1527 by Ratticus")
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 24)
    big_font = pygame.font.SysFont(None, 72)
    dim = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 160))
 
    run = Run()
    world, player, enemies = start_battle(run)
    state = "playing"                 # playing / paused / banner / ended
    banner = ("", "")
    banner_timer = 0.0
    debug = False
 
    running = True
    while running:
        dt = min(clock.tick(FPS) / 1000, 0.05)
 
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_F1:
                    debug = not debug                    # F1 = show hitboxes
                elif event.key == pygame.K_ESCAPE:
                    if state == "playing":
                        state = "paused"
                    elif state == "paused":
                        state = "playing"
                elif event.key == pygame.K_q and state == "paused":
                    running = False
                elif event.key == pygame.K_r and state in ("paused", "ended"):
                    run = Run()                          # restart the whole run
                    world, player, enemies = start_battle(run)
                    state = "playing"
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and state == "playing":
                # basic bitch combat, sux balls but ill make it cool :) or atleast cooler
                for e in enemies:
                    if e.distance_to(player) < 90:
                        e.take_damage(25)
 
        # update
        if state == "playing":
            player.face_mouse()
            player.move(pygame.key.get_pressed(), dt, world)
            for e in enemies:
                e.update(dt, player, world, enemies)
            enemies = [e for e in enemies if e.is_alive]
 
            result = battle_result(player, enemies)
            if result:
                banner = run.battle_won() if result == "won" else run.battle_lost()
                if run.result:
                    state = "ended"
                else:
                    state, banner_timer = "banner", BANNER_TIME
        elif state == "banner":
            banner_timer -= dt
            if banner_timer <= 0:
                world, player, enemies = start_battle(run)
                state = "playing"
 
        cam = player.pos - SCREEN_CENTER
 
        # draw back to front
        screen.fill(VOID_COLOR)
        world.draw_background(screen, cam)
        for e in enemies:
            e.draw(screen, cam, debug)
        player.draw(screen)
        if DRAW_FOREGROUND:
            world.draw_foreground(screen, cam)
        if debug:
            world.draw_hitboxes(screen, cam)
 
        # hud
        pygame.draw.rect(screen, (40, 40, 40), (10, 10, 200, 16))
        pygame.draw.rect(screen, (220, 50, 50), (10, 10, round(200 * player.health / player.max_health), 16))
        draw_text(screen, font, f"Enemies: {len(enemies)}", (10, 32))
        if debug:
            draw_text(screen, font, f"fps {clock.get_fps():.0f}", (10, 54))
        draw_text(screen, font, f"Map: {run.map_index}   Difficulty: {run.difficulty:g}", (10, SCREEN_H - 52))
        draw_text(screen, font, f"Reinforcements: {run.reinforcements}/{len(REINFORCE_MAPS)}", (10, SCREEN_H - 28))
 
        # overlays
        if state == "paused":
            screen.blit(dim, (0, 0))
            draw_text(screen, big_font, "PAUSED", (SCREEN_W / 2, 190), center=True)
            draw_text(screen, font, f"Map {run.map_index}   Difficulty {run.difficulty:g}   "
                                    f"Reinforcements {run.reinforcements}/{len(REINFORCE_MAPS)}",
                      (SCREEN_W / 2, 250), center=True)
            draw_text(screen, font, "ESC  resume", (SCREEN_W / 2, 310), center=True)
            draw_text(screen, font, "R  restart run", (SCREEN_W / 2, 340), center=True)
            draw_text(screen, font, "Q  quit", (SCREEN_W / 2, 370), center=True)
        elif state in ("banner", "ended"):
            screen.blit(dim, (0, 0))
            draw_text(screen, big_font, banner[0], (SCREEN_W / 2, 240), center=True)
            draw_text(screen, font, banner[1], (SCREEN_W / 2, 300), center=True)
            if state == "ended":
                draw_text(screen, font, "R  restart run", (SCREEN_W / 2, 350), center=True)
 
        pygame.display.flip()
    pygame.quit()
 
 
if __name__ == "__main__":
    main()