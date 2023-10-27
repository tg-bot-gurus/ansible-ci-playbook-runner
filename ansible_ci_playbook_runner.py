import os
import subprocess
import yaml

##### Global Vars

CONFIG_FILE = "playbooks_config.yml"

#####

##### Classes

class CliOption:

    name: str
    value: str | None

    def __init__(self, cli_config: dict):
        self.name = cli_config['name']
        self.value = self.resolve_value(cli_config)

    def resolve_value(self, value_config: dict) -> str:
        if not value_config.get('value',0):
            return None
        unprocessed_value = value_config['value']
        if value_config.get('value_is_env_var',0):
            assert type(unprocessed_value) is str, "Values stored as env vars can be strings only"
            return unprocessed_value if not value_config['value_is_env_var'] else self.resolve_env_type_value(unprocessed_value)
        if not type(unprocessed_value) is list:
            return unprocessed_value
        result = list()
        for element in unprocessed_value:
            if type(element) is dict:
                result.append(self.resolve_dict_value(element))
            else:
                result.append(element)
        if not value_config.get('separator',0):
            raise Exception("No separator is specified")
        return value_config['separator'].join(result)

    def resolve_env_type_value(self, value: str) -> str:
        env_var = os.environ.get(value)
        assert env_var is not None, f"{value} env var doesn't exist!"
        return env_var

    def resolve_dict_value(self, dict_value: dict) -> str:
        result_key = dict_value['name']
        if dict_value.get('value_is_env_var',0):
            result_value = dict_value['value'] if not dict_value['value_is_env_var'] else self.resolve_env_type_value(dict_value['value'])
        else:
            result_value = dict_value['value']
        return "{}={}".format(result_key,result_value)


class Command:

    command_name: str
    is_galaxy: bool
    playbook: str | None
    cli_args: list

    def __init__(self, command_name: str, cli_options: list, playbook=None):
        self.command_name = command_name
        if playbook is not None:
            self.is_galaxy = False
            self.playbook = playbook
        else:
            self.is_galaxy = True
            self.playbook = None
        self.cli_args = self.command_args(cli_options)

    def command_args(self, cli_options: list):
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


def parse_global_cli_options(command_type: str,config: dict) -> list:
    global_options = list()
    glob_opt_key = 'global_cli_options' if command_type != 'galaxy' else 'global_galaxy_cli_options'
    if config.get(glob_opt_key,0) and len(config[glob_opt_key]) > 0:
        for option in config[glob_opt_key]:
            global_options.append(CliOption(option))
    return global_options


def execute_command(command_type: str, playbook_info: dict, config: dict) -> None:
    cli_opt_key = 'cli_options' if command_type != 'galaxy' else 'galaxy_cli_options'
    global_cli_opts = parse_global_cli_options(command_type,config)
    cli_opts = list()
    for cli_opt in playbook_info[cli_opt_key]:
        cli_opts.append(CliOption(cli_opt))
    unified_cli_opts = list(set(global_cli_opts).union(cli_opts))
    if command_type != 'galaxy':
        command = Command('ansible-playbook',unified_cli_opts,playbook_info['path'])
    else:
        command = Command('ansible-galaxy',unified_cli_opts)
    command.run_command()


def process_playbook_data(playbook_info: dict, config: dict) -> None:
    if playbook_info['galaxy_deps_required']:
        if (not playbook_info.get('galaxy_cli_options',0) or
            len(playbook_info['galaxy_cli_options']) == 0):
            raise ValueError("galaxy_cli_options must be defined")
        execute_command('galaxy',playbook_info,config)
    if (not playbook_info.get('cli_options',0) or
        len(playbook_info['cli_options']) == 0):
        raise ValueError("Playbook-level cli_options must be defined")
    execute_command('playbook',playbook_info,config)


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
