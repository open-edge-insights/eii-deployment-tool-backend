# Copyright (c) 2021 Intel Corporation.

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

""" Module for camera handling """

import time
from threading import Thread, Lock
import cv2
from .util import Util

class Camera:
    """
    Class for managing camera streaming

    """

    def __init__(self):
        self.device_threads = {}
        self.mutex = Lock()
        self.util = Util()

    def resize_image(self, image, width=None, height=None, method=cv2.INTER_AREA):
        """Function to resize an image

        :param image: imagedata
        :type image: bytearray
        :param width: new image width
        :type width: int
        :param height: new image height
        :type height: int
        :param method: resize method
        :type resize: int
        :return new_image: Resized image
        :rtype new_image: bytearray
        """
        _ = self
        new_size = None
        (img_height, img_width) = image.shape[:2]

        if width is None and height is None:
            return image
        if width is None:
            aspect = height / float(img_height)
            new_size = (int(img_width * aspect), height)
        else:
            aspect = width / float(img_width)
            new_size = (width, int(img_height * aspect))
        new_image = cv2.resize(image, new_size, interpolation = method)
        return new_image


    def is_alive(self, device):
        """Safely checks if the thread corresponding to the specified
           camera device is alive/running or not

        :param device: device identifier
        :type device: string
        :return is_alive: Whether thread is running or not
        :rtype is_alive: boolean
        """
        self.mutex.acquire()
        alive = self.device_threads[device][Util.ALIVE]
        self.mutex.release()
        return alive


    def streamer_thread(self, device, image_width=None, image_height=None):
        # pylint disable=useless-return
        """ The thread that reads frames from the camera device

        :param device: device identifier
        :type device: string
        :param image_width: frame width
        :type image_width: int
        :param image_height: frame height
        :type image_height: int
        """
        cap = None
        try:
            dev = int(device) if device.isnumeric() else device
            cap = cv2.VideoCapture(dev)
            while self.is_alive(device) and cap and cap.isOpened():
                _, frame = cap.read()
                if frame is None:
                    time.sleep(0.2)
                    continue

                frame = self.resize_image(frame, image_width, image_height)
                # encode the frame in JPEG format
                (_, encoded_image) = cv2.imencode(".jpg", frame)
                if encoded_image is None:
                    self.util.logger.info("Warning: encoding image -> " \
                            "jpeg failed. Skipping frame")
                    continue
                # Convert to byte array along with headers for streaming
                bframe = b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +  \
                            bytearray(encoded_image) + b'\r\n'
                self.mutex.acquire()
                self.device_threads[device][Util.FRAMES] = bframe
                self.mutex.release()
            # Close video capture
            if cap and cap.isOpened():
                cap.release()
            # If thread was not signalled to terminate, then the camera capture
            # must have closed due to an error. Remove the thread and device info
            # from the list
            if self.is_alive(device):
                time.sleep(1)
                self.mutex.acquire()
                del self.device_threads[device]
                self.mutex.release()
                self.util.logger.error("Error while streaming camera %s", device)
        except Exception as exception:
            if cap and cap.isOpened():
                cap.release()
            if self.mutex.locked():
                self.mutex.release()
            self.util.logger.error("Error while streaming camera %s: %s",
                device, exception)


    def read_frame(self, device):
        """ Grabs frame from the queue and yields it for streaming

        :param device: device identifier
        :type device: str
        :return frame: frame
        :rtype frame: bytearray
        """
        # Exit if device is invalid/stopped
        self.mutex.acquire()
        alive = device in self.device_threads
        self.mutex.release()
        frame = None
        while alive:
            self.mutex.acquire()
            # Check for parent (thread) termination signal
            alive = self.device_threads[device][Util.ALIVE]
            frame = self.device_threads[device][Util.FRAMES]
            self.mutex.release()
            yield frame

    def start(self, devices, width, height):
        """Starts the specified cameras

        :param devices: list of camera devie names
        :type devices: [str]
        :param width: width of frame in pixels
        :type width: int
        :param height: height of frame in pixels
        :type height: int
        """
        self.mutex.acquire()
        # Launch thread for each device
        dts = self.device_threads
        for device in devices:
            if device not in dts:
                dts[device] = {}
                dts[device][Util.THREAD] = Thread(
                        target=self.streamer_thread,
                        args=(device, width, height))
                dts[device][Util.ALIVE] = True
                dts[device][Util.FRAMES] = None
                dts[device][Util.THREAD].start()
            else:
                self.util.logger.info("Warning: camera device %s already running", device)
        self.mutex.release()


    def stop(self, devices):
        """Stops the specified cameras

        :param devices: list of camera devie names
        :type devices: [str]
        """
        self.mutex.acquire()
        # When no devices are provided, assume all devices
        if len(devices) == 0:
            devices = list(self.device_threads)
        # Signal all the provided devices threads to exit
        for device in devices:
            if device in self.device_threads:
                self.device_threads[device][Util.ALIVE] = False
            else:
                self.util.logger.info("Warning: camera device %s not running",
                        device)
        # Make a safe copy of the list
        threads = self.device_threads.copy()
        self.mutex.release()
        # Wait for all the signalled theads to exit
        for device in devices:
            if device in threads:
                threads[device][Util.THREAD].join()
                self.mutex.acquire()
                if device in self.device_threads:
                    del self.device_threads[device]
                self.mutex.release()


    def get_status(self, devices = None):
        """ Gets the current status of all provided camera devices

        :param devices: list of camera device ids
        :type devices: list of strings
        :return camera_status: camera status
        :rtype camera_status: dict
        """
        camera_status = {}
        self.mutex.acquire()
        if devices is None or len(devices) == 0:
            for device in self.device_threads:
                camera_status[device] = "Running"
        else:
            for device in devices:
                if device in self.device_threads:
                    camera_status[device] = "Running"
                else:
                    camera_status[device] = "Not Running"
        self.mutex.release()
        return camera_status


    def parse_v4l2_ctrl_list(self, text):
        """ Parses output of v4l2-ctl -l

        :param text: output of v4l2-ctl -l
        :type text: str
        :return json dict of params and values
        :rtype: dict
        """
        data = {}
        status = True
        error_detail = ""
        try:
            for line in text.splitlines():
                tokens = line.split()
                if len(tokens) <= 4:
                    continue
                key = tokens[0]
                data[key] = {}
                data[key]["type"] = tokens[2][1:-1]
                print(tokens)
                for token in tokens[4:]:
                    key_value = token.split("=")
                    data[key][key_value[0]] = key_value[1]
        except ValueError as value_error:
            status = False
            data = {}
            error_detail = "Failed to parse v4l2 output: {}".format(value_error)
            self.util.logger.error(error_detail)
        return status, error_detail, data


    def set_config(self, configs):
        """ Sets the configurations for specified camera devices

        :param config: configuration to set
        :param config: dict
        :return current_config: configuration info
        :rtype current_config: dict
        """
        status = True
        error_detail = ""
        for device in configs:
            params = configs[device]
            for param in params:
                status, error_detail, result = self.util.os_command(
                        "v4l2-ctl -d {} -c {}={}".format(
                            device, param, params[param]))
                self.util.logger.debug("v4l2-ctl output: %s", result)
                if status is False:
                    self.util.logger.error(
                            "Failed to set camera %s config - %s=%s: %s",
                            device, param, params[param], error_detail)
        return status, error_detail


    def get_config(self, configs):
        """ Gets the configurations for specified camera devices

        :param config: configuration to fetch
        :param config: dict
        :return current_config: configuration info
        :rtype current_config: dict
        """
        data = {}
        error_detail = ""
        failed_devices = []
        for device in configs:
            status, error_detail, result = self.util.os_command("v4l2-ctl -d {} -l".format(device))
            self.util.logger.info("v4l2-ctl result: %s", result)
            if status is False:
                data[device] = {}
                failed_devices.append(device)
                continue
            status, _, result_json = self.parse_v4l2_ctrl_list(result)
            if status is False:
                data[device] = {}
                failed_devices.append(device)
                continue
            try:
                params = configs[device]
                if len(params) == 0 or params[0] == "*":
                    data[device] = result_json
                    continue
                data[device] = {}
                for param in params:
                    if param in result_json:
                        data[device][param] = result_json[param]
            except Exception as exception:
                status = False
                failed_devices.append(device)
                self.util.logger.error(
                        "Failed to validate params for device %s: %s",
                        device, exception)
                break


        if len(failed_devices) > 0:
            status = False
            error_detail = "get config failed for thse devices: {}".format(
                failed_devices)
        return status, error_detail, data
