from typing import Union
from enum import Enum

import base64
import argparse
import os
import sys
import subprocess
import yaml

##### Arg parsing

PARSER = argparse.ArgumentParser()
PARSER.add_argument(
    '--debug_mode',
    type=bool,
    required=False,
    default=os.environ.get('PLAY_RUNNER_DEBUG', default=False))
PARSER.add_argument(
    '--config_path',
    type=str,
    required=False,
    default=os.environ.get('PLAY_RUNNER_CONFIG', default='playbooks_config.yml'))
PARSER.add_argument(
    '--playbooks',
    type=str,
    required=False,
    default=os.environ.get('PLAY_RUNNER_PLAYBOOKS', default=''))
ARGS = PARSER.parse_args()

#####

##### Global Vars

CONFIG_FILE = ARGS.config_path
DEBUG_MODE = ARGS.debug_mode
PLAYBOOKS_LIMIT = ARGS.playbooks.split(';') if len(ARGS.playbooks) > 0 else list()
EXIT_CODES = list()

#####

##### Classes

class CommandType(Enum):
    GALAXY = {
        'command': 'ansible-galaxy',
        'value_name': 'galaxy_cli_options',
        'global_value_name': 'global_galaxy_cli_options'
    }
    PLAYBOOK = {
        'command': 'ansible-playbook',
        'value_name': 'cli_options',
        'global_value_name': 'global_cli_options'
    }


class CliOption:

    name: str
    value: str | None

    def __init__(self, cli_config: dict[str, Union[int, str, bool]]):
        self.name = cli_config['name']
        self.value = self.resolve_value(self.supply_missing_keys(cli_config))

    def supply_missing_keys(self, value_config: dict[str, Union[int, str, bool]]):
        if not value_config.get('value_is_env_var', False):
            value_config['value_is_env_var'] = False
        if not value_config.get('is_base64', False):
            value_config['is_base64'] = False
        if not value_config.get('value', False):
            value_config['value'] = None
        return value_config

    def resolve_value(self, value_config: dict[str, Union[int, str, bool]]) -> str:
        if value_config['value'] is None:
            return None
        unprocessed_value = value_config['value']
        if not isinstance(unprocessed_value, list):
            out_value = (unprocessed_value
                         if not value_config['value_is_env_var']
                         else self.resolve_env_type_value(unprocessed_value))
            return str(out_value) if not value_config['is_base64'] else self.decode_b64(out_value)
        result = list()
        for element in unprocessed_value:
            if isinstance(element, dict):
                result.append(self.resolve_dict_value(self.supply_missing_keys(element)))
            else:
                result.append(element)
        if not value_config.get('separator', False):
            raise Exception("No separator is specified")
        return '{}'.format(value_config['separator'].join(result))

    def decode_b64(self, value: str):
        return base64.b64decode(value).decode('utf-8')

    def resolve_env_type_value(self, value: str) -> str:
        env_var = os.environ.get(value)
        assert env_var is not None, f"{value} env var doesn't exist!"
        return str(env_var)

    def resolve_dict_value(self, value_config: dict[str, Union[int, str, bool]]) -> str:
        result_key = value_config['name']
        result = (value_config['value']
                  if not value_config['value_is_env_var']
                  else self.resolve_env_type_value(value_config['value']))
        result_value = result if not value_config['is_base64'] else self.decode_b64(result)
        return '{}={}'.format(result_key, result_value)


class Command:

    command_name: str
    cli_args: list

    def __init__(self, command_type: CommandType, cli_options: list[CliOption], playbook_path=None):
        self.command_name = command_type.value['command']
        self.command_type = command_type
        self.cli_args = self.command_args(cli_options, playbook_path)

    def command_args(self, cli_options: list[CliOption], playbook_path):
        args_list = [self.command_name]
        if self.command_type == CommandType.GALAXY:
            args_list.append('install')
        else:
            args_list.append(playbook_path)
            if os.environ.get('ANSIBLE_CHECK_MODE', default=False):
                args_list.append('-C')
        for cli_option in cli_options:
            if cli_option.value is not None:
                args_list.append(cli_option.name)
                args_list.append(cli_option.value)
            else:
                args_list.append(cli_option.name)
        return args_list

    def run_command(self) -> None:
        try:
            process = subprocess.run(self.cli_args, check=False)
            EXIT_CODES.append(process.returncode)
            print_debug_output("Executed command is '{}'. Its returncode is {}".format(
                self.cli_args, process.returncode))
        except subprocess.CalledProcessError as excep:
            print("Failed to run {}: {}".format(self.cli_args, excep))
            EXIT_CODES.append(1)


#####

##### functions

def print_debug_output(message: str) -> None:
    if DEBUG_MODE:
        print(message)


def load_config() -> dict:
    with open(CONFIG_FILE, 'r') as conf_file:
        config = dict(yaml.safe_load(conf_file))
    return config


def parse_global_cli_options(command_type: CommandType,
                             config: dict[str, Union[int, str, bool, list, dict]]) -> list:
    global_options = list()
    glob_opt_key = command_type.value['global_value_name']
    if config.get(glob_opt_key, False) and len(config[glob_opt_key]) > 0:
        for option in config[glob_opt_key]:
            global_options.append(CliOption(option))
    return global_options


def execute_command(command_type: CommandType,
                    playbook_info: dict[str, Union[int, str, bool, list, dict]],
                    config: dict[str, Union[int, str, bool, list, dict]]) -> None:
    cli_opt_key = command_type.value['value_name']
    global_cli_opts = parse_global_cli_options(command_type, config)
    cli_opts = list()
    for cli_opt in playbook_info[cli_opt_key]:
        cli_opts.append(CliOption(cli_opt))
    unified_cli_opts = list(set(global_cli_opts).union(cli_opts))
    command = Command(command_type, unified_cli_opts, playbook_info['path'])
    command.run_command()


def process_playbook_data(playbook_info: dict[str, Union[int, str, bool, list, dict]],
                          config: dict[str, Union[int, str, bool, list, dict]]) -> None:
    if playbook_info['galaxy_deps_required']:
        if (not playbook_info.get('galaxy_cli_options', False) or
                len(playbook_info['galaxy_cli_options']) == 0):
            raise ValueError("galaxy_cli_options must be defined")
        execute_command(CommandType.GALAXY, playbook_info, config)
    if (not playbook_info.get('cli_options', False) or
            len(playbook_info['cli_options']) == 0):
        raise ValueError("Playbook-level cli_options must be defined")
    execute_command(CommandType.PLAYBOOK, playbook_info, config)


def main() -> None:
    playbooks_config = load_config()
    if not playbooks_config.get('playbooks', False) or len(playbooks_config['playbooks']) == 0:
        print("Noting to work with. Please add playbooks to config as described in README")
        return
    playbooks = playbooks_config['playbooks']
    for playbook in playbooks:
        if len(PLAYBOOKS_LIMIT) > 0 and playbook.name not in PLAYBOOKS_LIMIT:
            continue
        process_playbook_data(playbook, playbooks_config)
    if len(EXIT_CODES) == 0:
        raise Exception("Something went wrong! EXIT_CODES list is empty")
    no_dup_exit_codes = list(set(EXIT_CODES))
    if len(no_dup_exit_codes) > 1 or no_dup_exit_codes[0] != 0:
        print_debug_output("Exiting with a non-zero exit code")
        sys.exit(1)

#####

##### main body

if __name__ == "__main__":
    main()
