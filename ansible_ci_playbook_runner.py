import os
import subprocess
import yaml

from typing import Union
from enum import Enum

##### Global Vars

CONFIG_FILE = "playbooks_config.yml"


#####

##### Classes

class CommandType(Enum):
    GALAXY = {
        'command': 'ansible-galaxy',
        'value_name': 'galaxy_cli_options',
        'global_value_name': 'global_galaxy_cli_options',
        'is_playbook': False
    }
    PLAYBOOK = {
        'command': 'ansible-playbook',
        'value_name': 'cli_options',
        'global_value_name': 'global_cli_options',
        'is_playbook': True
    }


class CliOption:

    name: str
    value: str | None

    def __init__(self, cli_config: dict[str,Union[int, str, bool]]):
        self.name = cli_config['name']
        self.value = self.resolve_value(cli_config)

    def resolve_value(self, value_config: dict[str,Union[int, str, bool]]) -> str:
        if not value_config.get('value',False):
            return None
        unprocessed_value = value_config['value']
        if value_config.get('value_is_env_var',False):
            assert type(unprocessed_value) is str, "Values stored as env vars can be strings only"
            return unprocessed_value if not value_config['value_is_env_var'] else self.resolve_env_type_value(unprocessed_value)
        if not type(unprocessed_value) is list:
            return unprocessed_value
        result = list()
        for element in unprocessed_value:
            if isinstance(element, dict):
                result.append(self.resolve_dict_value(element))
            else:
                result.append(element)
        if not value_config.get('separator',False):
            raise Exception("No separator is specified")
        return value_config['separator'].join(result)

    def resolve_env_type_value(self, value: str) -> str:
        env_var = os.environ.get(value)
        assert env_var is not None, f"{value} env var doesn't exist!"
        return env_var

    def resolve_dict_value(self, value: dict[str,Union[int, str, bool]]) -> str:
        result_key = value['name']
        if value.get('value_is_env_var',False):
            result_value = value['value'] if not value['value_is_env_var'] else self.resolve_env_type_value(value['value'])
        else:
            result_value = value['value']
        return "{}={}".format(result_key,result_value)


class Command:

    command_name: str
    is_galaxy: bool
    playbook: str | None
    cli_args: list

    def __init__(self, command_name: str, cli_options: list[CliOption], playbook=None):
        self.command_name = command_name
        if playbook is not None:
            self.is_galaxy = False
            self.playbook = playbook
        else:
            self.is_galaxy = True
            self.playbook = None
        self.cli_args = self.command_args(cli_options)

    def command_args(self, cli_options: list[CliOption]):
        args_list = [self.command_name]
        for cli_option in cli_options:
            if cli_option.value is not None:
                args_list.append("{} {}".format(cli_option.name,cli_option.value))
            else:
                args_list.append(cli_option.name)
        if not self.is_galaxy:
            if os.environ.get('ANSIBLE_CHECK_MODE',default=False):
                args_list.append('-C')
            args_list.append(self.playbook)
        return args_list

    def run_command(self) -> None:
        try:
            print("Executing '{}'".format(self.cli_args))
            subprocess.run(self.cli_args,capture_output=True)
        except Exception as e:
            print("Failed to run {}: {}".format(self.cli_args,e))


#####

##### functions

def load_config() -> dict:
    with open(CONFIG_FILE, 'r') as f:
        config = dict(yaml.safe_load(f))
    return config


def parse_global_cli_options(command_type: CommandType, config: dict[str, Union[int, str, bool, list, dict]]) -> list:
    global_options = list()
    glob_opt_key = command_type.value['global_value_name']
    if config.get(glob_opt_key,False) and len(config[glob_opt_key]) > 0:
        for option in config[glob_opt_key]:
            global_options.append(CliOption(option))
    return global_options


def execute_command(command_type: CommandType,
                    playbook_info: dict[str, Union[int, str, bool, list, dict]],
                    config: dict[str, Union[int, str, bool, list, dict]]) -> None:
    cli_opt_key = command_type.value['value_name']
    global_cli_opts = parse_global_cli_options(command_type,config)
    cli_opts = list()
    for cli_opt in playbook_info[cli_opt_key]:
        cli_opts.append(CliOption(cli_opt))
    unified_cli_opts = list(set(global_cli_opts).union(cli_opts))
    playbook_path = playbook_info['path'] if command_type.value['is_playbook'] else None
    command = Command(command_type.value['command'],unified_cli_opts,playbook_path)
    command.run_command()


def process_playbook_data(playbook_info: dict[str, Union[int, str, bool, list, dict]],
                          config: dict[str, Union[int, str, bool, list, dict]]) -> None:
    if playbook_info['galaxy_deps_required']:
        if (not playbook_info.get('galaxy_cli_options',False) or
            len(playbook_info['galaxy_cli_options']) == 0):
            raise ValueError("galaxy_cli_options must be defined")
        execute_command(CommandType.GALAXY,playbook_info,config)
    if (not playbook_info.get('cli_options',False) or
        len(playbook_info['cli_options']) == 0):
        raise ValueError("Playbook-level cli_options must be defined")
    execute_command(CommandType.PLAYBOOK,playbook_info,config)


def main() -> None:
    playbooks_config = load_config()
    if not playbooks_config.get('playbooks',0) or len(playbooks_config['playbooks']) == 0:
        print("Noting to work with. Please add playbooks to config as described in README")
        return
    playbooks = playbooks_config['playbooks']
    for playbook in playbooks:
        process_playbook_data(playbook,playbooks_config)


#####

##### main body

if __name__ == "__main__":
    main()
