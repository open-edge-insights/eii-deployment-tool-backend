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

import sys
import os
import time
import json
import subprocess as sp
import logging
import secrets
import shlex
from threading import Thread, Lock
from typing import List, Optional
import cv2
import uvicorn
from fastapi import FastAPI, Response, HTTPException, Depends
from fastapi import status as HTTPStatus
from fastapi.security import APIKeyCookie
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.responses import StreamingResponse

DESCRIPTION = """
EII Deployment Tool Backend provides REST APIs to Configure, build and deploy your
usecases

## Authentication

* **Login**
* **Logout**

## Project

* **Project Load**
* **Project Store**
* **Get project list**

## Config

* **Generate Config**

## Camera

* **Start Camera**
* **Stop Camera**
* **Stream Camera**

"""
app = FastAPI(
    title = "Intel© Edge Insights for Industrial (EII) REST APIs",
    description = DESCRIPTION,
    version = "0.0.1"
)
session_cookie = APIKeyCookie(name="session")

class Util:
    """
    Class for various generic utility functions

    """

    IE_DIR = "/app/IEdgeInsights/"
    EII_CONFIG_PATH = IE_DIR + "build/provision/config/eii_config.json"
    EII_PROJECTS_PATH = IE_DIR + "build/projects/"
    EII_BUILD_PATH = IE_DIR + "build"
    TEMP_USECASE_FILE_PATH = EII_BUILD_PATH + "/.usecasex.yml"
    LOGFILE = IE_DIR + "/build/console.log"
    JSON_EXT = ".json"

    def __init__(self):
        error = None
        # Initilize logging
        env_log_level=os.environ.get("LOG_LEVEL", "INFO")

        if env_log_level == "DEBUG":
            logging_format = "[%(funcName)(): %(lineno)s  ] %(message)s"
            logging_level = logging.DEBUG
        elif env_log_level == "INFO":
            logging_format = "%(message)s"
            logging_level = logging.INFO
        elif env_log_level == "ERROR":
            logging_format = "%(message)s"
            logging_level = logging.ERROR
        else:
            logging_format = "%(message)s"
            logging_level = logging.INFO
            error = "Invalid log level {}. Resetting log level to INFO".format(
                    env_log_level)

        logging.basicConfig(level=logging_level, format=logging_format)
        self.logger = logging.getLogger(__name__)
        if error:
            self.logger.ERROR(error)


    def load_file(self, path):
        """Reads a file and return its contents as utf-8 string

        :param path: file path
        :type path: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: file contents
        :rtype: str
        """
        try:
            data = None
            status = True
            error_detail = ""
            with open(path, "r", encoding='utf8') as filehandle:
                data = filehandle.read()
            if isinstance(data, bytearray) or isinstance(data, bytes):
                data = data.decode('utf-8')
        except Exception as exception:
            status = False
            error_detail = "failed to read file: [{}]: {}".format(path, exception)
        return status, error_detail, data


    def store_file(self, path, data, overwrite=False):
        """Writes the specified data to file

        :param path: file name
        :type path: str
        :param data: data to write
        :type data: str/bytearray
        :param overwrite: Whether to replace existing file
        :type overwrite: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        try:
            error_detail = ""
            mode = None
            status = True
            if overwrite:
                mode = "w"
            else:
                mode = "a"

            with open(path, mode) as filehandle:
                if isinstance(data, str):
                    filehandle.write(data)
                elif isinstance(data, bytearray) or isinstance(data, bytes):
                    filehandle.write(data.decode('utf-8'))
                else:
                    status = False
                    error_detail = "Internal error: Unhandled type: {}".format(type(data))
                    self.logger.error(error_detail)
        except Exception as exception:
            status = False
            error_detail = "Failed to write file: [{}]: {}".format(path, exception)
            self.logger.error(error_detail)

        return status, error_detail


    def get_consolidated_config(self, path = None):
        """Get specified/current config data

        :param path: path for the config file
        :type path: str
        :return: status
        :rtype: bool
        :return: error description
        :rtype: str
        :return: config data
        :rtype: dict
        """
        status = False
        eii_config = None

        if path is None:
            path = util.EII_CONFIG_PATH
        try:
            status, error_detail, eii_config_str = self.load_file(path)
            if status:
                eii_config = json.loads(eii_config_str)

        except Exception as exception:
            status = False
            error_detail = "exception while reading eii_config.json: {}".format(
                    exception)
            self.logger.error(error_detail)

        return status, error_detail, eii_config


    def store_consolidated_config(self, config, path = None):
        """Write config data to the specified/current config file

        :param config: config data
        :type config: dict
        :param path: path to store the config file
        :type path: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        status = False
        if path is None:
            path = util.EII_CONFIG_PATH
        try:
            status, error_detail = self.store_file(path, json.dumps(config, indent=4), True)
        except Exception as exception:
            error_detail = "exception while writing {}: {}".format(path, exception)
            self.logger.error(error_detail)

        return status, error_detail


    def shell(self, cmd):
        """Execute a shell command and return the output
        :param cmd: shell command
        "type cmd: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: command output
        :rtype: str
        """
        out = ""
        status = False
        error_detail = ""
        try:
            out = sp.check_output(
                     shlex.split(cmd),
                     shell=False)
            status = True
        except Exception as exception:
            error_detail = "error while executing {}: {}".format(cmd, exception)
            self.logger.error(error_detail)
        return status, error_detail, out


    def scan_dir(self, dir_path):
        """Returns the list of files and directories in the specified path

        :param dir_path: path to directory
        :type dir_path: str
        :return: status
        :rtype: bool
        :return: error description
        :rtype: str
        :return: list of files and directories
        :rtype: dict[(str,list[str])
        """
        status = True
        error_detail = ""
        file_list = {"files": [], "dirs": []}
        try:
            for (_, dirnames, filenames) in os.walk(dir_path):
                file_list["files"].extend(filenames)
                file_list["dirs"].extend(dirnames)
                break
        except Exception as exception:
            error_detail = "failed to list files at {}: {}".format(dir_path, exception)
            self.logger.error(error_detail)
            status = False
        return status, error_detail, file_list


    def create_usecase_yml_file(self, components, path):
        """Creates a usecase yml file

        :param components: list of component names
        :type components: [str]
        :param path: path to usecase file
        :type path: str
        :return: status
        :rtype: bool
        :return: error description
        :rtype: str
        """
        status = True
        error_detail = ""
        try:
            with open(path, "w") as fyml:
                fyml.write("AppContexts:\n")
                for component in components:
                    fyml.write("- {}\n".format(component))
        except Exception as exception:
            error_detail = "exception while creating usecase yml file: {}".format(
                    exception)
            self.logger.error(error_detail)
            status = False
        return status, error_detail


