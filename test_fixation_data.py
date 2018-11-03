from et import MyEyetracker
from appJar import gui

SCREEN_WIDTH = 1920
SCREEN_HEIGHT = 1080

def draw_circle(fixation_point_data):
	print('Drawing circle...')
	x, y = fixation_point_data[1][0]
	x, y = x * SCREEN_WIDTH, y * SCREEN_HEIGHT
	print(x, y)
	app.addCanvasOval('c1', x - 3, y - 3, 6, 6, fill='red')
	app.topLevel.update()

def main():
	et.start_collection()
	while True:
		draw_circle(et.wait_for_fixation_point())
	et.stop_collection()

app = gui()
app.setSize(SCREEN_WIDTH, SCREEN_HEIGHT)
app.addCanvas('c1')
et = MyEyetracker()
app.setStartFunction(main)
app.setLocation(0, 0)
app.go()

