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

""" Module for handling configuration, build and deploy """

import os
import json
import base64
from threading import Thread
from string import digits
import yaml
from eiiutil.util import Util as EiiUtil
from .util import Util


class Builder:
    """This class will have functions related to build and deploy

    """
    def __init__(self):
        self.util = Util()
        self.threads = {Util.BUILD: {}, Util.DEPLOY: {}}
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
                    fyml.write(f"- {component}\n")
        except Exception as exception:
            error_detail = f"exception while creating usecase yml file: {exception}"
            self.util.logger.error(error_detail)
            status = False
        return status, error_detail

    def merge_interfaces(self, target, source):
        """merge interfaces definitions

        :param target: target interface list
        :type target: [dict]
        :param source: source interface list
        :type source: [dict]
        """
        intf_types = ["Publishers", "Subscribers", "Servers", "Clients"]
        for intf_type in intf_types:
            if intf_type in source:
                if intf_type not in target:
                    target[intf_type] = source[intf_type]
                    continue
                for intf in source[intf_type]:
                    if intf not in target[intf_type]:
                        target[intf_type].append(source[intf_type])

    def do_generate_config(self, components, instances, dev_mode, reset):
        """Generate the consolidated config file

        :param components: list of component names
        :type name: [str]
        :param instances: no. of instances to generate
        :type instances: int
        :param dev_mode: whether dev or prod mode
        :type dev_mode: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        if Util.is_busy():
            return False, Util.BUSY, ""

        if len(components) > 0:
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

        # Set DEV_MODE
        key = "DEV_MODE"
        value = "true" if dev_mode else "false"
        env_path = self.util.EII_BUILD_PATH + '/.env'
        status, error_out = self.update_env_file(env_path, key, value)
        if status is False:
            error_detail = f"error: FAILE to set DEV_MODE in .env!: {error_out}"
            self.util.logger.error(error_detail)
            return status, error_detail, None

        os.chdir(self.util.EII_BUILD_PATH)
        if reset is False:
            # Save old config
            status, error_detail, old_config = self.util.get_consolidated_config()
        v_str = f"-v{instances}" if instances > 1 else ""
        status, error_detail, _ = self.util.os_command_in_host(
            'cd {}/build && sudo -E python3 builder.py -f {} {}'
            .format(self.util.host_eii_dir, self.util.TEMP_USECASE_FILE_NAME, v_str))
        if not status:
            error_detail = "error: failed to generate eii_config"
            self.util.logger.error(error_detail)
            return False, error_detail, None
        status, error_detail, new_config = self.util.get_consolidated_config()
        if not status:
            error_detail = "error: failed to retrieve eii_config"
            self.util.logger.error(error_detail)
            return False, error_detail, None
        if reset is False:
            # Apply saved config to the new config
            for component in old_config:
                if component in new_config:
                    if component.endswith("/config"):
                        new_config[component] = old_config[component]
                    elif component.endswith("/interfaces"):
                        self.merge_interfaces(new_config[component], old_config[component])

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
                    error_detail = f"Parse error. Invalid EII config file!: {exception}"
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
            return False, Util.BUSY

        status = True
        error_detail = ""
        try:
            status, error_detail, eii_config_str = self.util.load_file(
                self.util.EII_CONFIG_PATH)
            if status:
                eii_config = json.loads(eii_config_str)
                for service in config:
                    service_dir = service.rstrip(digits)
                    _, _, schema = self.util.load_file(
                        self.util.EII_DIR + service_dir + "/schema.json")
                    # A bug in platform causes VA validation to always fail
                    # This hack avoids validation for VA.
                    # TODO: remove this hack when issue is fixed in platform
                    if service_dir != "VideoAnalytics" and \
                        schema and not EiiUtil.validate_json(
                        schema, json.dumps(config[service]["config"])):
                        status = False
                        error_detail = f"Schema validation failed for {service}"
                        self.util.logger.error(error_detail)
                        break
                    eii_config[f"/{service}/config"] = config[service]["config"]
                    eii_config[f"/{service}/interfaces"] = config[service]["interfaces"]
                if status:
                    status, error_detail = self.util.store_consolidated_config(eii_config)
        except Exception as exception:
            error_detail = f"Exception while updating EII config: {exception}"
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
            with open(path, "r", encoding=Util.ENCODING) as reader:
                for line in reader.readlines():
                    key_value = line.strip().split("=")
                    if status or key_value is None or key_value[0] != key:
                        out = out + line
                        continue
                    out = out + f"{key}={value}\n"
                    status = True
            with open(path, "w", encoding=Util.ENCODING) as writer:
                writer.writelines(out)
        except Exception as exception:
            status = False
            error_detail = f"error: FAILED to update env file: {exception}"
        return status, error_detail

    def get_services_from_docker_compose_yml(self, yml):
        """Get list of services from specified docker-compose.yml file

        :param yml: path to docker-compose.yml
        :type yml: str
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
            with open(yml, 'r', encoding=Util.ENCODING) as reader:
                data = yaml.safe_load(reader)
                if "services" not in data:
                    self.util.logger.error('Invalid yaml file: No services defined')
                    return None
                for name in data["services"]:
                    services.append(name)
            status = True
        except Exception as exception:
            error_detail = f"failed to get services from {yml}: {exception}"
            self.util.logger.error(error_detail)
        return status, error_detail, services

    def builder_thread(self, services, sequential, no_cache):
        """Thread for building

        :param services: List of services to be built or "*" for all services
        :type services: [str]
        :param sequential: Whether to buid services one by one or as a whole
        :type sequential: bool
        :param no_cache: whether to use --no-cache option with build
        :type no_cache: bool
        """
        no_cache_str = "--no-cache" if no_cache else ""
        if services[0] != "*":
            services_list = services
            sequential = True
        elif sequential:
            status, error_out, services_list = \
                self.get_services_from_docker_compose_yml(self.util.EII_BUILD_PATH +
                        '/docker-compose-build.yml')
            if status is False:
                self.util.logger.error("Build FAILED: failed to parse yml file: %s",
                                       error_out)
                Util.set_state(Util.BUILD, 0, "Failed")
                self.threads[Util.BUILD][Util.ALIVE] = False
                return

        status, error_out, _ = self.util.os_command_in_host(
            "rm -f {}/build/{}".format(self.util.host_eii_dir, Util.LOGFILE_BUILD))
        if status is False:
            Util.set_state(Util.BUILD, 0, "Failed")
            self.util.logger.error(
                "Build FAILED: Failed to remove build log file: %s", error_out)
            self.threads[Util.BUILD][Util.ALIVE] = False
            return

        if sequential:
            num_services = len(services_list)
            i = 0
            for service in services_list:
                if not self.threads[Util.BUILD][Util.ALIVE]:
                    break
                status, error_out, _ = self.util.os_command_in_host(
                    'cd {}/build && docker-compose -f docker-compose-build.yml ' \
                    'build {} {} >> {} 2>&1'.format(self.util.host_eii_dir,
                                                    no_cache_str,
                                                    service,
                                                    Util.LOGFILE_BUILD))
                if status is False:
                    Util.set_state(Util.BUILD, 0, "Failed")
                    self.util.logger.error("Build FAILED: %s", error_out)
                    self.threads[Util.BUILD][Util.ALIVE] = False
                    return
                i = i + 1
                Util.set_state(Util.BUILD, int((i*100)/num_services))
        else:
            Util.set_state(Util.BUILD, 50)
            status, error_out, _ = self.util.os_command_in_host(
                'cd {}/build && docker-compose -f docker-compose-build.yml ' \
                'build {} >> {} 2>&1'.format(self.util.host_eii_dir,
                                             no_cache_str,
                                             Util.LOGFILE_BUILD))
            if status is False:
                Util.set_state(Util.BUILD, 0, "Failed")
                self.util.logger.error("Build FAILED: %s", error_out)
                self.threads[Util.BUILD][Util.ALIVE] = False
                return

        Util.set_state(Util.BUILD, 100, "Success")
        self.threads[Util.BUILD][Util.ALIVE] = False

    def do_build(self, services, sequential, no_cache):
        """Do build

        :param services: List of services to be built or "*" for all services
        :type services: [str]
        :param sequential: Whether to buid services one by one or as a whole
        :type sequential: bool
        :param no_cache: whether to use --no-cache option with build
        :type no_cache: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        if Util.is_busy():
            return False, Util.BUSY, ""

        Util.set_state(Util.BUILD, 0)
        self.util.logger.info("Building...")
        self.threads[Util.BUILD][Util.THREAD] = Thread(
            target=self.builder_thread,
            args=(services, sequential, no_cache))
        self.threads[Util.BUILD][Util.ALIVE] = True
        self.threads[Util.BUILD][Util.THREAD].start()
        return True, "", ""

    def deployer_thread(self, images, ip_address, username, password, path):
        """Thread for deploying

        :param images: List of docker images to be deployed
        :type images: [str]
        :param ip_address: Remote machine IP address
        :type ip_address: str
        :param username: Remote machine username
        :type username: str
        :param password: Remote machine password
        :type password: str
        :param path: Remote machine directory path where files need to be copied
        :type path: str

        """

        # export images to remote machine
        n_images = len(images)
        i = 0
        for image in images:
            if not self.threads[Util.DEPLOY][Util.ALIVE]:
                break
            status, error_out, _ = self.util.os_command_in_host(
                'docker save {} | bzip2 | sshpass -p "{}" ssh -o '
                'StrictHostKeyChecking=no {}@{} docker load'.format(
                    image, password, username, ip_address))
            if status is False:
                Util.set_state(Util.DEPLOY, 0, "Failed")
                self.util.logger.error("Deploy FAILED: Reason: %s", error_out)
                self.threads[Util.DEPLOY][Util.ALIVE] = False
                return
            i = i + 1
            Util.set_state(Util.DEPLOY, (i*100)/(n_images + 1))

        if not self.threads[Util.DEPLOY][Util.ALIVE]:
            Util.set_state(Util.DEPLOY, 0, "Failed")
            return

        status, error_out, _ = self.util.os_command(
            'sshpass -p "{}" rsync -r -e "ssh -o StrictHostKeyChecking=no" -z {} {}@{}:{}'
            .format(password, Util.EII_BUILD_PATH[:-1], username, ip_address, path))
        if status is False:
            Util.set_state(Util.DEPLOY, 0, "Failed")
            self.util.logger.error("Deploy FAILED: Reason: %s", error_out)
            self.threads[Util.DEPLOY][Util.ALIVE] = False
            return

        Util.set_state(Util.DEPLOY, 100, "Success")
        self.threads[Util.DEPLOY][Util.ALIVE] = False

    def do_deploy(self, images, ip_address, username, password, path):
        """Do deploy

        :param images: List of docker images to be deployed
        :type images: [str]
        :param ip_address: Remote machine IP address
        :type ip_address: str
        :param username: Remote machine username
        :type username: str
        :param password: Remote machine password
        :type password: str
        :param path: Remote machine directory path where files need to be copied
        :type path: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        if Util.is_busy():
            return False, Util.BUSY

        Util.set_state(Util.DEPLOY, 0)
        self.util.logger.info("Deploying...")
        self.threads[Util.DEPLOY][Util.THREAD] = Thread(
            target=self.deployer_thread,
            args=(images, ip_address, username, password, path))
        self.threads[Util.DEPLOY][Util.ALIVE] = True
        self.threads[Util.DEPLOY][Util.THREAD].start()
        return True, ""

    def do_get_logs_base64(self, tasks):
        """Get logs for the specified tasks

        :param tasks: List of tasks
        :type tasks: [str]
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: logs
        :rtype: dict
        """
        logs = {}
        for task in tasks:
            if task == Util.BUILD:
                log_file = Util.EII_BUILD_PATH + Util.LOGFILE_BUILD
            else:
                error_detail = f"Unknown task: {task}"
                self.util.logger.error(error_detail)
                return False, error_detail, {}

            status, error_detail, data = self.util.load_file(log_file)
            if status is False:
                self.util.logger.error("Failed to load log file: %s", log_file)
                logs[task] = ""
                continue
            logs[task] = base64.b64encode(bytes(data, Util.ENCODING)).decode(Util.ENCODING)
        return True, "", logs

    def do_generate_udf_config(self, path):
        """Generate config for the specified UDF path

        :param path: Path to UDF, relative to the IEdgeInsights directory
        :type tasks: [str]
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        :return: UDF configuration
        :rtype: dict
        """
        config = {}
        UDF_BASE_PATH = "common/video/udfs/"
        CONSTR_PREFIX = "def__init__(self"
        UDF_SIGNATURE = "classUdf:"

        # Trim leading / from path, if exist
        if path.startswith("/"):
            path = path[1:]
        if not path.startswith(UDF_BASE_PATH):
            error_detail = f"Invalid UDF path: {path}"
            self.util.logger.error(error_detail)
            return False, error_detail, {}

        try:
            # Extract UDF type from path
            udf_path = path[len(UDF_BASE_PATH):]
            tokens = udf_path.split("/")
            # Validate UDF path
            if tokens is None or len(tokens) < 2 or tokens[1].strip() == "":
                error_detail = f"Invalid UDF path: {path}"
                return False, error_detail, {}
            config["type"] = tokens[0]
            # Extract/generate UDF name from path
            # for e.g. pcb/pcb_classifier.py => pcb.pcb_classifier
            udf_name = tokens[1]
            for token in tokens[2:]:
                udf_name = udf_name + "." + token
            extn_pos = udf_name.rfind(".")
            config["name"] = udf_name if extn_pos < 0 else udf_name[:extn_pos]

            validated_udf = False
            found_params = False
            if config["type"] == "python":
                # Parse the UDF code to extract the constructor params.
                # All of these params will go to the UDF config
                with open(Util.EII_DIR + path, "r", encoding=Util.ENCODING) as filehandle:
                    for line in filehandle:
                        code = line.strip()
                        # Make sure the udf has the keyword 'class Udf'
                        if not validated_udf and "".join(code.split()) == UDF_SIGNATURE:
                            validated_udf = True
                        if not validated_udf:
                            continue
                        code = "".join(code.split())
                        if not found_params:
                            # Make sure the udf has the constructor defined
                            if not code.startswith(CONSTR_PREFIX):
                                continue
                            found_params = True
                            code = code[len(CONSTR_PREFIX):]
                        # Tokenize and extarct the constructor params
                        endpos = code.find("):")
                        if endpos >= 0:
                            code = code[:endpos]
                        params = code.split(",")
                        for param in params:
                            if param != "":
                                config[param] = ""
                        if endpos >= 0:
                            break
        except Exception as exception:
            error_detail = f"Failed to parse udf: {path}. {exception}"
            self.util.logger.error(error_detail)
            return False, error_detail, {}
        return True, "", config

    def get_eii_containers_list(self):
        """Get list of all eii containers in the system

        :return: whitespce seperated list of container id's
        :rtype: str
        """
        _ = self
        status, _, conts = self.util.os_command_in_host(
            "docker ps -qaf name=ia_*", True)
        cont_list = ""
        if status and conts:
            for cont in conts.splitlines():
                cont_list = cont_list + " " + cont
        return cont_list

    def do_run(self, action):
        """Start/stop/restart containers in the usecase

        :param action: Action to be performed: start/stop/restart
        :type action: str
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        allowed_actions = [Util.START, Util.STOP, Util.RESTART]
        if action not in allowed_actions:
            error_detail = f"error: Invalid action: {action}"
            self.util.logger.error(error_detail)
            return False, error_detail

        if Util.is_busy():
            return False, Util.BUSY

        conts = self.get_eii_containers_list()
        stop = f"docker stop {conts} && docker rm {conts};" if conts else ""
        path = self.util.host_eii_dir + "build"

        if action == Util.START:
            cmd = f"cd {path} && ./eii_start.sh"
        elif action == Util.STOP:
            cmd = f"{stop}"
        elif action == Util.RESTART:
            cmd = f"cd {path} && ./eii_start.sh"

        if cmd == "":
            self.util.logger.debug("No remote command to execute")
            return True, ""

        status, error_detail, _ = self.util.os_command_in_host(cmd)
        if not status:
            error_detail = f"error: failed to perform {action}"
            self.util.logger.error(error_detail)
            return False, error_detail
        return status, ""