class Authentication():
    """
    Class for grouping authentication related functions and data
    """
    tokens = {}
    def get_user_credentials(username):
        """Returns the login credentials for the give username

        :param username: Username
        :type username: str
        :return: user login credentails
        "rtype: ()
        """
        for tup in CREDS:
            if username in tup[0]:
                return tup
        return None


    def validate_token(token: str = Depends(session_cookie)):
        """Checks whether the given token is valid

        :param token: session token returned by /eii/ui/login API
        :type token: str
        :return: Whether token is valid or not
        :rtype: bool
        """
        if token not in Authentication.tokens:
            raise HTTPException(
                status_code=HTTPStatus.HTTP_403_FORBIDDEN,
                detail="Invalid authentication"
            )
        return token


class Project():
    def do_load_project(name):
        """Returns the config data for an existing project

        :param name: name for the project
        :type name: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: config data
        :rtype: dict
        """
        path = util.EII_PROJECTS_PATH + name + util.JSON_EXT
        status, error_detail, config = util.get_consolidated_config(path)
        if status is False:
            util.logger.error("Failed to load project {}: {}".format(name, error_detail))
        return status, error_detail, config


    def do_store_project(name, replace = True):
        """Create config file for the current unsaved project

        :param name: name for the project
        :type name: str
        :param replace: Whether replace existing file
        :type replace: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        status, error_detail, config = util.get_consolidated_config()
        if status:
            path = util.EII_PROJECTS_PATH + name + util.JSON_EXT
            if replace is False and os.path.isfile(path):
                util.logger.error("Error: destination file {} already exists!".format(path))
                status = False
            else:
                status, error_detail = util.store_consolidated_config(config, path)
        return status, error_detail


    def do_list_projects():
        """Get list of project files

        :param name: name for the project
        :type name: string
        :param replace: Whether replace existing file
        :type replace: boolean
        :return: status
        :rtype: boolean
        :return: list of projects
        :rtype: list of str
        """
        status, error_detail, dir_info = util.scan_dir(util.EII_PROJECTS_PATH)
        if status:
            projects = [ p[:-5] for p in dir_info["files"] if p.endswith(util.JSON_EXT) ]
        else:
            projects = None
        return status, error_detail, projects


class Project():
    def do_load_project(name):
        """Returns the config data for an existing project

        :param name: name for the project
        :type name: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: config data
        :rtype: dict
        """
        path = util.EII_PROJECTS_PATH + name + util.JSON_EXT
        return util.get_consolidated_config(path)


    def do_store_project(name, replace = True):
        """Create config file for the current unsaved project

        :param name: name for the project
        :type name: str
        :param replace: Whether replace existing file
        :type replace: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        status, error_detail, config = util.get_consolidated_config()
        if status:
            path = util.EII_PROJECTS_PATH + name + util.JSON_EXT
            if replace is False and os.path.isfile(path):
                util.logger.error("Error: destination file {} already exists!".format(path))
                status = False
            else:
                status, error_detail = util.store_consolidated_config(config, path)
        return status, error_detail


    def do_list_projects():
        """Get list of project files

        :param name: name for the project
        :type name: string
        :param replace: Whether replace existing file
        :type replace: boolean
        :return: status
        :rtype: boolean
        :return: list of projects
        :rtype: list of str
        """
        status = False
        status, error_detail, dir_info = util.scan_dir(util.EII_PROJECTS_PATH)
        if status:
            projects = [ p[:-5] for p in dir_info["files"] if p.endswith(util.JSON_EXT) ]
        else:
            projects = None
        return status, error_detail, projects


