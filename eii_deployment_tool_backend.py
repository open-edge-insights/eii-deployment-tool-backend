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

""" Main module of Deployment tool backend """

import sys
import json
from typing import List, Optional, Dict
import uvicorn
from starlette.status import (HTTP_403_FORBIDDEN, HTTP_404_NOT_FOUND)
from starlette.responses import StreamingResponse
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from libs.project import Project
from libs.util import Util
from libs.authentication import Authentication
from libs.camera import Camera
from libs.builder import Builder

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
* **Get Config**
* **Set Config**

## Camera

* **Start Camera**
* **Stop Camera**
* **Stream Camera**
* **Get Camera Config**
* **Set Camera Config**

## UDF

* **List files, directories*

## Provision & Build

* **Provision**
* **Build**
* **Get status**


"""
app = FastAPI(
    title = "Intel© Edge Insights for Industrial (EII) REST APIs",
    description = DESCRIPTION,
    version = "0.0.1"
)

#
# Instantiate classes
#
auth = Authentication()
util = Util()
project = Project()
camera  = Camera()
builder = Builder()

#
# Parmeter class definitions
#

class ProjectInfo(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines Project information param

    """
    name: str = Field(..., title="Project name", min_length=1,max_length=128)
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "name": "my_new_usecase"
            }
        }


class Credentials(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines credential param for authentication/login

    """
    username: str = Field(..., title="User name", min_length=1, max_length=32)
    password: str = Field(..., title="Password", min_length=1, max_length=32)
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "username": "admin",
                "password": "admin@123"
            }
        }


class CameraInfo(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines camaera info param to use with */camera/* APIs

    """
    devices: List[str] = Field(..., title="Camera devices list",
            min_items=0, max_items=32, max_length=64)
    width: Optional[int] = Field(None, title="Frame width", gt=0, lt=9999)
    height: Optional[int] = Field(None, title="Frame height", gt=0, lt=9999)
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "devices": ["0"],
                "width": 320,
                "height": 240
            }
        }


class CameraConfigsGet(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines camera config param to use with */camera/config/get API

    """
    configs: Dict = Field(..., title="Camera device configuration get")
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "configs": {
                    "0": ["*"],
                    "1": [
                        "brightness",
                        "contrast"
                    ]
                }
            }
        }


class CameraConfigsSet(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines camera config param to use with */camera/config/set API

    """
    configs: Dict = Field(..., title="Camera device configuration set")
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "configs": {
                    "0": {
                        "gamma": "100"
                    },
                    "1": {
                        "brightness": "5",
                        "contrast": "6"
                    }
                }
            }
        }


class ComponentList(BaseModel): # pylint: disable=too-few-public-methods
    """ Class that defines component list param to use with */config/* APIs

    """
    names: List[str] = Field(..., title="Component names", min_length=1, max_length=64,
                            min_items=1, max_items=96)
    class Config: # pylint: disable=too-few-public-methods
        """ example data """
        schema_extra = {
            "example": {
                "names": ["VideoIngestion", "VideoAnalytics"]
            }
        }


class ComponentInfo(BaseModel): # pylint: disable=too-few-public-methods
    """ Class that defines component info param to use with */config/* APIs

    """
    names: List[str] = Field(..., title="Component names", min_length=1, max_length=64,
            min_items=1, max_items=96)
    instance_count: int = Field(..., title="Number of instances", gt=0, lt=33)
    class Config: # pylint: disable=too-few-public-methods
        """example data """
        schema_extra = {
            "example": {
                "names": ["VideoIngestion", "VideoAnalytics"],
                "instance_count": 2
            }
        }


