"""
TODO
- Cell categories
- More cells
- Pause menu for saving, loading, customizing grid, etc.
"""

VERSION = "1.0"

import pygame
import os
import math

# Load textures
textures = {}
if not os.path.exists("textures"):
    os.makedirs("textures")

with open("textures/texture_names.txt") as f:
    # Notation:
    # tex_name file_name
    for line in f.readlines():
        line = line.split("#")[0]
        if not line.strip(): continue
        parts = line.strip().split()
        tex_name, file_name = parts[0], parts[1]
        textures[tex_name] = pygame.image.load(f"textures\\{file_name}")

# Vector class
class Vector:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __add__(self, other):
        return Vector(self[0] + other[0], self[1] + other[1])
    
    def __sub__(self, other):
        return Vector(self[0] - other[0], self[1] - other[1])
    
    def __mul__(self, other):
        return Vector(self[0] * other, self[1] * other)
    
    def __pow__(self, other):
        return Vector(self[0] * other[0], self[1] * other[1])
    
    def rotcw(self):
        return Vector(-self[1], self[0])
    
    def rotccw(self):
        return Vector(self[1], -self[0])  
    
    def rot180(self):
        return Vector(-self[0], -self[1])
    
    def tuple(self):
        return (self.x, self.y)

    def __getitem__(self, index):
        return (self.x, self.y)[index]

    def __str__(self):
        return f"<X: {self.x}, Y: {self.y}>"
    
    def __eq__(self, other):
        if not isinstance(other, Vector):
            return NotImplemented
        return self.x == other.x and self.y == other.y
    
    def __class_getitem__(cls, _):
        return cls

# Sample vectors
UP = Vector(0, -1)
DOWN = Vector(0, 1)
LEFT = Vector(-1, 0)
RIGHT = Vector(1, 0)

# Grid class (immutable)
class Grid:
    range = ((-50, 50), (-50, 50))
    cells = []
    state_stack = []

    def getCellAt(pos):
        candidates = [c for c in Grid.cells if c.pos == pos]
        if candidates: return candidates[0]
        return None

    def isInBounds(point):
        x, y = point
        (xmin, xmax), (ymin, ymax) = Grid.range
        return (
            (xmin is None or x >= xmin) and
            (xmax is None or x <= xmax) and
            (ymin is None or y >= ymin) and
            (ymax is None or y <= ymax)
        )
    
    def clear_all():
        for c in Grid.cells:
            c.destroy(silent = True)

    def save_state():
        saved = []
        for c in Grid.cells:
            saved.append({
                "type": Cell.subclasses.index(c.__class__),
                "x": c.pos.x,
                "y": c.pos.y,
                "dir": [RIGHT, DOWN, LEFT, UP].index(c.dir)
            })
        return saved
    
    def load_state(state):
        Grid.clear_all()
        for item in state:
            cell_class = Cell.subclasses[item["type"]]
            pos = Vector(item["x"], item["y"])
            dir_vec = [RIGHT, DOWN, LEFT, UP][item["dir"]]
            cell_class(pos, dir_vec)

    def push_state():
        Grid.state_stack.append(Grid.save_state())
    
    def pop_state():
        Grid.load_state(Grid.state_stack.pop())

# Helpers
def rotate_by_dir(dir):
    global RIGHT, LEFT, UP, DOWN
    match dir:
        case _ if dir == RIGHT:
            return 0
        case _ if dir == LEFT:
            return 180
        case _ if dir == UP:
            return 90
        case _ if dir == DOWN:
            return 270
        case _:
            return 0

def shortest_angle(a, b):
    diff = (b - a + 180) % 360 - 180
    return a + diff

TICK_RATE = 10 # cells per second