class Camera:
    """
    Class for managing camera streaming

    """

    def __init__(self):
        self.device_threads = {}
        self.mutex = Lock()

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
        new_size = None
        (h, w) = image.shape[:2]

        if width is None and height is None:
            return image
        if width is None:
            aspect = height / float(h)
            new_size = (int(w * aspect), height)
        else:
            aspect = width / float(w)
            new_size = (width, int(h * aspect))
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
        alive = self.device_threads[device]["alive"]
        self.mutex.release()
        return alive


    def streamer_thread(self, device, image_width=None, image_height=None):
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
                (_, encodedImage) = cv2.imencode(".jpg", frame)
                if encodedImage is None:
                    util.logger.info("Warning: encoding image -> " \
                            "jpeg failed. Skipping frame")
                    continue
                # Convert to byte array along with headers for streaming
                bframe = b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' +  \
                            bytearray(encodedImage) + b'\r\n'
                self.mutex.acquire()
                self.device_threads[device]["frames"] = bframe
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
                util.logger.error("Error while streaming camera {}".format(
                    device))
        except Exception as exception:
            if cap and cap.isOpened():
                cap.release()
            if self.mutex.locked():
                self.mutex.release()
            util.logger.error("Error while streaming camera {}: {}".format(
                device, exception))


    # Called by thread function
    def generate_frame(self, device):
        """ Grabs frame from the queue and yields it for streaming

        :param device: device identifier
        :type device: string
        :return frame: frame
        :rtype frame: bytearray
        """
        # Exit if device is invalid/stopped
        self.mutex.acquire()
        alive = True if device in self.device_threads else False
        self.mutex.release()
        frame = None
        while alive:
            self.mutex.acquire()
            # Check for parent (thread) termination signal
            alive = self.device_threads[device]["alive"]
            frame = self.device_threads[device]["frames"]
            self.mutex.release()
            yield frame


    def get_camera_status(self, devices = None):
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

##############################################################################
def do_generate_config(components, instances):
    """Generate the consolidated config file

    :param components: list of component names
    :type name: [str]
    :param instances: no. of instances to generate
    :type instances: int
    :return: status of operation
    :rtype: bool
    :return: error description
    :rtype: str
    """
    status, error_detail = util.create_usecase_yml_file(components, util.TEMP_USECASE_FILE_PATH)
    if not status:
        return False, error_detail, None
    vi = False
    for component in components:
        if component.find("VideoIngestion") == 0:
            vi = True
            break
    if instances > 1 and vi is False:
        error_detail = "unsupported multi-instance configuration"
        util.logger.error(error_detail)
        return False, error_detail, None

    os.chdir(util.EII_BUILD_PATH)
    # Save old config
    status, error_detail, old_config = util.get_consolidated_config()
    #print(old_config)
    if instances > 1:
        status, error_detail, out = util.shell('python3 builder.py -f {} -v{}' \
                .format(util.TEMP_USECASE_FILE_PATH, instances))
    else:
        status, error_detail, out = util.shell('python3 builder.py -f {}' \
                .format(util.TEMP_USECASE_FILE_PATH))
    util.store_file(util.LOGFILE, out, True)
    status, error_detail, new_config = util.get_consolidated_config()
    if not status:
        error_detail = "error: failed to generate eii_config"
        util.logger.error(error_detail)
        return False, error_detail, None

    # Apply saved config to the new config
    for component in old_config:
        util.logger.error("Component: {}".format(component))
        if component in new_config:
            new_config[component] = old_config[component]

    status, error_detail = util.store_consolidated_config(new_config)
    return status, error_detail, new_config


