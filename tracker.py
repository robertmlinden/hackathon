import constants as c

from pygaze.libtime import clock
import tobii_research as tr
import os
import math
import copy
import time
import json

DEBUG = True

class Tracker(object):
    INVALID = -1
    INVALID_PAIR = (INVALID, INVALID)

    def __init__(self, user):
        try:
            self.eyetracker = tr.find_all_eyetrackers()[0]
        except IndexError:
            if c.DEBUG: print('Restart Tobii eyetracker service. It is currently shut off/unresponsive.')
            import sys
            sys.exit(1)

        self.screendist = c.SCREENDIST
        
        self.gaze_data = []

        self.eye_used_default = self.AVERAGE

         # maximal distance from fixation start (if gaze wanders beyond this, fixation has stopped)
        self.fixtresh = 0.5  # degrees
        # amount of time gaze has to linger within self.fixtresh to be marked as a fixation
        self.spdtresh = 35  # degrees per second
        # saccade acceleration threshold
        self.accthresh = 9500  # degrees per second**2
        # blink detection threshold used in PyGaze method
        
        self.screensize = c.SCREENSIZE  # display size in cm
        self.dispsize = c.DISPSIZE
        self.pixpercm = (self.dispsize[0] / float(self.screensize[0]) +
                         self.dispsize[1] / float(self.screensize[1])) / 2.0
        self.errdist = 2  # degrees; maximal error for drift correction
        self.pxerrdist = self._deg2pix(self.screendist, self.errdist, self.pixpercm)

        self.terminate = False

        calibration_file = user + '.json'
        calibration_filepath = os.path.join(c.CALIBRATION_PATH, calibration_file)

        self.config = json.load()

    @property
    def config(self):
        return {
            'pxfixtresh': self.pxfixtresh,
            'fixtimetresh': self.fixtimetresh,
            'pxdsttresh': self.pxdsttresh,
            'pxacctresh': self.pxacctresh,
            'blinkthresh': self.blinkthresh
        }

    @config.setter
    def config(self, configuration):
        for key, value in configuration.items():
            self.__setattr__(key, value)

    def setTerminate(self):
        self.terminate = True

    def done(self):
        return self.terminate
    
    def millis(self):
        return clock.get_time() - self.t0

    def is_valid_sample(self, spos):
        return spos != self.INVALID_PAIR

    def start_recording(self):
        self.gaze_data = []
        self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._on_gaze_data, as_dictionary=True)
        time.sleep(1)
        self.recording = True
        self.t0 = clock.get_time()

    def stop_recording(self):
        self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA)
        self.recording = False

    def _deg2pix(self, cmdist, angle, pixpercm):
        return pixpercm * math.tan(math.radians(angle)) * float(cmdist)

    def _on_gaze_data(self, gaze_data):
        self.gaze_data.append(gaze_data)

    def _mean(self, array):
        if array:
            a = [s for s in array if s is not None]
        else:
            a = [0]
        return sum(a) / float(len(a))

    def __enter__ (self):
        return self

    def __exit__(self, *exc):
        """
        Invoke when calls <manager object>.shutdown().
        """
        if c.DEBUG: print("Terminate the manager thread")
        if c.DEBUG: print("__exit__")

    def _norm_2_px(self, normalized_point):
        return (round(normalized_point[0] * self.dispsize[0], 0),
                round(normalized_point[1] * self.dispsize[1], 0))

    def _px_2_norm(self, pixelized_point):
        return (pixelized_point[0] / self.dispsize[0], pixelized_point[1] / self.dispsize[1])

    '''
    param `eye`: "right" or "left"
    '''
    def one_eye_gaze_valid(self, eye):
        return self.gaze_data[-1][eye + "_gaze_point_validity"]

    def one_eye_gaze_sample(self, eye):
        if self.one_eye_gaze_valid(eye):
            return self._norm_2_px(self.gaze_data[-1][eye + "_gaze_point_on_display_area"])
        else:
            return self.INVALID_PAIR
        
    
    def gaze_point(self, gaze_sample):
        if gaze_sample["left_gaze_point_validity"] and gaze_sample["right_gaze_point_validity"]:
            left_sample = self._norm_2_px(gaze_sample["left_gaze_point_on_display_area"])
            right_sample = self._norm_2_px(gaze_sample["right_gaze_point_on_display_area"])
            return (self._mean([left_sample[0], right_sample[0]]), self._mean([left_sample[1], right_sample[1]]))
        if gaze_sample["left_gaze_point_validity"]:
            return self._norm_2_px(gaze_sample["left_gaze_point_on_display_area"])
        if gaze_sample["right_gaze_point_validity"]:
            return self._norm_2_px(gaze_sample["right_gaze_point_on_display_area"])
        return (-1, -1)
    
    def pupil_size(self, gaze_sample):
        pupil_data = self.INVALID
        if gaze_sample:
            if gaze_sample["left_pupil_validity"] and gaze_sample["right_pupil_validity"]:
                pupil_data = self._mean([gaze_sample["left_pupil_diameter"], gaze_sample["right_pupil_diameter"]])
            if gaze_sample["left_pupil_validity"]:
                pupil_data = gaze_sample["left_pupil_diameter"]
            if gaze_sample["right_pupil_validity"]:
                pupil_data = gaze_sample["right_pupil_diameter"]
        return pupil_data

    def sample(self):
        gaze_sample = self.gaze_data[-1]
        t = self.millis()
        x, y = self.gaze_point(gaze_sample)
        d = self.pupil_size(gaze_sample)
        return (t, x, y, d)

    def wait_for_fixation_start(self):
        params = self.config
        pxfixtresh = params['pxfixtresh']
        fixtimetresh = params['fixtimetresh']

        spos = self.sample()
        while not self.is_valid_sample((spos[1],spos[2])):
            spos = self.sample()

        t0 = spos[0]
        sx, sy = spos[1], spos[2]

        while True:
            npos = data_generator.__next__()
            nx, ny = npos[1], npos[2]
            if self.is_valid_sample((nx, ny)):
                # check if new sample is too far from starting position
                if (nx - sx)**2 + (ny - sy)**2 > pxfixtresh**2:  # Pythagoras
                    # if not, reset starting position and time
                    sx, sy = nx, ny
                    t0 = npos[0]
                # if new sample is close to starting sample
                else:
                    # get timestamp
                    t1 = npos[0]
                    # check if fixation time threshold has been surpassed
                    if t1 - t0 >= fixtimetresh:
                        # return time and starting position

                        return t0, sx, sy

    def get_fixation_point(self, data_generator):
        params = self.config
        pxfixtresh = params['pxfixtresh']

        stime, sx, sy = self.wait_for_fixation_start(data_generator)
        etime = None
        while True:
            # get new sample from the samples.csv file
            npos = data_generator.__next__()
            nx, ny = npos[1], npos[2]
            # check if sample is valid
            if self.is_valid_sample((npos[1],npos[2])):
                # check if sample deviates to much from starting position
                if (nx - sx)**2 + (ny - sy)**2 > pxfixtresh**2:
                    # break loop if deviation is too high
                    etime = npos[0]
                    break

        return stime, etime, sx, sy

