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

""" Module for project handling """

import os
from .util import Util

class Project():
    """ The projects module contain classes to manage projects in the Deployment tool """

    def __init__(self):
        pass

    def do_load_project(self, name):
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
        _ = self
        util = Util()
        path = util.EII_PROJECTS_PATH + name + util.JSON_EXT
        status, error_detail, config = util.get_consolidated_config(path)
        if status is False:
            util.logger.error("Failed to load project %s: %s", name, error_detail)
        else:
            store_config = config.copy()
            store_config.pop(util.DT_CONFIG_KEY, None)
            status, error_detail = util.store_consolidated_config(store_config)

        return status, error_detail, config


    def do_store_project(self, name, show_wv, replace = True):
        """Create config file for the current unsaved project

        :param name: name for the project
        :type name: str
        :param show_wv: Whether to include Web Visualizer in usecase
        :type show_wv: bool
        :param replace: Whether replace existing file
        :type replace: bool
        :return: status of operation
        :rtype: bool
        :return: error description
        :rtype: str
        """
        _ = self
        util = Util()
        status, error_detail, config = util.get_consolidated_config()
        if status:
            path = util.EII_PROJECTS_PATH + name + util.JSON_EXT
            if replace is False and os.path.isfile(path):
                util.logger.error("Error: destination file %s already exists!", path)
                status = False
            else:
                config[util.DT_CONFIG_KEY] = {util.SHOW_WV: show_wv}
                status, error_detail = util.store_consolidated_config(config, path)
        return status, error_detail


    def do_list_projects(self):
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
        _ = self
        util = Util()
        status, error_detail, dir_info = util.scan_dir(util.EII_PROJECTS_PATH)
        if status:
            projects = [ p[:-5] for p in dir_info["files"] if p.endswith(util.JSON_EXT) ]
        else:
            projects = None
        return status, error_detail, projects