def make_response_json(status, data, error_detail):
    """Common function for creating the response object for all the APIs

    :param status: status of repsonse
    :type status: bool
    :param data: response data
    :type data: stringified json
    :param errdesc: Description of error, if any
    :type error_detail: str
    :return: response data
    :rtype: json
    """

    if status is False or data in (None, ""):
        data = ""
    if status:
        error_detail = ""
        if not isinstance(data, str):
            data = json.dumps(data)

    #TBD
    console_log = ""
    response_json = {
                        "data": data,
                        "status_info": {
                            "status": status,
                            "error_detail": error_detail,
                            "console": console_log
                        }
                    }

    return response_json


##############################################################################
# Parmeter class definitions

class ProjectInfo(BaseModel):
    name: str = Field(..., title="Project name", max_length=128)
    class Config:
        schema_extra = {
            "example": {
                "name": "my_new_usecase"
            }
        }

class Credentials(BaseModel):
    username: str = Field(..., title="User name", max_length=32)
    password: str = Field(..., title="Password", max_length=32)
    class Config:
        schema_extra = {
            "example": {
                "username": "admin",
                "password": "admin@123"
            }
        }

class CameraInfo(BaseModel):
    devices: List[str] = Field(..., title="Camera devices list",
            min_items=0, max_items=32, max_length=64)
    width: Optional[int] = Field(None, title="Frame width", gt=0, lt=9999)
    height: Optional[int] = Field(None, title="Frame height", gt=0, lt=9999)
    class Config:
        schema_extra = {
            "example": {
                "devices": ["/dev/video0", "/dev/video1", "1", "2"],
                "width": 320,
                "height": 240
            }
        }

class ComponentInfo(BaseModel):
    names: List[str] = Field(..., title="Component names", max_length=64, min_items=1, max_items=96)
    instance_count: int = Field(..., title="Number of instances", gt=0, lt=33)
    class Config:
        schema_extra = {
            "example": {
                "names": ["VideoIngestion", "VideoAnalytics"],
                "instance_count": 2
            }
        }

class ResponseStatus(BaseModel):
    status: bool = Field(..., title="Error status")
    error_detail: str = Field(..., title="Error detail")
    console: str = Field(..., title="Console log")

class Response(BaseModel):
    data: str = Field(..., title="Response Data")
    status_info: ResponseStatus = Field(..., title="Response Status")

class Response403(BaseModel):
    detail: str

class Response204(BaseModel):
    detail: str

#
# API defnitions
#

@app.post('/eii/ui/login',
    response_model=Response,
    responses = {200: {"model": Response},
                 403: {"model": Response403}},
    description="Authenticates a user and creates secure session"
)
def login(creds: Credentials):
    user_cred = Authentication.get_user_credentials(creds.username)
    if user_cred is None or user_cred[1] != creds.password:
        raise HTTPException(
            status_code=HTTPStatus.HTTP_403_FORBIDDEN,
            detail="Invalid user or password")
    token = secrets.token_urlsafe(16)
    Authentication.tokens[token] = creds.username
    response = JSONResponse(
                    content=make_response_json(
                        True,
                        json.dumps(token),
                        ""
                    )
               )
    response.set_cookie("session",
                        token,
                        max_age=1800,
                        expires=1800)
    return response


@app.get("/eii/ui/logout",
    response_model=Response,
    responses = {200: {"model": Response},
                 403: {"model": Response403}},
    description="Logs out a user and delete the session"
)
def logout(token: str = Depends(Authentication.validate_token)):
    del Authentication.tokens[token]
    response = JSONResponse(
                    content=make_response_json(
                        True,
                        "Successfully logged out",
                        ""
                    )
               )
    response.delete_cookie("session")
    return response


@app.post('/eii/ui/project/load',
    response_model=Response,
    responses={200: {"model": Response}},
    description="Returns specified project config data"
)
def project_load(param: ProjectInfo, token: str=Depends(
        Authentication.validate_token)):
    _ = token
    status, error_detail, config = Project.do_load_project(param.name)
    return make_response_json(status, config, error_detail)


