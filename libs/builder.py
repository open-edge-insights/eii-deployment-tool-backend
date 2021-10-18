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

""" Module for handling configuration, build and provisioning """

import os
import json
from .util import Util

class Builder:
    """This class will have functions related to build and provisioning

    """
    def __init__(self):
        self.util = Util()


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
            with open(path, "w", encoding="utf8") as fyml:
                fyml.write("AppContexts:\n")
                for component in components:
                    fyml.write("- {}\n".format(component))
        except Exception as exception:
            error_detail = "exception while creating usecase yml file: {}".format(
                    exception)
            self.util.logger.error(error_detail)
            status = False
        return status, error_detail


    def do_generate_config(self, components, instances):
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
        status, error_detail = self.create_usecase_yml_file(
                components, self.util.TEMP_USECASE_FILE_PATH)
        if not status:
            return False, error_detail, None
        vi_exists = False
        for component in components:
            if component.find("VideoIngestion") == 0:
                vi_exists = True
                break
        if instances > 1 and vi_exists is False:
            error_detail = "unsupported multi-instance configuration"
            self.util.logger.error(error_detail)
            return False, error_detail, None

        os.chdir(self.util.EII_BUILD_PATH)
        # Save old config
        status, error_detail, old_config = self.util.get_consolidated_config()
        if instances > 1:
            status, error_detail, out = self.util.shell('python3 builder.py -f {} -v{}' \
                    .format(self.util.TEMP_USECASE_FILE_PATH, instances))
        else:
            status, error_detail, out = self.util.shell('python3 builder.py -f {}' \
                    .format(self.util.TEMP_USECASE_FILE_PATH))
        self.util.store_file(self.util.LOGFILE, out, True)
        status, error_detail, new_config = self.util.get_consolidated_config()
        if not status:
            error_detail = "error: failed to generate eii_config"
            self.util.logger.error(error_detail)
            return False, error_detail, None

        # Apply saved config to the new config
        for component in old_config:
            if component in new_config:
                new_config[component] = old_config[component]

        status, error_detail = self.util.store_consolidated_config(new_config)
        return status, error_detail, new_config


    def do_get_config(self, components):
        """Generate the consolidated config file

        :param components: list of component names
        :type name: [str]
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: config
        :rtype: dict
        """
        status = True
        config = {}
        status, error_detail, cconfig = self.util.get_consolidated_config()
        if status:
            for config_key in cconfig:
                try:
                    tokens = config_key.split("/")
                    key = tokens[1]
                    subkey = tokens[2]

                    if key in ["GlobalEnv", "EtcdUI"] or key not in components:
                        continue
                    if key not in config:
                        config[key] = {subkey: cconfig[config_key]}
                    else:
                        config[key].update({subkey: cconfig[config_key]})
                except Exception as exception:
                    error_detail = "Parse error. Invalid EII config file!: {}".format(
                                                exception)
                    self.util.logger.error(error_detail)
                    status = False
                    config = {}
                    break

        return status, error_detail, config


    def do_set_config(self, config):
        """Updates the consolidated config file, with the provided config

        :param config: configuration to update
        :type config: dict
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        status = True
        error_detail = ""
        print(config)
        try:
            status, error_detail, eii_config_str = self.util.load_file(
                    self.util.EII_CONFIG_PATH)
            if status:
                eii_config = json.loads(eii_config_str)
                for service in config:
                    eii_config["/{}/config".format(service)] = config[service]["config"]
                    eii_config["/{}/interfaces".format(service)] = \
                        config[service]["interfaces"]
                    status, error_detail = self.util.store_consolidated_config(eii_config)
        except Exception as exception:
            error_detail = "Exception while updating EII config: {}".format(exception)
            self.util.logger.error(error_detail)
            status = False

        return status, error_detail
