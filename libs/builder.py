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
from threading import Thread
import yaml
from .util import Util

class Builder:
    """This class will have functions related to build and provisioning

    """
    def __init__(self):
        self.util = Util()
        self.threads = {Util.BUILD: {}, Util.PROVISION: {}}
        for key in self.threads:
            self.threads[key][Util.ALIVE] = False


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
        if Util.is_busy():
            return False, "busy", ""

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
        v_str = "-v{}".format(instances) if instances > 1 else ""
        status, error_detail, _ = self.util.os_command_in_host(
                'cd {}/build && sudo -E python3 builder.py -f {} {}' \
                .format(self.util.host_eii_dir,
                    self.util.TEMP_USECASE_FILE_NAME, v_str))
        if not status:
            error_detail = "error: failed to generate eii_config"
            self.util.logger.error(error_detail)
            return False, error_detail, None
        status, error_detail, new_config = self.util.get_consolidated_config()
        if not status:
            error_detail = "error: failed to retrieve eii_config"
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
        if Util.is_busy():
            return False, "busy"

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

    def update_env_file(self, path, key, value):
        """Updates an env file with 'key=value' pairs

        :param path: path to the env file
        :type path: str
        :param key: key to look for
        :type key: str
        :param value: value to set
        :typevaluey: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        out = ""
        status = False
        error_detail = ""
        try:
            with open(path, "r", encoding="utf-8") as reader:
                for line in reader.readlines():
                    key_value = line.strip().split("=")
                    if status or key_value is None or key_value[0] != key:
                        out = out + line
                        continue
                    out = out + "{}={}\n".format(key, value)
                    status = True
            with open(path, "w", encoding="utf-8") as writer:
                writer.writelines(out)
        except Exception as exception:
            status = False
            error_detail = "error: FAILED to update env file: {}".format(
                    exception)
        return status, error_detail


    def provision_thread(self):
        """Thread for Provisioning

        """
        self.util.logger.info("Provisioning...")
        status, error_out, _ = self.util.os_command_in_host(
                'cd {}/build/provision && sudo ./provision.sh ' \
                '../docker-compose.yml'.format(self.util.host_eii_dir))
        if not status:
            Util.set_state(Util.PROVISION, 0, "Failed")
            error_detail = "error: provisioning FAILED!: {}".format(error_out)
            self.util.logger.error(error_detail)
        else:
            Util.set_state(Util.PROVISION, 100, "Success")
        self.threads[Util.PROVISION][Util.ALIVE] = False


    def do_provision(self, dev_mode):
        """Do provision

        :param dev_mode: Whether DEV_MODE need to be set to "true" or "false"
        :type dev_mode: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        if Util.is_busy():
            return False, "busy", ""

        Util.set_state(Util.PROVISION, 0)
        status = False
        error_detail = ""
        self.util.logger.info("Setting provisioning mode...")
        # Set DEV_MODE
        key = "DEV_MODE"
        value = "true" if dev_mode else "false"
        env_path = self.util.EII_BUILD_PATH + '/.env'
        status, error_out = self.update_env_file(env_path, key, value)
        if status is False:
            error_detail = "error: FAILE to set DEV_MODE in .env!: {}".format(
                    error_out)
            self.util.logger.error(error_detail)
            Util.set_state(Util.PROVISION, 0, "Failed")
            return status, error_detail, ""

        Util.set_state(Util.PROVISION, 10)
        self.threads[Util.PROVISION][Util.THREAD] = Thread(target=self.provision_thread)
        self.threads[Util.PROVISION][Util.ALIVE] = True
        self.threads[Util.PROVISION][Util.THREAD].start()
        status = True
        return status, error_detail, ""


    def get_services_from_docker_compose_yml(self, yml):
        """Get list of services from specified docker-compose.yml file

        :param yml: path to docker-compose.yml
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :type yml: str
        """
        status = False
        services = []
        error_detail = ""
        try:
            with open(yml, 'r', encoding='utf-8') as reader:
                data = yaml.safe_load(reader)
                if "services" not in data:
                    self.util.logger.error('Invalid yaml file: No services defined')
                    return None
                for name in data["services"]:
                    services.append(name)
            status = True
        except Exception as exception:
            error_detail = "failed to get services from {}: {}".format(yml, exception)
            self.util.logger.error(error_detail)
        return status, error_detail, services


    def builder_thread(self, services, no_cache):
        """Thread for building

        :param services: List of services to be built or "*" for all services
        :type services: [str]
        :param no_cache: whether to use --no-cache option with build
        :type no_cache: bool
        """
        no_cache_str = "--no-cache" if no_cache else ""
        if services[0] == "*":
            status, error_out, services_list = \
                self.get_services_from_docker_compose_yml(self.util.EII_BUILD_PATH + \
                        '/docker-compose-build.yml')
            if status is False:
                self.util.logger.error("Build FAILED: failed to parse yml file: %s",
                            error_out)
                Util.set_state(Util.BUILD, 0, "Failed")
                self.threads[Util.BUILD][Util.ALIVE] = False
                return
        else:
            services_list = services

        num_services = len(services_list)
        i = 0
        self.util.store_file(self.util.LOGFILE, "", True)
        for service in services_list:
            if not self.threads[Util.BUILD][Util.ALIVE]:
                break
            status, error_out, _ = self.util.os_command_in_host(
                'cd {}/build && docker-compose -f docker-compose-build.yml ' \
                'build {} {}'.format(self.util.host_eii_dir, no_cache_str, service))
            if status is False:
                Util.set_state(Util.BUILD, 0, "Failed")
                self.util.logger.error("Build FAILED: %s", error_out)
                self.threads[Util.BUILD][Util.ALIVE] = False
                return
            i = i + 1
            Util.set_state(Util.BUILD, int((i*100)/num_services))
        Util.set_state(Util.BUILD, 100, "Success")
        self.threads[Util.BUILD][Util.ALIVE] = False


    def do_build(self, services, no_cache):
        """Do build

        :param services: List of services to be built or "*" for all services
        :type services: [str]
        :param no_cache: whether to use --no-cache option with build
        :type no_cache: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        if Util.is_busy():
            return False, "busy", ""

        self.util.logger.info("Building...")
        self.threads[Util.BUILD][Util.THREAD] = Thread(target=self.builder_thread,
                args=(services, no_cache))
        self.threads[Util.BUILD][Util.ALIVE] = True
        self.threads[Util.BUILD][Util.THREAD].start()
        return True, "", ""
