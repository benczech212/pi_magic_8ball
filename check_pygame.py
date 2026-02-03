import os
import pygame
import sys

print("Setting dummy driver...")
os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"

print("Initializing pygame...")
pygame.init()
print("Pygame initialized.")

print("Setting mode...")
try:
    screen = pygame.display.set_mode((100, 100))
    print("Mode set.")
except Exception as e:
    print(f"Set mode failed: {e}")
    sys.exit(1)

print("Filling screen...")
screen.fill((255, 0, 0))
print("Saving image...")
pygame.image.save(screen, "test_dummy.png")
print("Image saved.")
sys.exit(0)
