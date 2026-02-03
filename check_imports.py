import sys
import time

print("Start imports...")
t0 = time.time()

print("Importing pygame...")
import pygame
print(f"Pygame imported in {time.time()-t0:.2f}s")

print("Importing gpiozero...")
try:
    from gpiozero import Button
    print(f"gpiozero imported in {time.time()-t0:.2f}s")
except Exception as e:
    print(f"gpiozero failed: {e}")

print("Importing lgpio...")
try:
    import lgpio
    print(f"lgpio imported in {time.time()-t0:.2f}s")
except Exception as e:
    print(f"lgpio failed: {e}")

print("Done imports.")