# Main cell class
class Cell:
    pos: Vector[int]
    dir: Vector[int]
    vel: Vector[int]
    anim_from: Vector[int]
    anim_to: Vector[int]
    anim_t: float
    render_rot: float
    target_rot: float

    max_priority = 0

    def __init__(self, pos, dir):
        self.pos = pos
        self.dir = dir
        self.vel = Vector(0, 0)
        self.anim_from = pos
        self.anim_to = pos
        self.anim_t = 1.0
        self.render_rot = rotate_by_dir(dir)
        self.target_rot = self.render_rot
        Grid.cells.append(self)
    
    subclasses = []
    def __init_subclass__(cls):
        Cell.subclasses.append(cls)
        if Cell.max_priority < cls.get_priority(None):
            Cell.max_priority = cls.get_priority(None)
    
    def shallow_copy(self):
        print(self, "copied")
        new = self.__class__(self.pos, self.dir)
        new.vel = self.vel
        new.anim_from = self.anim_from
        new.anim_to = self.anim_to
        new.anim_t = self.anim_t
        new.render_rot = self.render_rot
        new.target_rot = self.target_rot
        return new
    
    def futurePos(self):
        new = self.pos + self.vel
        if Grid.getCellAt(new) is not None: return
        if not Grid.isInBounds(new): return
        return new

    def move(self, vel = None):
        vel = vel or self.vel
        self.vel = Vector(0, 0)

        if vel == Vector(0, 0): return
        
        self.finish_animation()
        
        self.vel = Vector(0, 0)
        new = self.pos + vel
        if (cell_in_front := Grid.getCellAt(new)) is not None:
            cell_in_front.apply_force(vel, self)
            if Grid.getCellAt(new) is not None: return
            
        if not Grid.isInBounds(new): return
        
        if self.anim_from == self.anim_to: self.anim_from = self.pos
        self.anim_to = new
        self.anim_rot_to = rotate_by_dir(self.dir)

        self.anim_t = 0.0

        self.pos = new
    
    def destroy(self, silent = False):
        if not silent: print("Destroyed", self)
        if self in Grid.cells: Grid.cells.remove(self)
        del self
    
    def __str__(self):
        return f"{self.get_label()} at {self.pos} facing {self.dir}"
    
    def can_move(self, force, visited=None):
        if visited is None:
            visited = set()

        if id(self) in visited:
            return False

        visited.add(id(self))

        next_pos = self.pos + force

        if not Grid.isInBounds(next_pos):
            return False

        cell = Grid.getCellAt(next_pos)
        if cell is None:
            return True

        return cell.can_move(force, visited)
    
    def rotate(self, new_dir):
        self.dir = new_dir
        self.target_rot = rotate_by_dir(new_dir)

    def update_animation(self, dt):
        # position animation
        if self.anim_t < 1.0:
            self.anim_t += TICK_RATE * dt
            if self.anim_t > 1.0:
                self.anim_t = 1.0

        # rotation animation
        ROTATE_SPEED = 200
        diff = (self.target_rot - self.render_rot + 180) % 360 - 180
        step = ROTATE_SPEED * dt * TICK_RATE

        if abs(diff) <= step:
            self.render_rot = self.target_rot
        else:
            self.render_rot += step if diff > 0 else -step
    
    def finish_animation(self):
        if self.anim_t < 1.0:
            t = self.anim_t
            self.anim_from = Vector(
                self.anim_from.x + (self.anim_to.x - self.anim_from.x) * t,
                self.anim_from.y + (self.anim_to.y - self.anim_from.y) * t,
            )

        self.anim_to = self.anim_from
        self.anim_t = 1.0
    
    def get_render_pos(self):
        t = self.anim_t
        return Vector(
            self.anim_from.x + (self.anim_to.x - self.anim_from.x) * t,
            self.anim_from.y + (self.anim_to.y - self.anim_from.y) * t,
        )
    
    # These are all to be set by subclasses
    def get_label(self): pass
    def get_desc(self): pass
    def get_image(self): pass
    def get_priority(self): pass
    def tick(self): pass
    def apply_force(self, force, cell=None):
        if force == Vector(0, 0):
            return
        if not self.can_move(force):
            return
        self.move(force)

class Wall(Cell):
    def get_label(self): return "Wall"
    def get_desc(self): return "Cannot be moved"
    def get_image(self): return "cell_wall"
    def get_priority(self): return 0
    def apply_force(self, force, cell=None): pass

