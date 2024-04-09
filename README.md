# ansible-ci-playbook-runner
Python script that could be used as a supporting tool for running multiple Ansible playbooks in CI environments. In a nutshell, the script is a wrapper around `ansible-playbook` and `ansible-galaxy` which enables anyone to process one or more Ansible playbooks along with the corresponding `requirements.yml` files.

# How to use
1. Make sure to place the `playbooks_config.yml` configuration file in your local project. See below for more details.
2. Clone this repository and make sure the main Python script [ansible_ci_playbook_runner.py](./ansible_ci_playbook_runner.py) is placed at the same level as `playbooks_config.yml`.
3. Run the script :)

# Config file
The main configuration file the script relies on is `playbooks_config.yml`. This configuration file lists various options for launching one or more Ansible playbooks. See [playbooks_config.yml](./playbooks_config.yml) for reference. Here is a brief description of some config file entries:
1. `playbooks` key contains a list of dictionaries representing playbooks. Each playbook entry consists of the following elements:
   * `name` (*string*): a meaningful playbook name
   * `path` (*string*): path to the playbook (relative to the [ansible_ci_playbook_runner.py](./ansible_ci_playbook_runner.py) script)
   * `cli_options` (*list[dict]*): a list of `ansible-playbook`/`ansible-galaxy` CLI arguments.
       - if an argument value's type is a *string*, a cli_option element must contain at least `name` and `value` keys. If the value is an environment variable, an additional key should be specified to indicate that - `value_is_env_var`, which accepts a boolean value (`True` or `False`). If the value is a base64-encoded string, an additional key should also be specified - `is_base64`, which accepts a boolean value (`True` or `False`).
       - if an argument value's type is a *list*, an additional key should be specified - `separator`. For instance, some `ansible-playbook` CLI arguments, such as `--limit` accept a comma-separated string, and if, when using this tool, you decide to specify a list of hosts/groups in the `--limit` argument as a YAML list, you'll have to specify the `separator` key with the value `,`. Another use case is arguments that can be specified more than once, such as `--extra-vars`. The current automation deals with such arguments in the following way: the `' '` is specified as a separator, and its value is a list of cli_options abiding by exactly the same rules as mentioned earlier.
     * `galaxy_deps_required` (*bool*): determines whether Galaxy dependencies should be installed or not.
     * `galaxy_cli_options` (*list[dict]*): the same as `cli_options` described above.
2. `global_cli_options` (*list[dict]*): a list of cli_options to apply to all `ansible-playbook` runs.
3. `global_galaxy_cli_options` (*list[dict]*): a list of cli_options to apply to all `ansible-galaxy` runs.

