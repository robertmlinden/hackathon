from pygame.locals import *
from random import randint
import pygame
import time
from tracker import Tracker
from calibrate import calibrate_user
from queue import Queue
 
class Apple:
    x = 0
    y = 0
    step = 44
 
    def __init__(self,x,y):
        self.x = x * self.step
        self.y = y * self.step
 
    def draw(self, surface, image):
        surface.blit(image,(self.x, self.y)) 
 
 
class Player:
    x = [0]
    y = [0]
    step = 44
    direction = 0
    length = 3
 
    updateCountMax = 2
    updateCount = 0
 
    def __init__(self, length):
       self.length = length
       for i in range(0,2000):
           self.x.append(-100)
           self.y.append(-100)
 
       # initial positions, no collision.
       self.x[1] = 1*44
       self.x[2] = 2*44
 
    def update(self):
 
        self.updateCount = self.updateCount + 1
        if self.updateCount > self.updateCountMax:
 
            # update previous positions
            for i in range(self.length-1,0,-1):
                self.x[i] = self.x[i-1]
                self.y[i] = self.y[i-1]
 
            # update position of head of snake
            if self.direction == 0:
                self.x[0] = self.x[0] + self.step
            if self.direction == 1:
                self.x[0] = self.x[0] - self.step
            if self.direction == 2:
                self.y[0] = self.y[0] - self.step
            if self.direction == 3:
                self.y[0] = self.y[0] + self.step
 
            self.updateCount = 0
 
 
    def moveRight(self):
        self.direction = 0
 
    def moveLeft(self):
        self.direction = 1
 
    def moveUp(self):
        self.direction = 2
 
    def moveDown(self):
        self.direction = 3 
 
    def draw(self, surface, image):
        for i in range(0,self.length):
            surface.blit(image,(self.x[i],self.y[i])) 
 
class Game:
    def isCollision(self,x1,y1,x2,y2,bsize):
        if x1 >= x2 and x1 <= x2 + bsize:
            if y1 >= y2 and y1 <= y2 + bsize:
                return True
        return False
 
import os

class Snake:
 
    windowWidth = 1920
    windowHeight = 1080
 
    def __init__(self):
        self._running = True
        self._display_surf = None
        self._image_surf = None
        self._apple_surf = None
        self.game = Game()
        self.player = Player(3) 
        self.apple = Apple(5,5)
        self.RESOURCES = 'resources'
 
    def on_init(self):
        pygame.init()
        #self._display_surf = pygame.display.set_mode((self.windowWidth,self.windowHeight), pygame.HWSURFACE)
        self._display_surf = pygame.Surface((windowWidth, windowHeight))
        self._display_surf.fill('#000000')

        self._running = True
        self._image_surf = pygame.image.load(os.path.join(self.RESOURCES, "snake.jpg")).convert()
        self._apple_surf = pygame.image.load(os.path.join(self.RESOURCES, "food.jpg")).convert()
 
    def on_event(self, event):
        if event.type == QUIT:
            self._running = False
 
    def on_loop(self):
        self.player.update()
 
        # does snake eat apple?
        for i in range(0,self.player.length):
            if self.game.isCollision(self.apple.x,self.apple.y,self.player.x[i], self.player.y[i],44):
                self.apple.x = randint(2,9) * 44
                self.apple.y = randint(2,9) * 44
                self.player.length = self.player.length + 1
 
 
        # does snake collide with itself?
        for i in range(2,self.player.length):
            if self.game.isCollision(self.player.x[0],self.player.y[0],self.player.x[i], self.player.y[i],40):
                print("You lose! Collision: ")
                print("x[0] (" + str(self.player.x[0]) + "," + str(self.player.y[0]) + ")")
                print("x[" + str(i) + "] (" + str(self.player.x[i]) + "," + str(self.player.y[i]) + ")")
                exit(0)
 
        pass
 
    def on_render(self):
        self._display_surf.fill((0,0,0))
        self.player.draw(self._display_surf, self._image_surf)
        self.apple.draw(self._display_surf, self._apple_surf)
        pygame.display.flip()
 
    def on_cleanup(self):
        self.eyetracker.stop_recording()
        pygame.quit()
 
    import sys

    def listen_for_fixations(self, fixation_point_queue):
        while True:
            stime, etime, spos = self.eyetracker.get_fixation()
            fixation_time = etime - stime
            fixation_point_queue.put(fixation_time, spos)

    def get_direction(self, fixation_points):
        fixation_points.sort(key=lambda fixation_point: fixation_point[0], reverse=True)
        direction = fixation_points[0]
        print(direction)

    def on_execute_eye_tracking(self):
        if self.on_init() == False:
            self._running = False

        # Put eye code here
        fixation_point_queue = Queue()

        import threading
        thread = threading.Thread(target=self.listen_for_fixations, args=(fixation_point_queue,))
        thread.start()
 
        while( self._running ):
            pygame.event.pump()

            fixations = []
            while not fixation_point_queue.empty():
                fixations.append(fixation_point_queue.get())

            if fixations:
                direction = self.get_direction(fixations)
 
            self.on_loop()
            self.on_render()
 
            time.sleep (50.0 / 1000.0)


        self.on_cleanup()
 
user = 'robert'

if __name__ == "__main__":
    snake = Snake()
    calibrate_user(user)
    tracker = Tracker(user)
    tracker.start_recording()
    
    tracker.stop_recording()
    