class Mover(Cell):
    def get_label(self): return "Mover"
    def get_desc(self): return "Moves forward over time"
    def get_image(self): return "cell_mover"
    def get_priority(self): return 3
    def tick(self):
        if (cellInFront := Grid.getCellAt(self.pos + self.dir)) is not None:
            cellInFront.apply_force(self.dir, self)
        self.vel += self.dir

class Generator(Cell):
    def get_label(self): return "Generator"
    def get_desc(self): return "Generates the cell behind it in front of it"
    def get_image(self): return "cell_generator"
    def get_priority(self): return 1

    def tick(self):
        back_pos = self.pos - self.dir

        source = Grid.getCellAt(back_pos)
        if source is None:
            return

        new_cell = source.shallow_copy()
        new_cell.pos = self.pos
        new_cell.apply_force(self.dir)

        if new_cell.pos == self.pos:
            new_cell.destroy()

class RotatorCW(Cell):
    def get_label(self): return "Rotator (clockwise)"
    def get_desc(self): return "Rotates adjacent cells clockwise 90 degrees"
    def get_image(self): return "cell_rotatorcw"
    def get_priority(self): return 2
    def tick(self):
        if (cellU := Grid.getCellAt(self.pos + UP)) is not None:
            cellU.rotate(cellU.dir.rotcw())
        if (cellD := Grid.getCellAt(self.pos + DOWN)) is not None:
            cellD.rotate(cellD.dir.rotcw())
        if (cellL := Grid.getCellAt(self.pos + LEFT)) is not None:
            cellL.rotate(cellL.dir.rotcw())
        if (cellR := Grid.getCellAt(self.pos + RIGHT)) is not None:
            cellR.rotate(cellR.dir.rotcw())

class RotatorCCW(Cell):
    def get_label(self): return "Rotator (counter-clockwise)"
    def get_desc(self): return "Rotates adjacent cells counter-clockwise 90 degrees"
    def get_image(self): return "cell_rotatorccw"
    def get_priority(self): return 2
    def tick(self):
        if (cellU := Grid.getCellAt(self.pos + UP)) is not None:
            cellU.rotate(cellU.dir.rotccw())
        if (cellD := Grid.getCellAt(self.pos + DOWN)) is not None:
            cellD.rotate(cellD.dir.rotccw())
        if (cellL := Grid.getCellAt(self.pos + LEFT)) is not None:
            cellL.rotate(cellL.dir.rotccw())
        if (cellR := Grid.getCellAt(self.pos + RIGHT)) is not None:
            cellR.rotate(cellR.dir.rotccw())

class Rotator180(Cell):
    def get_label(self): return "Rotator (180)"
    def get_desc(self): return "Rotates adjacent cells 180 degrees"
    def get_image(self): return "cell_rotator180"
    def get_priority(self): return 2
    def tick(self):
        if (cellU := Grid.getCellAt(self.pos + UP)) is not None:
            cellU.rotate(cellU.dir.rot180())
        if (cellD := Grid.getCellAt(self.pos + DOWN)) is not None:
            cellD.rotate(cellD.dir.rot180())
        if (cellL := Grid.getCellAt(self.pos + LEFT)) is not None:
            cellL.rotate(cellL.dir.rot180())
        if (cellR := Grid.getCellAt(self.pos + RIGHT)) is not None:
            cellR.rotate(cellR.dir.rot180())

class Push(Cell):
    def get_label(self): return "Push"
    def get_desc(self): return "Can be pushed by other cells"
    def get_image(self): return "cell_push"
    def get_priority(self): return 0

class Slide(Cell):
    def get_label(self): return "Slide"
    def get_desc(self): return "Can be pushed only in the indicated direction"
    def get_image(self): return "cell_slide"
    def get_priority(self): return 0
    def apply_force(self, force, cell=None):
        if force == self.dir or force == self.dir.rot180():
            super().apply_force(force, self)
    
class Enemy(Cell):
    def get_label(self): return "Enemy"
    def get_desc(self): return "Destroys any cell that moves into it, along with itself"
    def get_image(self): return "cell_enemy"
    def get_priority(self): return 0  
    def apply_force(self, force, cell=None):
        if cell is None: return
        cell.destroy()
        self.destroy()