class ListFilesInfo(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines param to use with */files/list/* API

    """
    path: str = Field(..., title="Directory path", min_length=1, max_length=512)
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "path": "/common/video/udfs/"
            }
        }


class ProvisionInfo(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines param to use with */provision/ API

    """
    dev_mode: bool = Field(..., title="Is DEV_MODE enabled")
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "dev_mode": True
            }
        }


class BuildInfo(BaseModel): # pylint: disable=too-few-public-methods
    """Class that defines param to use with */build/ API
       Services param contains the list of services to be built or "*"
       if all services in the usecase needs to be built

    """
    services: List[str] = Field(..., title="Services to build")
    no_cache: Optional[bool] = Field(False, title="enable --no-cache")
    class Config: # pylint: disable=too-few-public-methods
        """example data
        """
        schema_extra = {
            "example": {
                "services": ["*"],
                "no_cache": False
            }
        }


#
# Response class definitions
#
class Response200Status(BaseModel): # pylint: disable=too-few-public-methods
    """ Class that defines the status field of successful response

    """
    status: bool = Field(..., title="Error status")
    error_detail: str = Field(..., title="Error detail")
    console: str = Field(..., title="Console log")


class Response200(BaseModel): # pylint: disable=too-few-public-methods
    """ Class that defines a successful response

    """
    data: str = Field(..., title="Response Data")
    status_info: Response200Status = Field(..., title="Response Status")


class Response403(BaseModel): # pylint: disable=too-few-public-methods
    """ Class that defines Authentication error response

    """
    detail: str


class Response404(BaseModel): # pylint: disable=too-few-public-methods
    """ Class that defines a 404 response """
    detail: str

#
# API defnitions
#

@app.post('/eii/ui/login',
    response_model=Response200,
    responses = {200: {"model": Response200},
                 403: {"model": Response403}},
    description="Authenticates a user and creates secure session"
)
def login(creds: Credentials):
    """Authenticates a user and creates secure session

    :param creds: user crdentails
    :type creds: dict
    :return response: API response
    :rtype Response200
    """
    user_cred = auth.get_user_credentials(creds.username, CREDS)
    if user_cred is None or user_cred[1] != creds.password:
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="Invalid user or password")
    token = auth.generate_token(creds.username)
    response = JSONResponse(
                    content=util.make_response_json(
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
    response_model=Response200,
    responses = {200: {"model": Response200},
                 403: {"model": Response403}},
    description="Logs out a user and delete the session"
)
def logout(token: str = Depends(Authentication.validate_session)):
    """Logs out a user and delete the session

    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    del auth.tokens[token]
    response = JSONResponse(
                    content=util.make_response_json(
                        True,
                        "Successfully logged out",
                        ""
                    )
               )
    response.delete_cookie("session")
    return response


@app.post('/eii/ui/project/load',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Returns specified project config data"
)
def project_load(proj: ProjectInfo, token: str=Depends(
        Authentication.validate_session)):
    """Returns specified project config data

    :param proj: project info
    :type token: ProjectInfo
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, config = project.do_load_project(proj.name)
    return util.make_response_json(status, config, error_detail)


@app.post('/eii/ui/project/store',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Saves current project config data to specified file"
)
def project_store(proj: ProjectInfo, token: str=Depends(
        Authentication.validate_session)):
    """Stores the specified project config data

    :param proj: project info
    :type token: ProjectInfo
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail = project.do_store_project(proj.name)
    return util.make_response_json(status, " ", error_detail)


@app.get('/eii/ui/project/list',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Returns list of all the saved project config data"
)
def project_list(
        token: str=Depends(Authentication.validate_session)
        ):
    """"Returns list of all the saved project config data"

    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, projects = project.do_list_projects()
    return util.make_response_json(status, projects, error_detail)


@app.post('/eii/ui/config/generate',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Generates default config for the specified components"
            " and returns the same"
)
def generate_config(comp_info: ComponentInfo,
        token: str=Depends(Authentication.validate_session)):
    """Generates default config for the specified components
       and returns the same

    :param comp_info: component info
    :type token: ComponentInfo
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, config = builder.do_generate_config(
                                        comp_info.names,
                                        comp_info.instance_count)
    return util.make_response_json(status, config, error_detail)


@app.post('/eii/ui/config/get',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Get current config for the specified components"
)
def get_config(comp_list: ComponentList,
        token: str=Depends(Authentication.validate_session)):
    """Get current config for the specified components"

    :param comp_list: component list
    :type token: ComponentList
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, config = builder.do_get_config(comp_list.names)
    return util.make_response_json(status, config, error_detail)


@app.post('/eii/ui/config/set',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Get current config for the specified components"
)
def set_config(config: Dict,
        token: str=Depends(Authentication.validate_session)):
    """Get current config for the specified components"

    :param config:
    :type token: EiiConfig
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail = builder.do_set_config(config)
    return util.make_response_json(status, "", error_detail)

@app.post('/eii/ui/camera/config/get',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Get configurations of the specified camera devices"
)
def camera_config_get(camera_configs: CameraConfigsGet,
        token: str=Depends(Authentication.validate_session)):
    """"Get configuration info of the specified camera devices

    :param camera_configs: camera configurations
    :type token: CameraConfigsGet
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, configs = camera.get_config(camera_configs.configs)
    response = util.make_response_json(status, configs, error_detail)
    return response


@app.post('/eii/ui/camera/config/set',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Set configurations for the specified camera devices"
)
def camera_config_set(camera_configs: CameraConfigsSet,
        token: str=Depends(Authentication.validate_session)):
    """"Set configuration for the specified camera devices

    :param camera_configs: camera configurations
    :type token: CameraConfigsGet
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail = camera.set_config(camera_configs.configs)
    response = util.make_response_json(status, "", error_detail)
    return response


@app.post('/eii/ui/camera/{action}',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Starts, stops and return status of the specified camera devices"
)
def camera_operate(action: str,
        camera_info: CameraInfo,
        token: str=Depends(Authentication.validate_session)):
    """Starts, stops and return status of the specified camera devices"

    :param camera_info: camera info
    :type token: CameraInfo
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    supported_actions = ["start", "stop", "status"]

    if action not in supported_actions:
        return util.make_response_json(False, "", \
                "Camera API FAILED. invalid arguments. expected any of {}" \
		.format(supported_actions))

    response = {}
    if action == "start":
        camera.start(camera_info.devices, camera_info.width, camera_info.height)
        num_devices = len(camera_info.devices)
        if num_devices == 0:
            response = util.make_response_json(False, "", "No camera devices specified")
        else:
            response = util.make_response_json(
                    True, camera.get_status(),"")
    elif action == "stop":
        camera.stop(camera_info.devices)
        response = util.make_response_json(True,
                camera.get_status(), "")
    elif action == "status":
        response = util.make_response_json(True,
                camera.get_status(camera_info.devices), "")
    return response


@app.get('/eii/ui/camera/stream/{device}',
    response_class=StreamingResponse,
    description="Stream from the specified camera device"
)
async def camera_stream(device: str,
        token: str=Depends(Authentication.validate_session)):
    """description="Stream from the specified camera device"

    :param device: camera device name
    :type token: str
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    :return response: HTTP_404_NOT_FOUND status
    :rtype tuple
    """
    _ = token
    # make a safe copy of the global dict
    camera.mutex.acquire()
    threads = camera.device_threads.copy()
    camera.mutex.release()
    if device in threads:
        response = StreamingResponse(camera.read_frame(device),
            media_type="multipart/x-mixed-replace;boundary=frame")
    else:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND,
                detail="Device not found!")

    return response


@app.post('/eii/ui/files/list',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Get list of files and directories at the specified path"
)
def list_files(list_files_info: ListFilesInfo,
        token: str=Depends(Authentication.validate_session)):
    """"Get list of files and directories at the specified path

    :param list_files_info: param containing the directory path to search
    :type list_files_info: ListFilesInfo
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail,data = util.scan_dir(util.EII_DIR + list_files_info.path)
    response = util.make_response_json(status, data, error_detail)
    return response


@app.post('/eii/ui/provision',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Do Provisioning"
)
def provision(provision_info: ProvisionInfo,
        token: str=Depends(Authentication.validate_session)):
    """"Do provisioning

    :param dev_mode: Provision in dev mode ot prod mode
    :type dev_mode: bool
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, data = builder.do_provision(provision_info.dev_mode)
    response = util.make_response_json(status, data, error_detail)
    return response


@app.post('/eii/ui/build',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Do Provisioning"
)
def build(build_info: BuildInfo,
        token: str=Depends(Authentication.validate_session)):
    """"Do build

    :param build_info: services to build
    :type build_info: BuildInfo
    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    status, error_detail, data = builder.do_build(
            build_info.services, build_info.no_cache)
    response = util.make_response_json(status, data, error_detail)
    return response


@app.get('/eii/ui/status',
    response_model=Response200,
    responses={200: {"model": Response200}},
    description="Do Provisioning"
)
def getstatus(token: str=Depends(Authentication.validate_session)):
    """"Get status

    :param token: session token returned internally
    :type token: str
    :return response: API response
    :rtype Response200
    """
    _ = token
    data = Util.get_state()
    response = util.make_response_json(True, data, "")
    return response


if __name__ == '__main__':
    if len(sys.argv) != 3 or int(sys.argv[1]) <= 0:
        util.logger.error("Error: Invalid/missing arguments!")
        sys.exit(0)

    server_port = int(sys.argv[1])
    CREDS = json.loads(sys.argv[2])

    util.logger.info("Starting REST server...")
    app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=[]
            )
    uvicorn.run(app, host="0.0.0.0", port=server_port)