@app.post('/eii/ui/project/store',
    response_model=Response,
    responses={200: {"model": Response}},
    description="Saves current project config data to specified file"
)
def project_store(param: ProjectInfo, token: str=Depends(
        Authentication.validate_token)):
    _ = token
    status, error_detail = Project.do_store_project(param.name)
    return make_response_json(status, " ", error_detail)


@app.get('/eii/ui/project/list',
    response_model=Response,
    responses={200: {"model": Response}},
    description="Returns list of all the saved project config data"
)
# TODO:Disable authorization check for this API, as the same is not yet
# implemented in frontend
#def project_list(token: str=Depends(Authentication.validate_token)):
def project_list():
    status, error_detail, projects = Project.do_list_projects()
    return make_response_json(status, projects, error_detail)


@app.post('/eii/ui/config/generate',
    response_model=Response,
    responses={200: {"model": Response}},
    description="Generates default config for the specified components"
            " and returns the same"
)
def generate_config(param: ComponentInfo,
        token: str=Depends(Authentication.validate_token)):
    _ = token
    status, error_detail, config = do_generate_config(param.names,
            param.instance_count)
    return make_response_json(status, config, error_detail)


@app.post('/eii/ui/camera/{action}',
    response_model=Response,
    responses={200: {"model": Response}},
    description="Starts and stops the specified camera devices"
)
def camera_operate(action: str,
        cameraInfo: CameraInfo,
        token: str=Depends(Authentication.validate_token)):
    _ = token
    supported_actions = ["start", "stop", "status"]

    if action not in supported_actions:
        return make_response_json(False, "", \
                "Camera API FAILED. invalid arguments. expected any of {}" \
		.format(supported_actions))

    response = {}
    if action == "start":
        camera.mutex.acquire()
        # Launch thread for each device
        dts = camera.device_threads
        for device in cameraInfo.devices:
            if device not in dts:
                dts[device] = {}
                dts[device]["thread"] = Thread(
                        target=camera.streamer_thread,
                        args=(device, cameraInfo.width, cameraInfo.height))
                dts[device]["alive"] = True
                dts[device]["frames"] = []
                dts[device]["thread"].start()
            else:
                util.logger.info("Warning: camera device {} already running" \
                        .format(device))
        num_devices = len(cameraInfo.devices)
        camera.mutex.release()
        if num_devices == 0:
            response = make_response_json(False, "", "No camera devices specified")
        else:
            response = make_response_json(
                    True, camera.get_camera_status(),"")
    elif action == "stop":
        camera.mutex.acquire()
        devices = cameraInfo.devices
        # When no devices are provided, assume all devices
        if len(devices) == 0:
            devices = list(camera.device_threads)
        # Signal all the provided devices threads to exit
        for device in devices:
            if device in camera.device_threads:
                camera.device_threads[device]["alive"] = False
            else:
                util.logger.info("Warning: camera device {} not running" \
                        .format(device))
        # Make a safe copy of the list
        threads = camera.device_threads.copy()
        camera.mutex.release()
        # Wait for all the signalled theads to exit
        for device in devices:
            if device in threads:
                threads[device]["thread"].join()
                camera.mutex.acquire()
                del camera.device_threads[device]
                camera.mutex.release()
        response = make_response_json(True, camera.get_camera_status(), "")
    elif action == "status":
        camera.mutex.acquire()
        devices = cameraInfo.devices
        camera.mutex.release()
        response = make_response_json(True, camera.get_camera_status(devices), "")
    return response


@app.get('/eii/ui/camera/stream/{device}',
    response_class=StreamingResponse,
    description="Stream from the specified camera device"
)
async def camera_stream(device: str,
        token: str=Depends(Authentication.validate_token)):
    _ = token
    # make a safe copy of the global dict
    camera.mutex.acquire()
    threads = camera.device_threads.copy()
    camera.mutex.release()
    if device in threads:
        response = StreamingResponse(camera.generate_frame(device),
            media_type="multipart/x-mixed-replace;boundary=frame")
    else:
        # return 204 for invalid devices
        response = ('No data!', 204)
    return response



util = Util()
camera = Camera()

if __name__ == '__main__':
    if len(sys.argv) != 3 or int(sys.argv[1]) <= 0:
        util.logger.error("Error: Invalid/missing arguments!")
        sys.exit(0)

    server_port = int(sys.argv[1])
    CREDS = json.loads(sys.argv[2])

    util.logger.info("Starting REST server...")
    uvicorn.run(app, host="0.0.0.0", port=server_port)
