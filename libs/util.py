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

""" Module that provides generic utility functions """

import os
import json
import subprocess as sp
import logging
import shlex

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
        self.logger = logging.getLogger("DeploymentToolBackend")
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
        _ = self
        try:
            data = None
            status = True
            error_detail = ""
            with open(path, "r", encoding='utf8') as filehandle:
                data = filehandle.read()
            if isinstance(data, (bytearray, bytes)):
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

            with open(path, mode, encoding="utf8") as filehandle:
                if isinstance(data, str):
                    filehandle.write(data)
                elif isinstance(data, (bytearray, bytes)):
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
            path = self.EII_CONFIG_PATH
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
            path = self.EII_CONFIG_PATH
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
        out = b''
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
        return status, error_detail, out.decode("utf-8")


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


    def make_response_json(self,status, data, error_detail):
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
        _ = self
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
