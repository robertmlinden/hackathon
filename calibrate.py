import tobii_research as tr
import constants
import os
import json
import time
import math


from pygaze import libscreen
from pygaze import libinput

from tkinter import messagebox

DEBUG = False


class Calibrator(object):
    INVALID = -1
    INVALID_PAIR = (INVALID, INVALID)

    def __init__(self):
        try:
            self.eyetracker = tr.find_all_eyetrackers()[0]
        except IndexError:
            messagebox.showinfo("Error", "Tobii Eye Tracker not found. Please restart the Tobii Service\nfound in the \"Services\" application")
            import sys
            sys.exit(1)

        self.gaze_data = []

        self.disp = libscreen.Display()
        self.screen = libscreen.Screen()
        self.kb = libinput.Keyboard(keylist=['space', 'escape', 'q'], timeout=1)
        self.screendist = constants.SCREENDIST

        # calibration and validation points
        lb = 0.1  # left bound
        xc = 0.5  # horizontal center
        rb = 0.9  # right bound
        ub = 0.1  # upper bound
        yc = 0.5  # vertical center
        bb = 0.9  # bottom bound
        self.points_to_calibrate = [self._norm_2_px(p) for p in [(lb, ub), (rb, ub), (xc, yc), (lb, bb), (rb, bb)]]
        
        # maximal distance from fixation start (if gaze wanders beyond this, fixation has stopped)
        self.fixtresh = 1.5  # degrees
        # amount of time gaze has to linger within self.fixtresh to be marked as a fixation
        self.fixtimetresh = 100  # milliseconds
        # saccade velocity threshold
        self.spdtresh = 35  # degrees per second
        # saccade acceleration threshold
        self.accthresh = 9500  # degrees per second**2
        # blink detection threshold used in PyGaze method
        self.blinkthresh = 50 # milliseconds
        
        self.screensize = constants.SCREENSIZE  # display size in cm
        self.pixpercm = (self.disp.dispsize[0] / float(self.screensize[0]) +
                         self.disp.dispsize[1] / float(self.screensize[1])) / 2.0

    def __repr__(self):
        return json.dumps(self.__dict__)
    
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

    def calibrate(self, calibrate=True, validate=True):
        self.start_recording()
        self.screen.set_background_colour(colour=(0, 0, 0))

        if calibrate:
            origin = (int(self.disp.dispsize[0] / 4), int(self.disp.dispsize[1] / 4))
            size = (int(2 * self.disp.dispsize[0] / 4), int(2 * self.disp.dispsize[1] / 4))

            while not self.kb.get_key(keylist=['space'], flush=False)[0]:
                # TODO: What should we do when there are no gaze samples yet?
                # Should we wait or raise an Exception to indicate that
                # something went wrong.
                if not self.gaze_data:
                    continue
                gaze_sample = self.gaze_data[-1]

                self.screen.clear()

                validity_colour = (255, 0, 0)

                if gaze_sample['right_gaze_origin_validity'] and gaze_sample['left_gaze_origin_validity']:
                    left_validity = 0.15 < gaze_sample['left_gaze_origin_in_trackbox_coordinate_system'][2] < 0.85
                    right_validity = 0.15 < gaze_sample['right_gaze_origin_in_trackbox_coordinate_system'][2] < 0.85
                    if left_validity and right_validity:
                        validity_colour = (0, 255, 0)

                self.screen.draw_text(text="When correctly positioned press \'space\' to start the calibration.",
                                      pos=(int(self.disp.dispsize[0] / 2), int(self.disp.dispsize[1] * 0.1)),
                                      colour=(255, 255, 255),
                                      fontsize=20)
                self.screen.draw_line(colour=validity_colour, spos=origin, epos=(origin[0] + size[0], origin[1]), pw=1)
                self.screen.draw_line(colour=validity_colour, spos=origin, epos=(origin[0], origin[1] + size[1]), pw=1)
                self.screen.draw_line(colour=validity_colour,
                                      spos=(origin[0], origin[1] + size[1]),
                                      epos=(origin[0] + size[0], origin[1] + size[1]),
                                      pw=1)
                self.screen.draw_line(colour=validity_colour,
                                      spos=(origin[0] + size[0], origin[1] + size[1]),
                                      epos=(origin[0] + size[0], origin[1]),
                                      pw=1)

                right_eye, left_eye, distance = None, None, []
                if gaze_sample['right_gaze_origin_validity']:
                    distance.append(round(gaze_sample['right_gaze_origin_in_user_coordinate_system'][2] / 10, 1))
                    right_pos = gaze_sample['right_gaze_origin_in_trackbox_coordinate_system']
                    right_eye = ((1 - right_pos[0]) * size[0] + origin[0], right_pos[1] * size[1] + origin[1])
                    self.screen.draw_circle(colour=validity_colour,
                                            pos=right_eye,
                                            r=int(self.disp.dispsize[0] / 100),
                                            pw=5,
                                            fill=True)

                if gaze_sample['left_gaze_origin_validity']:
                    distance.append(round(gaze_sample['left_gaze_origin_in_user_coordinate_system'][2] / 10, 1))
                    left_pos = gaze_sample['left_gaze_origin_in_trackbox_coordinate_system']
                    left_eye = ((1 - left_pos[0]) * size[0] + origin[0], left_pos[1] * size[1] + origin[1])
                    self.screen.draw_circle(colour=validity_colour,
                                            pos=left_eye,
                                            r=int(self.disp.dispsize[0] / 100),
                                            pw=5,
                                            fill=True)

                self.screen.draw_text(text="Current distance to the eye tracker: {0} cm.".format(self._mean(distance)),
                                      pos=(int(self.disp.dispsize[0] / 2), int(self.disp.dispsize[1] * 0.9)),
                                      colour=(255, 255, 255),
                                      fontsize=20)

                self.disp.fill(self.screen)
                self.disp.show()

            # # # # # #
            # # calibration

            if not self.eyetracker:
                if DEBUG: print("WARNING! libtobii.TobiiProTracker.calibrate: no eye trackers found for the calibration!")
                self.stop_recording()
                return False

            calibration = tr.ScreenBasedCalibration(self.eyetracker)
            calibrating = True

            while calibrating:
                calibration.enter_calibration_mode()

                for point in self.points_to_calibrate:
                    self.screen.clear()
                    self.screen.draw_circle(colour=(255, 255, 255),
                                            pos=point,
                                            r=int(self.disp.dispsize[0] / 100.0),
                                            pw=5,
                                            fill=True)
                    self.screen.draw_circle(colour=(255, 0, 0),
                                            pos=point,
                                            r=int(self.disp.dispsize[0] / 400.0),
                                            pw=5,
                                            fill=True)
                    self.disp.fill(self.screen)
                    self.disp.show()

                    # Wait a little for user to focus.
                    time.sleep(1)

                    normalized_point = self._px_2_norm(point)

                    collect_result = calibration.collect_data(normalized_point[0], normalized_point[1])

                    if collect_result != tr.CALIBRATION_STATUS_SUCCESS:
                        # Try again if it didn't go well the first time.
                        # Not all eye tracker models will fail at this point, but instead fail on ComputeAndApply.
                        calibration.collect_data(normalized_point[0], normalized_point[1])

                self.screen.clear()
                self.screen.draw_text("Calculating calibration result....", colour=(255, 255, 255), fontsize=20)
                self.disp.fill(self.screen)
                self.disp.show()

                calibration_result = calibration.compute_and_apply()

                calibration.leave_calibration_mode()

                if DEBUG: print("Compute and apply returned {0} and collected at {1} points.".
                      format(calibration_result.status, len(calibration_result.calibration_points)))

                if calibration_result.status != tr.CALIBRATION_STATUS_SUCCESS:
                    self.stop_recording()
                    if DEBUG: print("WARNING! libtobii.TobiiProTracker.calibrate: Calibration was unsuccessful!")
                    return False

                self.screen.clear()
                for point in calibration_result.calibration_points:
                    self.screen.draw_circle(colour=(255, 255, 255),
                                            pos=self._norm_2_px(point.position_on_display_area),
                                            r=self.disp.dispsize[0] / 200,
                                            pw=1,
                                            fill=False)
                    for sample in point.calibration_samples:
                        if sample.left_eye.validity == tr.VALIDITY_VALID_AND_USED:
                            self.screen.draw_circle(colour=(255, 0, 0),
                                                    pos=self._norm_2_px(sample.left_eye.position_on_display_area),
                                                    r=self.disp.dispsize[0] / 450,
                                                    pw=self.disp.dispsize[0] / 450,
                                                    fill=False)
                            self.screen.draw_line(colour=(255, 0, 0),
                                                  spos=self._norm_2_px(point.position_on_display_area),
                                                  epos=self._norm_2_px(sample.left_eye.position_on_display_area),
                                                  pw=1)
                        if sample.right_eye.validity == tr.VALIDITY_VALID_AND_USED:
                            self.screen.draw_circle(colour=(0, 0, 255),
                                                    pos=self._norm_2_px(sample.right_eye.position_on_display_area),
                                                    r=self.disp.dispsize[0] / 450,
                                                    pw=self.disp.dispsize[0] / 450,
                                                    fill=False)
                            self.screen.draw_line(colour=(0, 0, 255),
                                                  spos=self._norm_2_px(point.position_on_display_area),
                                                  epos=self._norm_2_px(sample.right_eye.position_on_display_area),
                                                  pw=1)

                self.screen.draw_text("Press the \'R\' key to recalibrate or \'Space\' to continue....",
                                      pos=(0.5 * self.disp.dispsize[0], 0.95 * self.disp.dispsize[1]),
                                      colour=(255, 255, 255), fontsize=20)

                self.screen.draw_text("Left Eye", pos=(0.5 * self.disp.dispsize[0], 0.01 * self.disp.dispsize[1]),
                                      colour=(255, 0, 0), fontsize=20)
                self.screen.draw_text("Right Eye", pos=(0.5 * self.disp.dispsize[0], 0.03 * self.disp.dispsize[1]),
                                      colour=(0, 0, 255), fontsize=20)

                self.disp.fill(self.screen)
                self.disp.show()

                pressed_key = self.kb.get_key(keylist=['space', 'r'], flush=True, timeout=None)

                if pressed_key[0] == 'space':
                    calibrating = False

        if validate:
            # # # show menu
            self.screen.clear()
            self.screen.draw_text(text="Press space to start validation", colour=(255, 255, 255), fontsize=20)
            self.disp.fill(self.screen)
            self.disp.show()

            # # # wait for spacepress
            self.kb.get_key(keylist=['space'], flush=True, timeout=None)

            # # # # # #
            # # validation

            # # # arrays for data storage
            lxacc, lyacc, rxacc, ryacc = [], [], [], []

            # # loop through all calibration positions
            for pos in self.points_to_calibrate:
                # show validation point
                self.screen.clear()
                self.screen.draw_fixation(fixtype='dot', pos=pos, colour=(255, 255, 255))
                self.disp.fill(self.screen)
                self.disp.show()

                # allow user some time to gaze at dot
                time.sleep(1)

                lxsamples, lysamples, rxsamples, rysamples = [], [], [], []
                for sample in self.gaze_data:
                    if sample["left_gaze_point_validity"]:
                        gaze_point = self._norm_2_px(sample["left_gaze_point_on_display_area"])
                        lxsamples.append(abs(gaze_point[0] - pos[0]))
                        lysamples.append(abs(gaze_point[1] - pos[1]))
                    if sample["right_gaze_point_validity"]:
                        gaze_point = self._norm_2_px(sample["right_gaze_point_on_display_area"])
                        rxsamples.append(abs(gaze_point[0] - pos[0]))
                        rysamples.append(abs(gaze_point[1] - pos[1]))

                # calculate mean deviation
                lxacc.append(self._mean(lxsamples))
                lyacc.append(self._mean(lysamples))
                rxacc.append(self._mean(rxsamples))
                ryacc.append(self._mean(rysamples))

                # wait for a bit to slow down validation process a bit
                time.sleep(1)

            # calculate mean accuracy
            self.pxaccuracy = [(self._mean(lxacc), self._mean(lyacc)), (self._mean(rxacc), self._mean(ryacc))]

            # sample rate
            # calculate intersample times
            timestamps = []
            gaze_samples = self.gaze_data
            for i in range(0, len(gaze_samples) - 1):
                next_sample = gaze_samples[i + 1]['system_time_stamp']
                current_sample = gaze_samples[i]['system_time_stamp']
                timestamps.append((next_sample - current_sample) / 1000.0)

            # mean intersample time
            self.sampletime = self._mean(timestamps)
            self.samplerate = int(1000.0 / self.sampletime)

            # # # # # #
            # # RMS noise

            # # present instructions
            self.screen.clear()
            self.screen.draw_text(text="Noise calibration: please look at the dot\n\n(press space to start)",
                                  pos=(self.disp.dispsize[0] / 2, int(self.disp.dispsize[1] * 0.2)),
                                  colour=(255, 255, 255), fontsize=20)
            self.screen.draw_fixation(fixtype='dot', colour=(255, 255, 255))
            self.disp.fill(self.screen)
            self.disp.show()

            # # wait for spacepress
            self.kb.get_key(keylist=['space'], flush=True, timeout=None)

            # # show fixation
            self.screen.draw_fixation(fixtype='dot', colour=(255, 255, 255))
            self.disp.fill(self.screen)
            self.disp.show()
            self.screen.clear()

            # # wait for a bit, to allow participant to fixate
            time.sleep(1)

            # # get samples
            # samplelist, prefilled with 1 sample to prevent sl[-1] from producing an error
            # first sample will be ignored for RMS calculation
            sl = [self.sample()]
            t0 = self.millis()  # starting time
            while self.millis() - t0 < 1000:
                s = self.sample()  # sample
                if s != sl[-1] and self.is_valid_sample(s) and s != (0, 0):
                    sl.append(s)

            # # calculate RMS noise
            Xvar, Yvar = [], []
            for i in range(2, len(sl)):
                Xvar.append((sl[i][0] - sl[i - 1][0])**2)
                Yvar.append((sl[i][1] - sl[i - 1][1])**2)
            XRMS = (self._mean(Xvar))**0.5
            YRMS = (self._mean(Yvar))**0.5
            self.pxdsttresh = (XRMS, YRMS)

            # # # # # # #
            # # # calibration report

            # # # # recalculate thresholds (degrees to pixels)
            self.pxfixtresh = self._deg2pix(self.screendist, self.fixtresh, self.pixpercm)
            # in pixels per millisecons
            self.pxspdtresh = self._deg2pix(self.screendist, self.spdtresh / 1000.0, self.pixpercm)
            # in pixels per millisecond**2
            self.pxacctresh = self._deg2pix(self.screendist, self.accthresh / 1000.0, self.pixpercm)

            data_to_write = ''
            data_to_write += "pygaze calibration report start\n"
            data_to_write += "samplerate: %s Hz\n" % self.samplerate
            data_to_write += "sampletime: %s ms\n" % self.sampletime
            data_to_write += "accuracy (in pixels): LX=%s, LY=%s, RX=%s, RY=%s\n" % (self.pxaccuracy[0][0],
                                                                                     self.pxaccuracy[0][1],
                                                                                     self.pxaccuracy[1][0],
                                                                                     self.pxaccuracy[1][1])
            data_to_write += "precision (RMS noise in pixels): X=%s, Y=%s\n" % (self.pxdsttresh[0], self.pxdsttresh[1])
            data_to_write += "fixation threshold: %s pixels\n" % self.pxfixtresh
            data_to_write += "speed threshold: %s pixels/ms\n" % self.pxspdtresh
            data_to_write += "accuracy threshold: %s pixels/ms**2\n" % self.pxacctresh
            data_to_write += "pygaze calibration report end\n"

            self.screen.clear()
            self.screen.draw_text(text=data_to_write, pos=(self.disp.dispsize[0] / 2, int(self.disp.dispsize[1] / 2)),
                                  colour=(255, 255, 255), fontsize=20)
            self.disp.fill(self.screen)
            self.disp.show()

            self.kb.get_key(keylist=['space'], flush=True, timeout=None)
        
        self.stop_recording()
        self.disp.close()

        return True
    
    def is_valid_sample(self, spos):
        return spos != self.INVALID_PAIR

    def start_recording(self):
        self.gaze_data = []
        self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._on_gaze_data, as_dictionary=True)
        time.sleep(1)
        self.recording = True

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

    def cleanup(self):
        try:
            self.disp.close()
        except: 
            pass

    def __del__(self):
        self.cleanup()

    def __enter__ (self):
        return self

    def __exit__(self, *exc):
        """
        Invoke when calls <manager object>.shutdown().
        """
        if DEBUG: print("Terminate the manager thread")
        if DEBUG: print("__exit__")
        self.disp.close()

    def _norm_2_px(self, normalized_point):
        return (round(normalized_point[0] * self.disp.dispsize[0], 0),
                round(normalized_point[1] * self.disp.dispsize[1], 0))

    def _px_2_norm(self, pixelized_point):
        return (pixelized_point[0] / self.disp.dispsize[0], pixelized_point[1] / self.disp.dispsize[1])

    def one_eye_gaze_valid(self, eye):
        return self.gaze_data[-1][eye + "_gaze_point_validity"]

    def one_eye_gaze_sample(self, eye):
        if self.one_eye_gaze_valid(eye):
            return self._norm_2_px(self.gaze_data[-1][eye + "_gaze_point_on_display_area"])
        else:
            return self.INVALID_PAIR

    def millis(self):
        return time.clock() * 1000

    def sample(self):
        left_sample = self.one_eye_gaze_sample('left')
        right_sample = self.one_eye_gaze_sample('right')

        if self.one_eye_gaze_valid('left') and self.one_eye_gaze_valid('right'):
            return self._mean([left_sample[0], right_sample[0]]), self._mean([left_sample[1], right_sample[1]])
        elif self.one_eye_gaze_valid('left'):
            return left_sample
        elif self.one_eye_gaze_valid('right'):
            return right_sample
        else:
            return self.INVALID_PAIR

# Standalone Pygame+Pygaze application invoked by the frontend to calibrate the user
def calibrate_user(participant_username):
    calibrator = Calibrator()
    calibrator.calibrate()
    
    basepath = (constants.OUTPUT_PATH, participant_username)
    calibration_filename = "calibration.json"

    calibration_filepath = os.path.join(*basepath, calibration_filename)

    if not os.path.exists(os.path.join(*basepath)):
        os.makedirs(os.path.join(*basepath))

    with open(calibration_filepath, 'w+') as outfile:
        json.dump(calibrator.config, outfile)
