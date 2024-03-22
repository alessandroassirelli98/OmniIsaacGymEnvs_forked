import numpy as np
from pynput import keyboard
from omni.isaac.kit import SimulationApp

class KeyboardManager():
    def __init__(self, hand_coord):
        self.action = hand_coord
        self.hand_close_idx = len(self.action)-1
        self.kill = False
        listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
        listener.start()

    def on_press(self, key):
        if (key == keyboard.Key.up):
            self.action[0] = 1
        if (key == keyboard.Key.down):
            self.action[0] = -1
        if (key == keyboard.Key.left):
            self.action[1] = 1
        if (key == keyboard.Key.right):                                  
            self.action[1] = -1
        if (key == keyboard.Key.page_up):
            self.action[2] = 1
        if (key == keyboard.Key.page_down):                                  
            self.action[2] = -1
        if (key == keyboard.Key.shift_l):
            self.action[3] = 1
        if (key == keyboard.Key.shift_r):                                  
            self.action[3] = -1

        if (key == keyboard.Key.space):
            self.action[self.hand_close_idx] = 1

        if (key == keyboard.Key.esc):
            self.kill = True
    
    def on_release(self, key):
        if (key == keyboard.Key.up or keyboard.Key.down):
            self.action[0] = 0
        if (key == keyboard.Key.left or key == keyboard.Key.right):
            self.action[1] = 0
        if (key == keyboard.Key.page_up or key == keyboard.Key.page_down):
            self.action[2] = 0
        if (key == keyboard.Key.shift_l or key ==keyboard.Key.shift_l):                                  
            self.action[3] = 0

        if (key == keyboard.Key.space):
            self.action[self.hand_close_idx] = 0

    
