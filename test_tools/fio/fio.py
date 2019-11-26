#
# Copyright(c) 2019 Intel Corporation
# SPDX-License-Identifier: BSD-3-Clause-Clear
#

import datetime

import test_tools.fio.fio_param
import test_tools.fs_utils
from core.test_run import TestRun
from test_tools import fs_utils
from test_utils import os_utils


class Fio:
    def __init__(self, executor_obj=None):
        self.fio_version = "fio-3.7"
        self.default_run_time = datetime.timedelta(hours=1)
        self.jobs = []
        self.executor = executor_obj if executor_obj is not None else TestRun.executor
        self.base_cmd_parameters: test_tools.fio.fio_param.FioParam = None
        self.global_cmd_parameters: test_tools.fio.fio_param.FioParam = None

    def create_command(self):
        self.base_cmd_parameters = test_tools.fio.fio_param.FioParamCmd(self, self.executor)
        self.global_cmd_parameters = test_tools.fio.fio_param.FioParamConfig(self, self.executor)
        self.fio_file = f'fio_run_{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%s")}'
        self.base_cmd_parameters\
            .set_param('eta', 'always')\
            .set_param('output-format', 'json')\
            .set_param('output', self.fio_file)
        return self.global_cmd_parameters

    def is_installed(self):
        return self.executor.run("fio --version").stdout.strip() == self.fio_version

    def install(self):
        fio_url = f"http://brick.kernel.dk/snaps/{self.fio_version}.tar.bz2"
        fio_package = os_utils.download_file(fio_url)
        fs_utils.uncompress_archive(fio_package)
        TestRun.executor.run_expect_success(
            f"cd {fio_package.parent_dir}/{self.fio_version};"
            f"./configure && make -j && make install"
        )

    def calculate_timeout(self):
        if self.global_cmd_parameters.get_parameter_value("time_based") is None:
            return self.default_run_time

        total_time = self.global_cmd_parameters.get_parameter_value("runtime")
        ramp_time = self.global_cmd_parameters.get_parameter_value("ramp_time")
        if ramp_time is not None:
            total_time += ramp_time
        return datetime.timedelta(seconds=total_time)

    def run(self, timeout: datetime.timedelta = None):
        timeout = self.prepare_run(timeout)
        return self.executor.run(str(self), timeout)

    def run_in_background(self, timeout: datetime.timedelta = None):
        self.prepare_run(timeout)
        return self.executor.run_in_background(str(self))

    def prepare_run(self, timeout: datetime.timedelta = None):
        if not self.is_installed():
            self.install()

        if timeout is None:
            timeout = self.calculate_timeout()

        if len(self.jobs) > 0:
            self.executor.run(f"{str(self)}-showcmd -")
            TestRun.LOGGER.info(self.executor.run(f"cat {self.fio_file}").stdout)
        TestRun.LOGGER.info(str(self))
        return timeout

    def execution_cmd_parameters(self):
        if len(self.jobs) > 0:
            separator = "\n\n"
            return f"{str(self.global_cmd_parameters)}\n" \
                f"{separator.join(str(job) for job in self.jobs)}"
        else:
            return str(self.global_cmd_parameters)

    def __str__(self):
        if len(self.jobs) > 0:
            command = f"echo '{self.execution_cmd_parameters()}' |" \
                f" {str(self.base_cmd_parameters)} -"
        else:
            fio_parameters = test_tools.fio.fio_param.FioParamCmd(self, self.executor)
            fio_parameters.command_param_dict.update(self.base_cmd_parameters.command_param_dict)
            fio_parameters.command_param_dict.update(self.global_cmd_parameters.command_param_dict)
            fio_parameters.command_flags.extend(self.global_cmd_parameters.command_flags)
            fio_parameters.set_param('name', 'fio')
            command = str(fio_parameters)
        return command
