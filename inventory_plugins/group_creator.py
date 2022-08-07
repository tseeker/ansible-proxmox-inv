import os

from ansible import constants as C
from ansible.errors import AnsibleParserError
from ansible.module_utils._text import to_native
from ansible.plugins.inventory import BaseInventoryPlugin


DOCUMENTATION = """
    name: group_creator
    short_description: Uses Jinja2 templates to construct empty groups.
    description:
    - Uses a YAML configuration file with a valid YAML extension to define
      groups. The groups' names as well as the list of parent groups for a
      given group may use Jinja2 templates based on the host variables.
    options:
      plugin:
        description:
        - Token that ensures this is a source file for the C(group_creator)
          plugin.
        required: True
        choices: ['group_creator']
      groups:
        description:
        - The list of groups to create.
        type: list
        elements: dict
        required: True
        suboptions:
          name:
            description:
            - The template to generate a group name from. If an empty
              string is returned, the group will not be created.
            type: str
            required: true
          parents:
            description:
            - A list of templates to generate the names of the group's
              parents from. Empty strings will be ignored.
            type: list
            elements: str
            default: []
      strict:
          description:
          - If C(yes) make invalid templates a fatal error, otherwise skip and
            continue.
          required: False
          type: bool
          default: no
"""


class InventoryModule(BaseInventoryPlugin):
    """Constructs empty groups based on arbitrary variables."""

    NAME = "group_creator"

    def __init__(self):
        super(InventoryModule, self).__init__()

    def verify_file(self, path):
        valid = False
        if super(InventoryModule, self).verify_file(path):
            file_name, ext = os.path.splitext(path)
            if not ext or ext in ['.config'] + C.YAML_FILENAME_EXTENSIONS:
                valid = True
        return valid

    def _evaluate(self, template, variables, auto_template):
        t = self.templar
        if auto_template:
            template = "%s%s%s" % (
                t.environment.variable_start_string,
                template,
                t.environment.variable_end_string,
            )
        t.available_variables = variables
        return t.template(template, disable_lookups=True)

    def _get_group_name(self, host, name, host_vars, strict):
        try:
            name = self._evaluate(name, host_vars, False)
            return self._sanitize_group_name(name)
        except Exception as e:
            if strict:
                raise AnsibleParserError(
                    "Could not generate group name for host %s from '%s': (%s) %s"
                    % (host, name, to_native(repr(type(e))), to_native(e))
                )
            return ""

    def parse(self, inventory, loader, path, cache=False):
        super(InventoryModule, self).parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)
        strict = self.get_option("strict")
        for host in inventory.hosts:
            host_vars = self.inventory.get_host(host).get_vars()
            for group in self.get_option("groups"):
                name = self._get_group_name(host, group['name'], host_vars, strict)
                if not name:
                    continue
                self.inventory.add_group(name)
                for ptmpl in group.get("parents"):
                    parent = self._get_group_name(host, ptmpl, host_vars, strict)
                    if parent:
                        self.inventory.add_group(parent)
                        self.inventory.add_child(parent, name)
