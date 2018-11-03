import tobii_research as tr
import time

import utils
import copy

class MyEyetracker(object):

    def __init__(self):
        # The fixation threshold -- the bound for error
        self.DISTANCE_FRACTION_FIXATION_THRESHOLD = .025

        # Data collection duration in seconds
        self.TIME_COLLECT = 10

        self.FIXATION_TIME_THRESHOLD = 0.05

        try:
            self.my_eyetracker = tr.find_all_eyetrackers()[0]
        except ValueError:
            print('Tobii eyetracker not found')

        self.pos = (-1, -1)

        print('--------------------------------------------------------------------------------')
        print("Address: " + self.my_eyetracker.address)
        print("Model: " + self.my_eyetracker.model)
        print("Name (It's OK if this is empty): " + self.my_eyetracker.device_name)
        print("Serial number: " + self.my_eyetracker.serial_number)
        print('--------------------------------------------------------------------------------')

    def update_position_callback(self, gaze_data):
        # Print gaze points of left and right eye
        #print("Left eye: ({gaze_left_eye}) \t Right eye: ({gaze_right_eye})".format(
        #    gaze_left_eye=gaze_data['left_gaze_point_on_display_area'],
        #    gaze_right_eye=gaze_data['right_gaze_point_on_display_area']))
        left = gaze_data['left_gaze_point_on_display_area']
        right = gaze_data['right_gaze_point_on_display_area']
        #print(left, right)
        #print(left, right)
        try:
            int(left[0]), int(left[1]), int(right[0]), int(right[1])
        except:
            self.pos = (-1, -1)
        self.pos = utils.average(left[0], right[0]), utils.average(left[1], right[1])

    def is_valid_sample(self, pos):
        return pos != (-1, -1)

    def start_collection(self):
        self.my_eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.update_position_callback, as_dictionary=True)

    def stop_collection(self):
        self.my_eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self.update_position_callback)

    def listen_for_fixation_points(self, callback):
        self.start_collection()
        while True:
            callback(self.wait_for_fixation_point())
        self.stop_collection()

    def insight(self):
        t0 = time.clock()
        while time.clock() - t0 < self.TIME_COLLECT:
            print('Fixation piont at ' + str(self.wait_for_fixation_point()))

    def wait_for_fixation_start(self):
        # Get sample here

        # get starting time
        t0 = time.clock()

        while not self.is_valid_sample(self.pos):
            pass

        while True:
            spos = self.pos
            if self.is_valid_sample(self.pos):
                while True:
                    # get new sample
                    npos = self.pos

                    if not self.is_valid_sample(npos):
                        break

                    # check if new sample is too far from starting position to be within the same fixation
                    if (npos[0] - spos[0])**2 + (npos[1] - spos[1])**2 > self.DISTANCE_FRACTION_FIXATION_THRESHOLD**2:  # Pythagoras
                        # if not, reset starting position and time
                        spos = copy.copy(npos)
                        t0 = time.clock()
                    # if new sample is close to starting sample
                    else:
                        # get timestamp
                        t1 = time.clock()
                        # check if fixation time threshold has been surpassed
                        if t1 - t0 >= self.FIXATION_TIME_THRESHOLD:
                            return t0, npos

    def wait_for_fixation_point(self):
        print('Getting fixation point...')

        stime, spos = self.wait_for_fixation_start()
        
        etime = stime

        while True:
            # get new sample
            npos = self.pos  # get newest sample
            # check if sample is valid
            if self.is_valid_sample(npos):
                # check if sample deviates to much from starting position
                if (npos[0] - spos[0])**2 + (npos[1] - spos[1])**2 > self.DISTANCE_FRACTION_FIXATION_THRESHOLD**2:
                    # break loop if deviation is too high
                    etime = time.clock()
                    break
        print('returning...')
        return (stime, etime), (spos, npos)

'''
et = MyEyetracker()
et.start_collection()
et.insight()
et.stop_collection()
'''