class Trash(Cell):
    def get_label(self): return "Trash"
    def get_desc(self): return "Destroys any cell that moves into it"
    def get_image(self): return "cell_trash"
    def get_priority(self): return 0
    def apply_force(self, force, cell=None):
        if cell is None:
            return
        cell.destroy()

# Main pygame loop
pygame.init()
screen = pygame.display.set_mode((800, 500))
pygame.display.set_caption(f"Pyxell (v{VERSION})")
clock = pygame.time.Clock()

running = True
sim_run = False
sim_run_off_next_frame = False
camera_zoom = 32
camera_pos = (0, 0)
placedir = Vector(1, 0)
selected = None
runtime = 0
clicked_this_frame = False
clicked_last_frame = False

while running:
    dt = clock.tick(60) / 1000.0

    clicked_this_frame = pygame.mouse.get_pressed()[0]

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                sim_run = not sim_run
                runtime = 1
            if event.key == pygame.K_e: placedir = placedir.rotcw() 
            if event.key == pygame.K_q: placedir = placedir.rotccw()
            if event.key == pygame.K_r: Grid.clear_all()
    
    keys = pygame.key.get_pressed()
    speed = 1/3
    x, y = camera_pos

    if keys[pygame.K_d]: x += speed
    if keys[pygame.K_a]: x -= speed
    if keys[pygame.K_w]: y -= speed
    if keys[pygame.K_s]: y += speed

    camera_pos = (x, y)

    if sim_run_off_next_frame:
        sim_run_off_next_frame = False
        sim_run = False

    # Palette
    palette_x = 10
    palette_y = screen.get_height() - 42
    palette_spacing = 40
    palette_scale = 32

    # Playback controls
    controls_x = 10
    controls_y = 10
    controls_spacing = 40
    controls_scale = 32

    controls = ["play", "step"]
    if sim_run:
        controls = ["pause", "stop"]

    mouse_pos = pygame.mouse.get_pos()
    gui_click = False
    if clicked_this_frame:
        print("CLICK")
        
        # Check none icon
        if palette_x <= mouse_pos[0] <= palette_x + palette_scale and\
                palette_y <= mouse_pos[1] <= palette_y + palette_scale:
            selected = None
            gui_click = True
        
        if not sim_run:
            # Check cell palette
            for i, cell_class in enumerate(Cell.subclasses):
                x = palette_x + (i + 1) * palette_spacing
                if x <= mouse_pos[0] <= x + palette_scale and\
                        palette_y <= mouse_pos[1] <= palette_y + palette_scale:
                    selected = cell_class
                    gui_click = True
                    print("Selected:", selected)
        
        # Check playback controls
        for i, c in enumerate(controls):
            x = controls_x + controls_spacing * i
            if x <= mouse_pos[0] <= x + controls_scale and\
                    controls_y <= mouse_pos[1] <= controls_y + controls_scale:
                if not clicked_last_frame:
                    if c == "play":
                        Grid.push_state()
                        sim_run = True
                        runtime = 1
                        print("Playing simulation")
                    elif c == "pause":
                        sim_run = False
                        runtime = 1
                        print("Pausing simulation")
                    elif c == "stop":
                        sim_run = False
                        runtime = 1
                        Grid.pop_state()
                        print("Stopping simulation")
                    elif c == "step":
                        sim_run = True
                        sim_run_off_next_frame = True
                        runtime = 1
                        print("Stepping simulation")
                gui_click = True

        # Edit grid state
        if not gui_click and not sim_run:
            world_pos = Vector(
                camera_pos[0] + (mouse_pos[0] - screen.get_width() / 2) / camera_zoom,
                camera_pos[1] + (mouse_pos[1] - screen.get_height() / 2) / camera_zoom
            )
            world_pos = Vector(math.floor(world_pos.x), math.floor(world_pos.y))
            print("World pos:", world_pos)
            print("Cell at pos:", Grid.getCellAt(world_pos))
            if selected and Grid.getCellAt(world_pos) is None:
                selected(world_pos, placedir)
                print("Placing at", world_pos)
            elif not selected and Grid.getCellAt(world_pos) is not None:
                Grid.getCellAt(world_pos).destroy()

    # Update
    if sim_run:
        if runtime >= 1:
            runtime -= 1

            # Sort by priority, then by direction and position
            directions = [RIGHT, LEFT, UP, DOWN]
            keys = [lambda c: -c.pos[0], lambda c: c.pos[0],
                    lambda c: c.pos[1], lambda c: -c.pos[1]]

            for priority in range(Cell.max_priority + 1):
                tick_order = []

                for direction, key in zip(directions, keys):
                    matching = [
                        c for c in Grid.cells
                        if c.dir == direction and c.get_priority() == priority
                    ]
                    tick_order.extend(sorted(matching, key=key))
                    
                # One pass for ticking cells
                for c in tick_order:
                    print("Ticking", c)
                    c.anim_from = c.pos
                    c.tick()
                # Another pass for moving cells
                for c in tick_order:
                    print("Moving", c)
                    c.move()

    for cell in Grid.cells:
        cell.update_animation(dt)
    
    if sim_run:
        runtime += dt * TICK_RATE
    else:
        runtime = 0

    # Draw
    empty = textures["grid_blank"]
    screen.fill((0, 0, 0))

    # Calculate visible grid bounds
    cam_x, cam_y = camera_pos
    grid_width = screen.get_width() / camera_zoom
    grid_height = screen.get_height() / camera_zoom
    min_x = int(cam_x - grid_width / 2) - 1
    max_x = int(cam_x + grid_width / 2) + 1
    min_y = int(cam_y - grid_height / 2) - 1
    max_y = int(cam_y + grid_height / 2) + 1

    # Draw grid
    for x in range(min_x, max_x):
        for y in range(min_y, max_y):
            if not Grid.isInBounds(Vector(x, y)): continue
            screen_x = (x - cam_x) * camera_zoom + screen.get_width() / 2
            screen_y = (y - cam_y) * camera_zoom + screen.get_height() / 2
            scaled = pygame.transform.scale(empty, (camera_zoom, camera_zoom))
            screen.blit(scaled, (screen_x, screen_y))

    # Draw cells
    for x in range(min_x, max_x):
        for y in range(min_y, max_y):
            if not Grid.isInBounds(Vector(x, y)): continue
            if cell := Grid.getCellAt(Vector(x, y)):
                r = cell.get_render_pos()
                rx, ry = r.x, r.y

                screen_x = (rx - cam_x) * camera_zoom + screen.get_width() / 2
                screen_y = (ry - cam_y) * camera_zoom + screen.get_height() / 2

                screen_x += camera_zoom / 2
                screen_y += camera_zoom / 2

                image = textures[cell.get_image()]
                scaled = pygame.transform.scale(image, (camera_zoom, camera_zoom))
                rotated = pygame.transform.rotate(scaled, cell.render_rot)

                rect = rotated.get_rect(center=(screen_x, screen_y))
                screen.blit(rotated, rect)
    
    # Draw cell palette
    none = textures["gui_none"]
    select_offset = 10

    # Draw none icon
    y = palette_y
    if selected == None:
        y -= select_offset
    scaled = pygame.transform.scale(none, (palette_scale, palette_scale))
    screen.blit(scaled, (palette_x, y))
    
    # Draw the rest of the cell palette
    for i, cell_class in enumerate(Cell.subclasses):
        x = palette_x + (i + 1) * palette_spacing
        y = palette_y
        
        # Move selected cell up
        if selected == cell_class:
            y -= select_offset
        
        dummy_cell = cell_class(Vector(0, 0), placedir)
        image = textures[dummy_cell.get_image()]
        scaled = pygame.transform.scale(image, (palette_scale, palette_scale))
        rotated = pygame.transform.rotate(scaled, rotate_by_dir(dummy_cell.dir))
        screen.blit(rotated, (x, y))
        dummy_cell.destroy(silent = True)
    
    # Draw playback controls
    for i, c in enumerate(controls):
        x = controls_x + controls_spacing * i
        image = textures["gui_" + c]
        scaled = pygame.transform.scale(image, (controls_scale, controls_scale))
        screen.blit(scaled, (x, controls_y))
    
    clicked_last_frame = clicked_this_frame
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()